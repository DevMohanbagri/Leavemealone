"""Turn the MIT-licensed DataPurge broker registry into LeaveMeAlone's catalog.

The contact data, opt-out URLs, and step notes come from
https://github.com/puurpl/datapurge (MIT). The schema, priority ranking,
cluster grouping, and desk copy are original to LeaveMeAlone.

Usage:
  python scripts/build_catalog.py /path/to/datapurge/brokers
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "brokers.json"

UPSTREAM = {
    "acxiom",
    "epsilon",
    "data-axle",
    "lexisnexis",
    "lexisnexis-risk",
    "corelogic",
    "liveramp",
    "experian",
    "equifax",
    "transunion",
    "the-work-number",
    "oracle-data-cloud",
    "fullcontact",
    "peopledatalabs",
    "zoominfo",
}

HEADLINERS = {
    "spokeo",
    "whitepages",
    "beenverified",
    "truepeoplesearch",
    "fastpeoplesearch",
    "radaris",
    "thatsthem",
    "intelius",
    "truthfinder",
    "instant-checkmate",
    "us-search",
    "mylife",
    "peoplefinders",
    "nuwber",
    "clustrmaps",
    "familytreenow",
    "searchpeoplefree",
    "usphonebook",
    "checkpeople",
    "peekyou",
    "idcrawl",
    "cyberbackgroundchecks",
    "peoplelooker",
}

WHY = {
    "acxiom": "Upstream broker. Files it sells are how smaller people-search sites get your address in the first place.",
    "epsilon": "Major marketing co-op. Opting out here cuts catalog and email lists that feed dozens of mailers.",
    "data-axle": "Formerly Infogroup / InfoUSA. A core source for mailing lists, phone appends, and downstream brokers.",
    "lexisnexis": "Huge aggregator used by insurers, landlords, and people-search products. Slow, but high leverage.",
    "spokeo": "Often the first result when someone searches your name. It republishes, so this one needs a watch.",
    "whitepages": "High Google visibility for name and phone searches. Suppression usually needs the listing URL.",
    "beenverified": "People-search brand with sister sites. One opt-out is reported to cover the related brands.",
    "truepeoplesearch": "Fast to remove, fast to come back. Put it on a short recheck.",
    "fastpeoplesearch": "Ranks for address searches. Removal is a form plus the listing URL.",
    "radaris": "Stubborn, and it operates satellite sites. Remove the main profile, then check the satellites.",
    "intelius": "PeopleConnect network. One suppression covers Intelius, TruthFinder, Instant Checkmate, and US Search.",
    "truthfinder": "Same PeopleConnect suppression as Intelius. Do not file this one separately if you already did.",
    "instant-checkmate": "Same PeopleConnect suppression as Intelius.",
    "us-search": "Same PeopleConnect suppression as Intelius.",
    "mylife": "Reputation-style people search. The privacy request is a form, and they sometimes drag their feet.",
    "clustrmaps": "Maps your name to an address from public records. Easy opt-out, moderate chance it returns.",
    "thatsthem": "People search with a direct opt-out. Worth doing early because the pages rank.",
    "nuwber": "People search. Removal is a short form once you have the listing URL.",
    "corelogic": "Property and consumer data sold into lending and insurance. Email or form, not a public search.",
    "equifax": "Credit bureau. Opt out of prescreened offers, and use their privacy request for marketing data.",
    "experian": "Credit bureau. Separate from people-search sites. Freeze credit separately if that is your goal.",
    "transunion": "Credit bureau. Opt out of prescreened offers and marketing use.",
    "liveramp": "Identity graph used by advertisers to match you across sites. No public people search.",
    "zoominfo": "B2B contact data. If your work email is listed, their privacy form is the path.",
    "peopledatalabs": "Sells identity data to other companies. No consumer search page — request deletion anyway.",
    "familytreenow": "Relative and address listings. Opt-out is on the site and does not need an account.",
    "peoplefinders": "People search and background-style listings. Use their opt-out, not a paid account.",
    "searchpeoplefree": "Public people search. Removal page is straightforward.",
    "usphonebook": "Phone and address listings. Opt-out is a short form.",
    "checkpeople": "People search. Email confirmation is typical.",
    "peekyou": "Aggregates public web mentions of your name. Opt-out is a contact form.",
    "idcrawl": "Name search that pulls social and people-search links. Remove the profile, then watch.",
    "cyberbackgroundchecks": "People search with a removal form. High chance of a relist.",
    "whitepages-premium": "Paid Whitepages product. Suppress the free listing too — they are related, not identical.",
}

ACTION_TEXT = {
    "navigate": "Open the official opt-out page.",
    "input": "Enter the detail the form asks for. Use the copy buttons so you don't retype it.",
    "click": "Continue with the button the page shows.",
    "select": "Choose the matching option.",
    "submit": "Submit the form.",
    "wait_for": "Wait for the page to finish loading.",
    "verify_email": "Open the confirmation email they send and click the link. Check spam.",
    "captcha": "Complete the site's human check yourself. LeaveMeAlone will not bypass it.",
    "upload": "Upload only what they legally require. A utility bill is enough for many. Skip this if the form doesn't ask.",
    "checkbox": "Check the boxes that match the request: delete, and do not sell or share.",
    "confirm": "Confirm the request on the final screen.",
    "copy_url": "Copy the URL of your listing from the address bar.",
    "redirect": "Follow the redirect to the official form.",
    "redirect_notice": "The page may send you somewhere else. Stay on the broker's own domain.",
    "scroll_to_footer": "Scroll to the footer and open the privacy or opt-out link.",
    "select_listing": "Select only the listing that is actually you.",
    "select_reason": "Choose deletion or do-not-sell if they ask for a reason.",
    "search_and_select": "Search your name, then select your listing.",
    "open_app": "Continue in the page they open. Don't install anything you didn't mean to.",
    "sms_verify": "If they text a code, enter it. They should not ask you to pay.",
}


def human_steps(method: dict) -> list[str]:
    steps = []
    for step in method.get("steps") or []:
        if not isinstance(step, dict):
            continue
        action = (step.get("action") or "").strip()
        desc = (step.get("description") or "").strip()
        if action == "captcha":
            desc = ACTION_TEXT["captcha"]
        elif not desc:
            desc = ACTION_TEXT.get(action, "")
        if desc and desc not in steps:
            steps.append(desc)
    if steps:
        return steps
    kind = method.get("type")
    if kind == "email":
        return [
            "Copy the deletion letter.",
            f"Email it to {method.get('email_to') or 'the privacy address'}.",
            "Keep the sent mail. The deadline starts the day you send it.",
        ]
    if kind == "postal":
        return [
            "Print the letter.",
            "Mail it to the postal address. Certified mail is optional but gives you a receipt.",
            "Mark it submitted on the day you mail it.",
        ]
    if kind == "phone":
        return [
            f"Call {method.get('phone_number') or 'the listed number'}.",
            "Ask for deletion and a do-not-sell flag. Note the name of the person you spoke with.",
        ]
    if kind == "web_form":
        return [
            "Open the official opt-out page.",
            "Search your name and open the listing that is you.",
            "Submit the removal. Confirm any email they send.",
            "Come back and mark it submitted.",
        ]
    return ["Use the broker's published privacy request. Do not create a paid account."]


def compact_method(method: dict) -> dict:
    return {
        "type": method.get("type") or "web_form",
        "url": method.get("url") or None,
        "email": method.get("email_to") or None,
        "phone": method.get("phone_number") or None,
        "postal": method.get("postal_address") or None,
        "requires_id": bool(method.get("requires_id")),
        "requires_listing_url": bool(method.get("requires_listing_url")),
        "required_fields": method.get("required_fields") or [],
        "steps": human_steps(method),
        "notes": method.get("notes") or None,
    }


def priority_for(broker_id: str, category: str, scannable: bool) -> int:
    if broker_id in UPSTREAM or broker_id in HEADLINERS:
        return 1
    if category == "people-search" and scannable:
        return 2
    if category in {"people-search", "background-check", "public-records"}:
        return 3
    if category in {"data-aggregator", "marketing-list", "location-tracking", "social-scraper"}:
        return 4
    return 5


def erasable_for(category: str, data_types: list[str]) -> str:
    sticky = {"court-records", "criminal-records", "property-records", "voter-records", "marriage-records"}
    if category in {"public-records", "real-estate"} or sticky.intersection(data_types):
        return "partial"
    return "suppress"


def load_yaml_brokers(folder: Path) -> list[dict]:
    brokers = []
    for path in sorted(folder.rglob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"skip {path.name}: {exc}", file=sys.stderr)
            continue
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        scan = raw.get("scan") or {}
        optout = raw.get("optout") or {}
        legal = raw.get("legal") or {}
        timing = raw.get("timing") or {}
        meta = raw.get("meta") or {}
        methods = [compact_method(m) for m in (optout.get("methods") or []) if isinstance(m, dict)]
        not_listed = []
        for rule in scan.get("detection") or []:
            if isinstance(rule, dict) and rule.get("means") == "not_listed" and rule.get("value"):
                not_listed.append(str(rule["value"]))
        registries = [
            name
            for name, flag in (legal.get("registered_broker") or {}).items()
            if flag
        ]
        data_types = [str(x) for x in (raw.get("data_types") or [])]
        broker_id = str(raw["id"])
        category = str(raw.get("category") or "other")
        scannable = bool(scan.get("scannable")) and bool(scan.get("search_url"))
        primary = next((m for m in methods if m["type"] == "web_form" and m.get("url")), None)
        if primary is None:
            primary = next((m for m in methods if m.get("url") or m.get("email")), methods[0] if methods else None)
        brokers.append(
            {
                "id": broker_id,
                "name": raw.get("name") or broker_id,
                "domain": raw.get("domain") or "",
                "aliases": raw.get("aliases") or [],
                "category": category,
                "data_types": data_types,
                "scannable": scannable,
                "search_url": scan.get("search_url") if scannable else None,
                "scan_reason": None if scannable else (scan.get("reason") or "No public search."),
                "not_listed": not_listed,
                "cloudflare": bool((scan.get("anti_bot") or {}).get("cloudflare")),
                "captcha": bool((scan.get("anti_bot") or {}).get("captcha")),
                "methods": methods,
                "optout_url": (primary or {}).get("url"),
                "email": next((m.get("email") for m in methods if m.get("email")), None),
                "phone": next((m.get("phone") for m in methods if m.get("phone")), None),
                "postal": next((m.get("postal") for m in methods if m.get("postal")), None),
                "requires_listing_url": any(m.get("requires_listing_url") for m in methods),
                "requires_id": any(m.get("requires_id") for m in methods),
                "difficulty": optout.get("difficulty") or "medium",
                "minutes": optout.get("estimated_minutes") or 8,
                "processing_days": optout.get("processing_days") or timing.get("typical_removal_days") or 14,
                "legal_max_days": optout.get("legal_max_days") or 45,
                "notes": optout.get("notes") or meta.get("notes") or "",
                "why": WHY.get(broker_id) or "",
                "ccpa": bool(legal.get("ccpa")),
                "gdpr": bool(legal.get("gdpr")),
                "registries": registries,
                "state_laws": legal.get("state_laws") or [],
                "relisting": timing.get("relisting_likelihood") or "medium",
                "recheck_days": timing.get("recheck_interval_days") or 30,
                "confidence": meta.get("confidence") if meta.get("confidence") is not None else 0.5,
                "last_verified": meta.get("last_verified") or "",
                "defunct": bool(meta.get("defunct")),
                "priority": priority_for(broker_id, category, scannable),
                "erasable": erasable_for(category, data_types),
            }
        )
    return brokers


def assign_clusters(brokers: list[dict]) -> list[dict]:
    by_id = {b["id"]: b for b in brokers}
    clusters = []

    pc_members = [
        b["id"]
        for b in brokers
        if "suppression.peopleconnect.us" in json.dumps(b["methods"]).lower()
        or b["id"] in {"peopleconnect", "intelius", "truthfinder", "instant-checkmate", "us-search", "zabasearch", "classmates"}
    ]
    if pc_members:
        clusters.append(
            {
                "id": "peopleconnect",
                "name": "PeopleConnect",
                "optout_url": "https://suppression.peopleconnect.us/login",
                "members": sorted(set(pc_members)),
                "note": "One suppression covers this network, including Intelius, TruthFinder, Instant Checkmate, and US Search. File it once, then mark the sister sites submitted.",
            }
        )

    bv_members = [i for i in ("beenverified", "peoplelooker", "peoplesmart", "numberguru", "neighborwho", "ownerly") if i in by_id]
    if bv_members:
        clusters.append(
            {
                "id": "beenverified",
                "name": "BeenVerified",
                "optout_url": "https://www.beenverified.com/app/optout/search",
                "members": bv_members,
                "note": "BeenVerified's opt-out is reported to cover PeopleLooker and related brands. If a sister site still shows you, remove that listing too.",
            }
        )

    used = {m for c in clusters for m in c["members"]}
    by_url: dict[str, list[str]] = defaultdict(list)
    for broker in brokers:
        if broker["id"] in used or not broker.get("optout_url"):
            continue
        url = broker["optout_url"].rstrip("/").lower()
        if url.count("/") < 3:
            continue
        by_url[url].append(broker["id"])
    for url, members in sorted(by_url.items()):
        if len(members) < 4:
            continue
        clusters.append(
            {
                "id": "shared-" + members[0],
                "name": f"Shared opt-out ({by_id[members[0]]['name']})",
                "optout_url": by_id[members[0]].get("optout_url"),
                "members": members,
                "note": "These entries publish the same opt-out URL. File it once, then mark the group submitted if the page says the request covers all of them.",
            }
        )

    member_map = {}
    for cluster in clusters:
        for member in cluster["members"]:
            member_map.setdefault(member, cluster["id"])
    for broker in brokers:
        broker["cluster_id"] = member_map.get(broker["id"])
    return clusters


def main() -> None:
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/dp/datapurge-main/brokers")
    if not folder.is_dir():
        raise SystemExit(f"Broker folder not found: {folder}")
    brokers = load_yaml_brokers(folder)
    # Stable, useful order: priority, then name.
    brokers.sort(key=lambda b: (b["priority"], b["name"].lower()))
    clusters = assign_clusters(brokers)
    payload = {
        "source": "Broker contact data and opt-out notes adapted from the DataPurge registry (MIT License, Copyright 2026 DataPurge Contributors).",
        "source_url": "https://github.com/puurpl/datapurge",
        "generated": date.today().isoformat(),
        "disclaimer": "Opt-out pages change. Treat every link as a lead to the broker's own privacy request, not a guarantee. This is not legal advice.",
        "brokers": brokers,
        "clusters": clusters,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    active = [b for b in brokers if not b["defunct"]]
    print(
        f"wrote {OUT} brokers={len(brokers)} active={len(active)} "
        f"scannable={sum(1 for b in active if b['scannable'])} "
        f"emailable={sum(1 for b in active if b['email'])} clusters={len(clusters)} "
        f"bytes={OUT.stat().st_size}"
    )


if __name__ == "__main__":
    main()
