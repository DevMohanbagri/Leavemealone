"""LeaveMeAlone local server. Binds on the machine you run it on."""

from __future__ import annotations

import asyncio
import io
import re
import zipfile
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.catalog import load_catalog
from app.db import DB
from app.letters import (
    COMPLAINTS,
    LAWS,
    US_STATES,
    applicable_laws,
    build_letter,
    chunked,
    deadline_from,
    full_name,
    normalize_state,
    response_days,
)
from app.packet import render_packet
from app.sample import install_sample
from app.scanner import (
    UA,
    classify_page,
    corroborate,
    fill_search_url,
    parse_breaches,
    parse_ddg,
    queries_for,
)
from app.scoring import coverage, effective_status, exposure_label, exposure_score

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"

db = DB()
catalog = load_catalog()
http_client: httpx.AsyncClient | None = None
scan_tasks: dict[int, asyncio.Task] = {}

app = FastAPI(title="LeaveMeAlone", version=__version__, docs_url=None, redoc_url=None)


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


@app.on_event("startup")
async def startup() -> None:
    global http_client
    db._write(
        "UPDATE scans SET status = 'failed', error = 'The app restarted before this scan finished.', finished_at = ? WHERE status = 'running'",
        (utcnow(),),
    )
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(8.0, connect=5.0),
        follow_redirects=True,
        headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/json"},
        limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
    )
    asyncio.create_task(monitor_loop())


@app.on_event("shutdown")
async def shutdown() -> None:
    if http_client:
        await http_client.aclose()


def require_profile(profile_id: int) -> dict:
    profile = db.get_profile(profile_id)
    if not profile:
        raise HTTPException(404, "No dossier with that id.")
    return profile


def clean_profile(body: dict) -> dict:
    if not isinstance(body, dict):
        raise HTTPException(400, "Send a JSON dossier.")
    first = str(body.get("first_name") or "").strip()
    last = str(body.get("last_name") or "").strip()
    if not first or not last:
        raise HTTPException(400, "First and last name are required.")
    if len(first) > 80 or len(last) > 80:
        raise HTTPException(400, "That name is too long.")
    if not body.get("authorized"):
        raise HTTPException(400, "Confirm this is your information, or that you are allowed to act for this person.")
    emails = []
    for raw in (body.get("emails") or [])[:8]:
        email = str(raw).strip()
        if not email:
            continue
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            raise HTTPException(400, f"That email doesn't look right: {email}")
        emails.append(email)
    phones = []
    for raw in (body.get("phones") or [])[:8]:
        number = "".join(ch for ch in str(raw) if ch.isdigit())
        if not number:
            continue
        if not 7 <= len(number) <= 15:
            raise HTTPException(400, "Use a phone number of 7 to 15 digits.")
        phones.append(number)
    aliases = []
    for alias in (body.get("aliases") or [])[:6]:
        if not isinstance(alias, dict):
            continue
        aliases.append(
            {
                "first": str(alias.get("first") or "").strip()[:80],
                "last": str(alias.get("last") or "").strip()[:80],
            }
        )
    aliases = [a for a in aliases if a["first"] or a["last"]]
    addresses = []
    for raw in (body.get("addresses") or [])[:4]:
        if not isinstance(raw, dict):
            continue
        addresses.append(
            {
                "street": str(raw.get("street") or "").strip()[:120],
                "city": str(raw.get("city") or "").strip()[:80],
                "state": normalize_state(str(raw.get("state") or ""))[:2],
                "zip": str(raw.get("zip") or "").strip()[:12],
                "current": bool(raw.get("current", True)),
            }
        )
    if not emails and not phones and not any(a.get("city") for a in addresses):
        raise HTTPException(400, "Add an email, a phone, or a city. A name alone is too easy to mismatch.")
    dob = str(body.get("dob") or "").strip()
    if dob and not re.match(r"^\d{4}-\d{2}-\d{2}$", dob):
        raise HTTPException(400, "Date of birth should be YYYY-MM-DD, or leave it blank.")
    country = str(body.get("country") or "US").strip().upper()[:8] or "US"
    residence = normalize_state(str(body.get("residence_state") or (addresses[0]["state"] if addresses else "")))
    return {
        "label": str(body.get("label") or f"{first} {last}").strip()[:80],
        "first_name": first,
        "last_name": last,
        "middle_name": str(body.get("middle_name") or "").strip()[:80],
        "aliases": aliases,
        "emails": emails,
        "phones": phones,
        "addresses": addresses,
        "residence_state": residence,
        "country": country,
        "dob": dob or None,
        "include_dob": bool(body.get("include_dob")),
        "scan_phone": bool(body.get("scan_phone")),
        "flags": body.get("flags") if isinstance(body.get("flags"), dict) else {},
    }


def broker_name(broker_id: str | None) -> str:
    if not broker_id:
        return "Open web"
    broker = catalog.get(broker_id)
    return broker["name"] if broker else broker_id


def decorate_sighting(row: dict) -> dict:
    broker = catalog.get(row["broker_id"]) if row.get("broker_id") else None
    row = dict(row)
    row["broker_name"] = broker["name"] if broker else (row.get("title") or "Open web")
    row["category"] = broker.get("category") if broker else row.get("source")
    row["display_status"] = effective_status(row)
    row["optout_url"] = broker.get("optout_url") if broker else None
    row["erasable"] = broker.get("erasable") if broker else "suppress"
    return row


def decorate_removal(row: dict) -> dict:
    broker = catalog.get(row["broker_id"])
    row = dict(row)
    row["broker_name"] = broker["name"] if broker else row["broker_id"]
    row["category"] = broker.get("category") if broker else ""
    row["priority"] = broker.get("priority") if broker else 5
    row["relisting"] = broker.get("relisting") if broker else "medium"
    row["optout_url"] = broker.get("optout_url") if broker else None
    row["email"] = broker.get("email") if broker else None
    row["phone"] = broker.get("phone") if broker else None
    row["postal"] = broker.get("postal") if broker else None
    row["cloudflare"] = bool(broker.get("cloudflare")) if broker else False
    row["captcha"] = bool(broker.get("captcha")) if broker else False
    row["domain"] = broker.get("domain") if broker else ""
    row["overdue"] = bool(
        row["status"] == "submitted" and row.get("deadline_at") and row["deadline_at"] < today()
    )
    row["cluster_id"] = broker.get("cluster_id") if broker else None
    return row


def note_overdue(profile_id: int) -> None:
    for removal in db.list_removals(profile_id):
        if removal["status"] != "submitted" or not removal.get("deadline_at"):
            continue
        if removal["deadline_at"] >= today():
            continue
        if db.has_recent_alert(profile_id, "overdue", removal["broker_id"]):
            continue
        name = broker_name(removal["broker_id"])
        db.add_alert(
            profile_id,
            "overdue",
            f"{name} missed the deadline",
            f"You sent this on {(removal.get('submitted_at') or '')[:10]}. The deadline was {removal['deadline_at']}. Write the follow-up.",
            utcnow(),
            removal["broker_id"],
        )


def desk_payload(profile: dict) -> dict:
    note_overdue(profile["id"])
    sightings = [decorate_sighting(s) for s in db.list_sightings(profile["id"])]
    removals = [decorate_removal(r) for r in db.list_removals(profile["id"])]
    score = exposure_score(sightings)
    universe = len(catalog.active())
    counts = {
        "exposed": sum(1 for s in sightings if s["display_status"] == "exposed" and s["source"] != "breach"),
        "possible": sum(1 for s in sightings if s["display_status"] == "possible"),
        "blocked": sum(1 for s in sightings if s["display_status"] == "blocked"),
        "clear": sum(1 for s in sightings if s["display_status"] == "clear"),
        "breach": sum(1 for s in sightings if s["source"] == "breach" and s["display_status"] == "exposed"),
        "queued": sum(1 for r in removals if r["status"] == "queued"),
        "submitted": sum(1 for r in removals if r["status"] == "submitted"),
        "confirmed": sum(1 for r in removals if r["status"] == "confirmed"),
        "overdue": sum(1 for r in removals if r["overdue"]),
        "reappeared": sum(1 for r in removals if r["status"] == "reappeared"),
    }
    return {
        "profile": profile,
        "sightings": sightings,
        "removals": removals,
        "alerts": db.list_alerts(profile["id"]),
        "unread": db.unread_count(profile["id"]),
        "monitor": db.get_monitor(profile["id"]),
        "history": db.scan_history(profile["id"]),
        "score": score,
        "exposure_label": exposure_label(score),
        "coverage": coverage(removals, universe),
        "universe": universe,
        "counts": counts,
        "laws": applicable_laws(profile),
        "days": response_days(profile),
    }


def remember_change(profile_id: int, change: dict | None, finding: dict) -> None:
    if not change:
        return
    status = finding.get("status")
    if change["kind"] == "new" and status not in {"exposed", "possible"}:
        return
    if change["kind"] == "new" and status == "possible" and finding.get("source") != "probe":
        return
    broker_id = change.get("broker_id")
    name = finding.get("title") or broker_name(broker_id)
    detail = finding.get("snippet") or finding.get("detail") or ""
    if change["kind"] == "reappeared":
        title = f"{name} put you back"
        body = detail or "A listing that was clear is showing your details again."
        if broker_id:
            db.mark_reappeared(profile_id, broker_id)
    elif change["kind"] == "cleared":
        title = f"{name} looks clear"
        body = "The latest check did not find a corroborated listing."
    else:
        title = f"New trace · {name}"
        body = detail or "A check found your name with a corroborating detail."
    db.add_alert(profile_id, "breach" if finding.get("source") == "breach" else change["kind"], title, body[:500], utcnow(), broker_id)


def pick_brokers(profile: dict, scope: str) -> list[dict]:
    active = [b for b in catalog.active() if b.get("scannable") and b.get("search_url")]
    relist_rank = {"certain": 0, "high": 1, "medium": 2, "low": 3, "none": 4}
    active.sort(key=lambda b: (b.get("priority") or 5, relist_rank.get(b.get("relisting"), 2), b["name"]))
    if scope == "deep":
        chosen = active[:120]
    elif scope == "monitor":
        hot = set()
        for sighting in db.list_sightings(profile["id"]):
            status = effective_status(sighting)
            if sighting.get("broker_id") and status in {"exposed", "possible", "blocked"}:
                hot.add(sighting["broker_id"])
        for removal in db.list_removals(profile["id"]):
            if removal["status"] == "reappeared":
                hot.add(removal["broker_id"])
        chosen = [b for b in active if b["id"] in hot or (b.get("priority", 5) <= 2 and b.get("relisting") in {"high", "certain"})]
        chosen = chosen[:24]
    else:
        chosen = [b for b in active if (b.get("priority") or 5) <= 2][:36]
    if scope == "deep":
        return chosen
    return chosen


async def check_breaches(email: str) -> tuple[list[dict], str]:
    assert http_client
    errors = []
    found: list[dict] = []
    try:
        response = await http_client.get(
            f"https://api.xposedornot.com/v1/check-email/{quote(email)}",
            headers={"Accept": "application/json", "User-Agent": "LeaveMeAlone/1.0"},
        )
        if response.status_code == 404:
            pass
        elif response.status_code >= 400:
            errors.append(f"breach index returned {response.status_code}")
        else:
            found.extend(parse_breaches(response.json()))
    except httpx.HTTPError:
        errors.append("breach index did not answer")
    hibp = db.setting("hibp_api_key")
    if hibp:
        try:
            response = await http_client.get(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{quote(email)}",
                headers={"hibp-api-key": hibp, "user-agent": "LeaveMeAlone"},
            )
            if response.status_code == 404:
                pass
            elif response.status_code == 401:
                errors.append("Have I Been Pwned rejected the API key")
            elif response.status_code < 400:
                found.extend(parse_breaches(response.json()))
            else:
                errors.append(f"Have I Been Pwned returned {response.status_code}")
        except httpx.HTTPError:
            errors.append("Have I Been Pwned did not answer")
    # Deduplicate by name.
    uniq = []
    seen = set()
    for item in found:
        key = item["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    return uniq, "; ".join(errors)


async def search_web(query: str) -> tuple[list[dict], str]:
    assert http_client
    try:
        response = await http_client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query, "kl": "us-en"},
            headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code >= 400:
            return [], f"web search returned {response.status_code}"
        return parse_ddg(response.text)[:12], ""
    except httpx.HTTPError:
        return [], "web search did not answer"


async def execute_scan(scan_id: int, profile_id: int, scope: str) -> None:
    profile = db.get_profile(profile_id)
    if not profile:
        return
    summary = {
        "exposed": 0,
        "possible": 0,
        "clear": 0,
        "blocked": 0,
        "unreachable": 0,
        "inconclusive": 0,
        "breaches": 0,
        "web": 0,
        "checked": 0,
    }
    try:
        brokers = pick_brokers(profile, scope)
        db.add_event(scan_id, "start", {"scope": scope, "probes": len(brokers), "sample": False})
        for email in (profile.get("emails") or [])[:4]:
            breaches, error = await check_breaches(email)
            if error and not breaches:
                db.add_event(scan_id, "breach", {"email": email, "status": "unreachable", "detail": error})
                summary["unreachable"] += 1
            elif not breaches:
                db.add_event(scan_id, "breach", {"email": email, "status": "clear", "detail": "No known breach for this address."})
                summary["clear"] += 1
            for breach in breaches:
                summary["breaches"] += 1
                summary["exposed"] += 1
                finding = {
                    "broker_id": None,
                    "source": "breach",
                    "status": "exposed",
                    "url": "https://xposedornot.com/",
                    "title": breach["name"],
                    "snippet": f"{email} appears in {breach['name']}" + (f" ({breach['date']})" if breach.get("date") else "") + (f". Data: {breach['detail']}" if breach.get("detail") else "") + ". A breach cannot be deleted. Change the password.",
                    "evidence": {"email": True, "breach": breach["name"]},
                    "fingerprint": f"breach:{email.lower()}:{breach['name'].lower()}",
                }
                change = db.record_sighting(profile_id, finding, utcnow())
                remember_change(profile_id, change, finding)
                db.add_event(scan_id, "breach", {"email": email, "status": "exposed", "name": breach["name"], "detail": finding["snippet"]})
        semaphore = asyncio.Semaphore(4)

        async def probe(broker: dict) -> None:
            assert http_client
            async with semaphore:
                url = fill_search_url(broker.get("search_url") or "", profile)
                payload = {"broker_id": broker["id"], "name": broker["name"], "url": url or "", "category": broker.get("category")}
                if not url:
                    payload.update({"status": "skipped", "detail": "Not enough identifiers to build a search link."})
                    db.add_event(scan_id, "probe", payload)
                    return
                try:
                    response = await http_client.get(url, headers={"User-Agent": UA, "Accept": "text/html"})
                    judged = classify_page(response.status_code, response.text[:350_000], profile, broker.get("not_listed"))
                    final_url = str(response.url)
                except httpx.HTTPError:
                    judged = {
                        "status": "unreachable",
                        "detail": "Could not connect. The site, or this network, refused the check.",
                        "snippet": "",
                        "evidence": {},
                    }
                    final_url = url
                status = judged["status"]
                if status in summary:
                    summary[status] += 1
                summary["checked"] += 1
                finding = {
                    "broker_id": broker["id"],
                    "source": "probe",
                    "status": status,
                    "url": final_url,
                    "title": broker["name"],
                    "snippet": (judged.get("snippet") or "")[:240],
                    "evidence": judged.get("evidence") or {},
                    "fingerprint": f"probe:{broker['id']}",
                    "detail": judged.get("detail") or "",
                }
                change = db.record_sighting(profile_id, finding, utcnow())
                remember_change(profile_id, change, finding)
                payload.update({"status": status, "detail": judged.get("detail") or "", "url": final_url})
                db.add_event(scan_id, "probe", payload)
                await asyncio.sleep(0.15)

        if brokers:
            await asyncio.gather(*(probe(broker) for broker in brokers))
        for query in queries_for(profile):
            results, error = await search_web(query)
            if error:
                db.add_event(scan_id, "web", {"query": query, "status": "unreachable", "detail": error})
                summary["unreachable"] += 1
                continue
            db.add_event(scan_id, "web", {"query": query, "status": "done", "count": len(results)})
            for result in results:
                host = urlparse(result["url"]).netloc
                broker = catalog.match_host(host)
                text = f"{result.get('title') or ''} {result.get('snippet') or ''}"
                hit = corroborate(text, profile)
                if hit["level"] == "none":
                    continue
                status = "exposed" if hit["level"] == "strong" else "possible"
                summary["web"] += 1
                summary[status] += 1
                broker_id = broker["id"] if broker else None
                finding = {
                    "broker_id": broker_id,
                    "source": "web",
                    "status": status,
                    "url": result["url"],
                    "title": result.get("title") or host,
                    "snippet": (result.get("snippet") or text)[:240],
                    "evidence": hit["evidence"],
                    "fingerprint": f"probe:{broker_id}" if broker_id else f"web:{result['url']}",
                }
                change = db.record_sighting(profile_id, finding, utcnow())
                remember_change(profile_id, change, finding)
                db.add_event(
                    scan_id,
                    "web_hit",
                    {
                        "broker_id": broker_id,
                        "name": broker["name"] if broker else host,
                        "status": status,
                        "url": result["url"],
                        "detail": hit["why"],
                    },
                )
        checked = summary["checked"] or 1
        summary["network"] = "limited" if summary["unreachable"] >= max(3, int(checked * 0.7)) else "ok"
        sightings = db.list_sightings(profile_id)
        score = exposure_score(sightings)
        cover = coverage(db.list_removals(profile_id), len(catalog.active()))
        db.finish_scan(scan_id, "done", utcnow(), score, cover, summary)
        db.add_event(scan_id, "done", {"score": score, "coverage": cover, **summary})
    except Exception as exc:  # noqa: BLE001
        db.finish_scan(scan_id, "failed", utcnow(), 0, 0, summary, str(exc)[:300])
        db.add_event(scan_id, "error", {"detail": "The scan stopped early. What finished is saved."})
    finally:
        scan_tasks.pop(profile_id, None)


async def monitor_loop() -> None:
    while True:
        await asyncio.sleep(45)
        try:
            for row in db.due_monitors(utcnow()):
                profile = db.get_profile(row["profile_id"])
                if not profile or profile["sample"]:
                    nxt = (datetime.now(timezone.utc) + timedelta(hours=row["interval_hours"])).replace(microsecond=0).isoformat()
                    db.set_monitor(row["profile_id"], True, row["interval_hours"], nxt, utcnow())
                    continue
                if profile["id"] in scan_tasks:
                    continue
                scan_id = db.create_scan(profile["id"], "monitor", utcnow())
                scan_tasks[profile["id"]] = asyncio.create_task(execute_scan(scan_id, profile["id"], "monitor"))
                nxt = (datetime.now(timezone.utc) + timedelta(hours=row["interval_hours"])).replace(microsecond=0).isoformat()
                db.set_monitor(profile["id"], True, row["interval_hours"], nxt, utcnow())
                db.add_alert(
                    profile["id"],
                    "watch",
                    "Watch started a recheck",
                    "Looking again at pages that had you, pages that blocked the last check, and your email.",
                    utcnow(),
                )
        except Exception:
            continue


def email_batches(profile: dict, only_open: bool = True) -> dict:
    letter = build_letter(profile, None, "deletion")
    removals = {r["broker_id"]: r for r in db.list_removals(profile["id"])}
    grouped: dict[str, list[dict]] = {}
    for broker in catalog.active():
        email = (broker.get("email") or "").strip().lower()
        if not email or "@" not in email:
            continue
        removal = removals.get(broker["id"])
        if only_open and removal and removal["status"] in {"confirmed", "skipped", "submitted"}:
            continue
        grouped.setdefault(email, []).append({"id": broker["id"], "name": broker["name"], "category": broker["category"]})
    addresses = [{"email": email, "brokers": brokers} for email, brokers in sorted(grouped.items())]
    batches = []
    for index, chunk in enumerate(chunked(addresses, 25)):
        batches.append(
            {
                "index": index,
                "addresses": [item["email"] for item in chunk],
                "brokers": [b for item in chunk for b in item["brokers"]],
            }
        )
    return {"subject": letter["subject"], "body": letter["body"], "days": letter["days"], "batches": batches}


@app.get("/robots.txt")
def robots() -> PlainTextResponse:
    return PlainTextResponse("User-agent: *\nDisallow: /\n")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": __version__}


@app.get("/api/meta")
def meta() -> dict:
    return {
        "version": __version__,
        "stats": catalog.stats(),
        "laws": sorted(LAWS.keys()),
        "states": US_STATES,
        "complaints": COMPLAINTS,
        "disclaimer": catalog.disclaimer,
        "source_url": catalog.source_url,
        "hibp": bool(db.setting("hibp_api_key")),
    }


@app.get("/api/profiles")
def list_profiles() -> list[dict]:
    return db.list_profiles()


@app.post("/api/profiles")
def create_profile(body: dict) -> dict:
    data = clean_profile(body)
    data["sample"] = False
    return db.insert_profile(data, utcnow())


@app.post("/api/profiles/sample")
def create_sample() -> dict:
    return install_sample(db)


@app.get("/api/profiles/{profile_id}")
def get_profile(profile_id: int) -> dict:
    return require_profile(profile_id)


@app.put("/api/profiles/{profile_id}")
def update_profile(profile_id: int, body: dict) -> dict:
    current = require_profile(profile_id)
    if current["sample"]:
        raise HTTPException(400, "The sample dossier is fixed. Open your own to edit details.")
    data = clean_profile(body)
    data["flags"] = {**(current.get("flags") or {}), **(data.get("flags") or {})}
    updated = db.update_profile(profile_id, data, utcnow())
    return updated


@app.post("/api/profiles/{profile_id}/flags")
def update_flags(profile_id: int, body: dict) -> dict:
    profile = require_profile(profile_id)
    flags = dict(profile.get("flags") or {})
    incoming = body.get("flags") if isinstance(body, dict) else None
    if not isinstance(incoming, dict):
        raise HTTPException(400, "Send flags.")
    flags.update(incoming)
    return db.update_profile(profile_id, {"flags": flags, "label": profile["label"], "first_name": profile["first_name"], "last_name": profile["last_name"]}, utcnow())


@app.delete("/api/profiles/{profile_id}")
def delete_profile(profile_id: int) -> dict:
    require_profile(profile_id)
    db.delete_profile(profile_id)
    return {"ok": True}


@app.get("/api/profiles/{profile_id}/desk")
def desk(profile_id: int) -> dict:
    return desk_payload(require_profile(profile_id))


@app.get("/api/profiles/{profile_id}/export")
def export_profile(profile_id: int) -> dict:
    profile = require_profile(profile_id)
    payload = desk_payload(profile)
    payload["exported_at"] = utcnow()
    payload["kind"] = "leavemealone-dossier"
    return payload


@app.post("/api/profiles/import")
def import_profile(body: dict) -> dict:
    if not isinstance(body, dict):
        raise HTTPException(400, "Send an exported dossier.")
    raw = body.get("profile") if "profile" in body else body
    raw = dict(raw)
    raw["authorized"] = True
    raw["sample"] = False
    data = clean_profile(raw)
    data["sample"] = False
    return db.insert_profile(data, utcnow())


@app.get("/api/brokers")
def list_brokers(q: str = "", category: str = "", priority: int | None = None) -> dict:
    rows = catalog.list(q=q, category=category, priority=priority)
    return {"brokers": rows, "count": len(rows)}


@app.get("/api/brokers/{broker_id}")
def broker_detail(broker_id: str, profile_id: int | None = None) -> dict:
    broker = catalog.get(broker_id)
    if not broker:
        raise HTTPException(404, "That broker is not in the directory.")
    payload = dict(broker)
    cluster = catalog.cluster_by_id.get(broker.get("cluster_id") or "")
    if cluster:
        payload["cluster"] = {
            "id": cluster["id"],
            "name": cluster["name"],
            "note": cluster["note"],
            "optout_url": cluster.get("optout_url"),
            "members": [
                {"id": member, "name": broker_name(member)}
                for member in cluster.get("members") or []
            ],
        }
    if profile_id:
        profile = db.get_profile(profile_id)
        if profile and broker.get("search_url"):
            payload["filled_search_url"] = fill_search_url(broker["search_url"], profile)
    return payload


@app.post("/api/profiles/{profile_id}/scans")
async def start_scan(profile_id: int, body: dict | None = None) -> dict:
    profile = require_profile(profile_id)
    if profile["sample"]:
        raise HTTPException(400, "The sample dossier does not call out to the web. Open your own dossier to scan.")
    if profile_id in scan_tasks and not scan_tasks[profile_id].done():
        running = db.running_scan(profile_id)
        if running:
            return {"id": running["id"], "status": "running", "scope": running["scope"], "already": True}
    scope = ((body or {}).get("scope") or "priority").strip()
    if scope not in {"priority", "deep", "monitor"}:
        raise HTTPException(400, "Scope must be priority, deep, or monitor.")
    scan_id = db.create_scan(profile_id, scope, utcnow())
    scan_tasks[profile_id] = asyncio.create_task(execute_scan(scan_id, profile_id, scope))
    return {"id": scan_id, "status": "running", "scope": scope}


@app.get("/api/scans/{scan_id}")
def get_scan(scan_id: int, after: int = 0) -> dict:
    scan = db.get_scan(scan_id)
    if not scan:
        raise HTTPException(404, "No scan with that id.")
    return {
        "id": scan["id"],
        "profile_id": scan["profile_id"],
        "scope": scan["scope"],
        "status": scan["status"],
        "started_at": scan["started_at"],
        "finished_at": scan["finished_at"],
        "exposure_score": scan["exposure_score"],
        "summary": scan.get("summary_json"),
        "error": scan.get("error"),
        "events": db.scan_events(scan_id, after),
    }


@app.post("/api/profiles/{profile_id}/sightings")
def add_sighting(profile_id: int, body: dict) -> dict:
    require_profile(profile_id)
    url = str((body or {}).get("url") or "").strip()
    if not url.startswith("http"):
        raise HTTPException(400, "Paste a full http(s) listing URL.")
    host = urlparse(url).netloc
    broker = catalog.match_host(host)
    status = (body or {}).get("status") or "exposed"
    if status not in {"exposed", "possible", "clear"}:
        status = "exposed"
    note = str((body or {}).get("note") or "").strip()[:300]
    finding = {
        "broker_id": broker["id"] if broker else None,
        "source": "manual",
        "status": status,
        "url": url[:500],
        "title": broker["name"] if broker else host,
        "snippet": note or "You recorded this listing yourself.",
        "evidence": {"manual": True},
        "fingerprint": f"manual:{url[:180]}",
    }
    change = db.record_sighting(profile_id, finding, utcnow())
    remember_change(profile_id, change, finding)
    return {"ok": True, "broker_id": finding["broker_id"]}


@app.post("/api/sightings/{sighting_id}")
def set_sighting(sighting_id: int, body: dict) -> dict:
    row = db.get_sighting(sighting_id)
    if not row:
        raise HTTPException(404, "No sighting with that id.")
    status = (body or {}).get("user_status")
    if status not in {None, "", "exposed", "clear", "ignore", "possible"}:
        raise HTTPException(400, "Status must be exposed, possible, clear, or ignore.")
    updated = db.set_sighting_status(sighting_id, status or None, utcnow())
    return decorate_sighting(updated)


@app.post("/api/profiles/{profile_id}/wipe")
def wipe(profile_id: int, body: dict | None = None) -> dict:
    profile = require_profile(profile_id)
    scope = ((body or {}).get("scope") or "all").strip()
    if scope == "visible":
        ids = set()
        for sighting in db.list_sightings(profile_id):
            if sighting.get("broker_id") and effective_status(sighting) in {"exposed", "possible", "blocked"}:
                ids.add(sighting["broker_id"])
        for broker in catalog.active():
            if broker.get("priority") == 1:
                ids.add(broker["id"])
    else:
        ids = {b["id"] for b in catalog.active()}
    for broker_id in ids:
        db.ensure_removal(profile_id, broker_id)
    return {"queued": len(ids), "scope": scope, "name": full_name(profile)}


@app.get("/api/profiles/{profile_id}/letters")
def letters(profile_id: int, broker_id: str = "", kind: str = "deletion") -> dict:
    profile = require_profile(profile_id)
    if kind not in {"deletion", "followup", "escalation", "blanket"}:
        raise HTTPException(400, "Unknown letter type.")
    broker = catalog.get(broker_id) if broker_id and kind != "blanket" else None
    if broker_id and kind != "blanket" and not broker:
        raise HTTPException(404, "That broker is not in the directory.")
    removal = db.removal_for_broker(profile_id, broker_id) if broker_id else None
    letter = build_letter(profile, None if kind == "blanket" else broker, "deletion" if kind == "blanket" else kind, removal)
    return letter


@app.get("/api/profiles/{profile_id}/batches")
def batches(profile_id: int) -> dict:
    profile = require_profile(profile_id)
    return email_batches(profile, only_open=True)


@app.post("/api/profiles/{profile_id}/removals/bulk")
def bulk_removals(profile_id: int, body: dict) -> dict:
    profile = require_profile(profile_id)
    ids = body.get("broker_ids") if isinstance(body, dict) else None
    status = (body or {}).get("status") or "submitted"
    if status not in {"queued", "submitted", "confirmed", "skipped", "reappeared"}:
        raise HTTPException(400, "Unknown status.")
    if not isinstance(ids, list) or not ids:
        raise HTTPException(400, "Send broker ids.")
    if len(ids) > 250:
        raise HTTPException(400, "Mark at most 250 at a time.")
    method = (body or {}).get("method") or "email"
    when = utcnow()
    due = deadline_from(profile)
    updated = 0
    for broker_id in ids:
        if not catalog.get(str(broker_id)):
            continue
        row = db.ensure_removal(profile_id, str(broker_id))
        fields = {"status": status, "method": method}
        if status == "submitted":
            fields["submitted_at"] = when
            fields["deadline_at"] = due
        if status == "confirmed":
            fields["confirmed_at"] = when
        db.update_removal(row["id"], fields)
        updated += 1
    return {"updated": updated, "deadline": due if status == "submitted" else None}


@app.post("/api/removals/{removal_id}")
def update_removal(removal_id: int, body: dict) -> dict:
    row = db.get_removal(removal_id)
    if not row:
        raise HTTPException(404, "No removal with that id.")
    profile = require_profile(row["profile_id"])
    status = (body or {}).get("status") or row["status"]
    if status not in {"queued", "submitted", "confirmed", "skipped", "reappeared"}:
        raise HTTPException(400, "Unknown status.")
    fields = {
        "status": status,
        "method": (body or {}).get("method", row.get("method")),
        "listing_url": (body or {}).get("listing_url", row.get("listing_url")),
        "notes": (body or {}).get("notes", row.get("notes")),
        "submitted_at": row.get("submitted_at"),
        "deadline_at": row.get("deadline_at"),
        "confirmed_at": row.get("confirmed_at"),
    }
    if status == "submitted" and not fields["submitted_at"]:
        fields["submitted_at"] = utcnow()
        fields["deadline_at"] = deadline_from(profile, broker=catalog.get(row["broker_id"]))
    if status == "confirmed":
        fields["confirmed_at"] = utcnow()
    updated = db.update_removal(removal_id, fields)
    return decorate_removal(updated)


@app.get("/api/profiles/{profile_id}/packet", response_class=HTMLResponse)
def packet(profile_id: int) -> HTMLResponse:
    profile = require_profile(profile_id)
    return HTMLResponse(render_packet(profile, db.list_removals(profile_id), catalog))


@app.get("/api/profiles/{profile_id}/drafts.zip")
def drafts(profile_id: int, batch: int = 0) -> Response:
    profile = require_profile(profile_id)
    packed = email_batches(profile, only_open=True)
    if not packed["batches"]:
        raise HTTPException(400, "No open email brokers. The wide net is already marked sent, or none publish an email.")
    if batch < 0 or batch >= len(packed["batches"]):
        raise HTTPException(400, "That batch is out of range.")
    chosen = packed["batches"][batch]
    buffer = io.BytesIO()
    sender = (profile.get("emails") or ["me@example.com"])[0]
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        seen = set()
        for broker_info in chosen["brokers"]:
            broker = catalog.get(broker_info["id"])
            if not broker or not broker.get("email"):
                continue
            key = broker["email"].lower()
            if key in seen:
                continue
            seen.add(key)
            letter = build_letter(profile, broker, "deletion")
            message = EmailMessage()
            message["To"] = broker["email"]
            message["From"] = sender
            message["Subject"] = letter["subject"]
            message["X-Unsent"] = "1"
            message.set_content(letter["body"])
            filename = re.sub(r"[^a-z0-9]+", "-", broker["id"]).strip("-") + ".eml"
            archive.writestr(filename, message.as_string())
    if not seen:
        raise HTTPException(400, "Nothing to draft in that batch.")
    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=leavemealone-drafts-{batch + 1}.zip"},
    )


@app.get("/api/profiles/{profile_id}/monitor")
def get_monitor(profile_id: int) -> dict:
    require_profile(profile_id)
    return db.get_monitor(profile_id)


@app.put("/api/profiles/{profile_id}/monitor")
def set_monitor(profile_id: int, body: dict) -> dict:
    profile = require_profile(profile_id)
    enabled = bool((body or {}).get("enabled"))
    try:
        hours = int((body or {}).get("interval_hours") or 24)
    except (TypeError, ValueError):
        hours = 24
    hours = min(24 * 30, max(6, hours))
    if profile["sample"] and enabled:
        raise HTTPException(400, "Watch runs against the live web. Open your own dossier to turn it on.")
    nxt = None
    if enabled:
        nxt = (datetime.now(timezone.utc) + timedelta(hours=hours)).replace(microsecond=0).isoformat()
    return db.set_monitor(profile_id, enabled, hours, nxt)


@app.post("/api/profiles/{profile_id}/monitor/run")
async def run_monitor(profile_id: int) -> dict:
    require_profile(profile_id)
    return await start_scan(profile_id, {"scope": "monitor"})


@app.get("/api/profiles/{profile_id}/alerts")
def alerts(profile_id: int) -> dict:
    require_profile(profile_id)
    note_overdue(profile_id)
    return {"alerts": db.list_alerts(profile_id), "unread": db.unread_count(profile_id)}


@app.post("/api/alerts/{alert_id}/read")
def read_alert(alert_id: int) -> dict:
    db.read_alert(alert_id)
    return {"ok": True}


@app.post("/api/profiles/{profile_id}/alerts/read")
def read_alerts(profile_id: int) -> dict:
    require_profile(profile_id)
    db.read_all_alerts(profile_id)
    return {"ok": True}


@app.post("/api/password-range")
async def password_range(body: dict) -> dict:
    prefix = str((body or {}).get("prefix") or "").strip().upper()
    if not re.match(r"^[0-9A-F]{5}$", prefix):
        raise HTTPException(400, "Send the first 5 characters of the SHA-1 hash. Never send the password.")
    if not http_client:
        raise HTTPException(503, "The checker is not ready.")
    try:
        response = await http_client.get(
            f"https://api.pwnedpasswords.com/range/{prefix}",
            headers={"Add-Padding": "true", "User-Agent": "LeaveMeAlone"},
        )
        response.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(502, "The password range service did not answer. Nothing was stored.")
    return PlainTextResponse(response.text)


@app.post("/api/settings/hibp")
def set_hibp(body: dict) -> dict:
    key = str((body or {}).get("api_key") or "").strip()
    if key and len(key) < 8:
        raise HTTPException(400, "That key looks too short.")
    db.set_setting("hibp_api_key", key)
    return {"saved": bool(key)}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
