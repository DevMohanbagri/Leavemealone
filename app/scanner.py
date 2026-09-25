"""Public-page checks. No captcha bypass, no login bypass, no retries that hide a block."""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from urllib.parse import quote, urlparse, parse_qs, unquote

from app.letters import US_STATES, current_address, normalize_state

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

BLOCK_MARKERS = (
    "just a moment",
    "cf-browser-verification",
    "attention required",
    "verify you are human",
    "verify you are a human",
    "please enable javascript",
    "enable javascript and cookies",
    "pardon our interruption",
    "access denied",
    "request blocked",
    "bot detection",
    "are you a robot",
    "security check",
    "captcha",
    "unusual traffic",
    "complete the security check",
    "ray id",
)

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def digits(value: str) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def phone_keys(value: str) -> list[str]:
    raw = digits(value)
    if len(raw) == 11 and raw.startswith("1"):
        raw = raw[1:]
    keys = []
    if len(raw) >= 10:
        keys.append(raw[-10:])
    if len(raw) >= 7:
        keys.append(raw[-7:])
    return keys


def slug(value: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def fill_search_url(template: str, profile: dict) -> str | None:
    if not template:
        return None
    address = current_address(profile)
    state = normalize_state(address.get("state") or profile.get("residence_state"))
    state_token = US_STATES.get(state, state) if "spokeo.com" in template else state
    values = {
        "first_name": profile.get("first_name") or "",
        "last_name": profile.get("last_name") or "",
        "city": address.get("city") or "",
        "state": state_token or "",
        "zip": address.get("zip") or "",
        "street": address.get("street") or "",
        "email": (profile.get("emails") or [""])[0],
        "phone": digits((profile.get("phones") or [""])[0]) if profile.get("scan_phone") else "",
    }
    if not values["first_name"] or not values["last_name"]:
        return None
    # Never put a date of birth in a search URL.
    path, sep, query = template.partition("?")

    def sub(chunk: str, mode: str) -> str:
        def repl(match: re.Match) -> str:
            val = values.get(match.group(1), "")
            if mode == "path":
                return slug(val)
            return quote(val, safe="")

        return re.sub(r"\{(\w+)\}", repl, chunk)

    url = sub(path, "path")
    if sep:
        url += "?" + sub(query, "query")
    url = re.sub(r"-{2,}", "-", url)
    url = url.replace("/-", "/").replace("-/", "/")
    url = re.sub(r"[?&][a-z_]+=(?=&|$)", "", url)
    return url


def strip_html(html: str) -> str:
    text = TAG_RE.sub(" ", html or "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
    return SPACE_RE.sub(" ", text).strip()


def _name_present(text: str, profile: dict) -> bool:
    low = text.lower()
    first = (profile.get("first_name") or "").strip().lower()
    last = (profile.get("last_name") or "").strip().lower()
    if len(first) < 2 or len(last) < 2:
        return False
    return first in low and last in low


def corroborate(text: str, profile: dict) -> dict:
    low = text.lower()
    name = _name_present(text, profile)
    address = current_address(profile)
    city = (address.get("city") or "").strip().lower()
    city_hit = bool(city) and len(city) >= 3 and city in low
    email_hit = False
    for email in profile.get("emails") or []:
        if email and email.lower() in low:
            email_hit = True
            break
    phone_hit = False
    compact = digits(text)
    for phone in profile.get("phones") or []:
        for key in phone_keys(phone):
            if key and key in compact:
                phone_hit = True
                break
    evidence = {}
    if city_hit:
        evidence["city"] = address.get("city")
    if phone_hit:
        evidence["phone"] = True
    if email_hit:
        evidence["email"] = True
    if name and (city_hit or phone_hit or email_hit):
        bits = []
        if city_hit:
            bits.append("city")
        if phone_hit:
            bits.append("phone")
        if email_hit:
            bits.append("email")
        return {
            "level": "strong",
            "why": "Your name appears with your " + " and ".join(bits) + ".",
            "evidence": evidence,
        }
    if name:
        return {"level": "weak", "why": "Your first and last name appear, without your city, phone, or email.", "evidence": evidence}
    return {"level": "none", "why": "", "evidence": evidence}


def extract_snippet(text: str, profile: dict, width: int = 180) -> str:
    low = text.lower()
    last = (profile.get("last_name") or "").strip().lower()
    idx = low.find(last) if last else -1
    if idx < 0:
        return text[:width].strip()
    start = max(0, idx - 70)
    end = min(len(text), idx + width)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


def classify_page(status_code: int, html: str, profile: dict, not_listed: list[str] | None = None) -> dict:
    text = strip_html(html or "")
    low = text.lower()
    head = low[:1800]
    blocked = status_code in {401, 403, 429, 503} and len(text) < 600
    if any(marker in head for marker in BLOCK_MARKERS) or blocked:
        return {
            "status": "blocked",
            "detail": "The site put up a human check or refused an automated look. Open the link and confirm it yourself.",
            "snippet": "",
            "evidence": {},
        }
    for phrase in not_listed or []:
        if phrase and phrase.lower() in low:
            return {
                "status": "clear",
                "detail": f"The page says “{phrase}”.",
                "snippet": phrase,
                "evidence": {},
            }
    if status_code == 404:
        return {
            "status": "clear",
            "detail": "The search page returned not found.",
            "snippet": "",
            "evidence": {},
        }
    if not text:
        return {
            "status": "unreachable",
            "detail": "The site returned an empty page.",
            "snippet": "",
            "evidence": {},
        }
    hit = corroborate(text, profile)
    snippet = extract_snippet(text, profile) if hit["level"] != "none" else ""
    if hit["level"] == "strong":
        return {"status": "exposed", "detail": hit["why"], "snippet": snippet, "evidence": hit["evidence"]}
    if hit["level"] == "weak":
        return {"status": "possible", "detail": hit["why"], "snippet": snippet, "evidence": hit["evidence"]}
    return {
        "status": "inconclusive",
        "detail": "The page loaded, but your name and a corroborating detail were not both visible.",
        "snippet": "",
        "evidence": {},
    }


class _DDGParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results: list[dict] = []
        self._mode = None
        self._buf: list[str] = []
        self._href = None

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        cls = ad.get("class") or ""
        if tag == "a" and "result__a" in cls:
            self._mode = "title"
            self._href = ad.get("href")
            self._buf = []
        elif tag in {"a", "td", "span"} and "result__snippet" in cls:
            self._mode = "snippet"
            self._buf = []

    def handle_endtag(self, tag):
        if self._mode == "title" and tag == "a":
            self.results.append({"title": "".join(self._buf).strip(), "url": self._href or "", "snippet": ""})
            self._mode = None
        elif self._mode == "snippet" and tag in {"a", "td", "span"}:
            if self.results:
                self.results[-1]["snippet"] = "".join(self._buf).strip()
            self._mode = None

    def handle_data(self, data):
        if self._mode:
            self._buf.append(data)


def unwrap_ddg(url: str) -> str:
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        qs = parse_qs(parsed.query)
        if qs.get("uddg"):
            return unquote(qs["uddg"][0])
    return url


def parse_ddg(html: str) -> list[dict]:
    parser = _DDGParser()
    try:
        parser.feed(html or "")
    except Exception:
        return []
    cleaned = []
    for row in parser.results:
        url = unwrap_ddg(row.get("url") or "")
        if not url.startswith("http"):
            continue
        cleaned.append({"title": row.get("title") or "", "url": url, "snippet": row.get("snippet") or ""})
    return cleaned


def parse_breaches(payload) -> list[dict]:
    if not payload:
        return []
    if isinstance(payload, dict):
        if payload.get("Error") or str(payload.get("status", "")).lower() in {"not found", "no breaches found"}:
            return []
        raw = payload.get("breaches") or payload.get("exposed") or []
    elif isinstance(payload, list):
        raw = payload
    else:
        return []
    found = []
    for item in raw:
        if isinstance(item, str):
            found.append({"name": item, "date": "", "detail": ""})
        elif isinstance(item, (list, tuple)) and item:
            found.append({"name": str(item[0]), "date": str(item[1]) if len(item) > 1 else "", "detail": ""})
        elif isinstance(item, dict):
            name = item.get("Name") or item.get("name") or item.get("breach") or item.get("BreachID") or "Unknown breach"
            date = item.get("BreachDate") or item.get("date") or item.get("breachDate") or ""
            classes = item.get("DataClasses") or item.get("dataClasses") or []
            detail = ", ".join(classes) if isinstance(classes, list) else str(classes or "")
            found.append({"name": str(name), "date": str(date), "detail": detail})
    return found


def password_sha1(password: str) -> str:
    return hashlib.sha1(password.encode("utf-8")).hexdigest().upper()


def queries_for(profile: dict) -> list[str]:
    first = profile.get("first_name") or ""
    last = profile.get("last_name") or ""
    address = current_address(profile)
    city = address.get("city") or ""
    state = normalize_state(address.get("state") or profile.get("residence_state"))
    queries = [f"\"{first} {last}\""]
    if city:
        queries.append(f"\"{first} {last}\" \"{city}\"")
    if state:
        queries.append(f"\"{first} {last}\" {state} (address OR phone OR age)")
    if profile.get("scan_phone"):
        for phone in profile.get("phones") or []:
            pretty = phone_keys(phone)
            if pretty:
                queries.append(pretty[0])
    # Cap so a scan cannot fan out into a research campaign on someone else.
    return queries[:3]
