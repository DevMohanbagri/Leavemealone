"""Country, region, and city names. Suggestions only — a typed place is always kept."""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACES_PATH = ROOT / "data" / "places.json"
CITIES_PATH = ROOT / "data" / "cities.json"

# Names people type that are not the official label in the place file.
ALIASES = {
    "usa": "US",
    "u.s.": "US",
    "u.s.a.": "US",
    "united states of america": "US",
    "uk": "GB",
    "u.k.": "GB",
    "britain": "GB",
    "great britain": "GB",
    "uae": "AE",
    "holland": "NL",
    "czechia": "CZ",
    "republic of korea": "KR",
    "korea": "KR",
}


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFD", value or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return " ".join(text.lower().split())


@lru_cache(maxsize=1)
def load_places() -> dict:
    payload = json.loads(PLACES_PATH.read_text(encoding="utf-8"))
    countries = payload.get("countries") or []
    by_code = {c["code"]: c for c in countries}
    by_fold: dict[str, str] = {}
    for country in countries:
        by_fold[_fold(country["code"])] = country["code"]
        by_fold[_fold(country["name"])] = country["code"]
        if country.get("iso3"):
            by_fold[_fold(country["iso3"])] = country["code"]
    for alias, code in ALIASES.items():
        by_fold[_fold(alias)] = code
    return {"countries": countries, "by_code": by_code, "by_fold": by_fold, "source": payload.get("source", ""), "license": payload.get("license", "")}


@lru_cache(maxsize=1)
def _city_index() -> dict[str, list[tuple[str, str]]]:
    raw = json.loads(CITIES_PATH.read_text(encoding="utf-8"))
    index = {}
    for code, names in raw.items():
        index[code] = [(_fold(name), name) for name in names]
    return index


def countries() -> list[dict]:
    return [{"code": c["code"], "name": c["name"], "regions": c.get("regions") or []} for c in load_places()["countries"]]


def normalize_country(value: str | None) -> str:
    raw = " ".join((value or "").split())
    if not raw:
        return ""
    code = load_places()["by_fold"].get(_fold(raw))
    if code:
        return code
    return raw[:56]


def country_name(value: str | None) -> str:
    code = normalize_country(value)
    country = load_places()["by_code"].get(code)
    if country:
        return country["name"]
    return " ".join((value or "").split())


def clean_region(value: str | None, country: str | None = "") -> str:
    from app.letters import US_STATES, normalize_state

    raw = " ".join((value or "").split())
    if not raw:
        return ""
    code = normalize_country(country)
    if code == "US" or (not code and normalize_state(raw) in US_STATES):
        state = normalize_state(raw)
        if state in US_STATES:
            return state
    country_row = load_places()["by_code"].get(code)
    if country_row:
        folded = _fold(raw)
        for region in country_row.get("regions") or []:
            if _fold(region) == folded:
                return region
    return raw[:80]


def clean_city(value: str | None, country: str | None = "") -> str:
    raw = " ".join((value or "").split())
    if not raw:
        return ""
    code = normalize_country(country)
    folded = _fold(raw)
    for key, name in _city_index().get(code, []):
        if key == folded:
            return name
    return raw[:80]


def search_cities(country: str | None, query: str, limit: int = 8) -> list[str]:
    code = normalize_country(country)
    needle = _fold(query)
    if not code or len(needle) < 1:
        return []
    rows = _city_index().get(code, [])
    starts = [name for key, name in rows if key.startswith(needle)]
    if len(starts) >= limit:
        return starts[:limit]
    contains = [name for key, name in rows if needle in key and not key.startswith(needle)]
    return (starts + contains)[:limit]
