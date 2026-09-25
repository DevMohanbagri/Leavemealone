"""Broker directory. Contact data is adapted from the DataPurge registry (MIT)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "data" / "brokers.json"

# Product copy and a few search URLs the upstream registry under-specifies.
OVERRIDES = {
    "fast-people-search": {
        "priority": 1,
        "why": "Ranks when someone searches your name plus a city. Removal needs the listing URL, then the form.",
        "search_url": "https://www.fastpeoplesearch.com/name/{first_name}-{last_name}_{city}-{state}",
    },
    "family-tree-now": {
        "priority": 1,
        "why": "Publishes relatives and past addresses. The opt-out is on the site and does not need an account.",
        "search_url": "https://www.familytreenow.com/search/genealogy/results?first={first_name}&last={last_name}&citystatezip={city}%2C%20{state}",
    },
    "cyber-background-checks": {
        "priority": 1,
        "why": "People-search page with a public removal form. These listings tend to come back.",
    },
    "smart-background-checks": {
        "priority": 1,
        "why": "Another high-visibility people search. Pull it with the official opt-out, not a paid report.",
    },
    "advanced-background-checks": {
        "priority": 1,
        "why": "Public people search. Opt out from their removal page, then watch for a relist.",
    },
    "truepeoplesearch": {
        "why": "The removal page is often blocked by their own security service. Email support@truepeoplesearch.com, call 888-838-4803, or mail the letter. Do not try to get around the block.",
        "email": "support@truepeoplesearch.com",
        "phone": "888-838-4803",
        "postal": "TruePeopleSearch.com, PO Box 7775 PMB 29296, San Francisco, CA 94120-7775",
        "notes": "Contacts taken from the TruePeopleSearch privacy notice (updated 2026-03-06) and the about page. contact@ is not the published address. The /removal form sits behind their security wall.",
        "last_verified": "2026-09-25",
    },
    "clustrmaps": {
        "why": "Pins your name to an address from property and other public records. The broker copy can be suppressed; the county record cannot.",
    },
    "radaris": {
        "why": "Slow opt-out, and the brand runs satellite sites. Remove the main profile, then search the satellites by hand.",
    },
}

SUMMARY_FIELDS = (
    "id",
    "name",
    "domain",
    "category",
    "scannable",
    "priority",
    "difficulty",
    "minutes",
    "processing_days",
    "legal_max_days",
    "relisting",
    "recheck_days",
    "erasable",
    "defunct",
    "cluster_id",
    "requires_listing_url",
    "requires_id",
    "optout_url",
    "email",
    "phone",
    "postal",
    "why",
    "ccpa",
    "gdpr",
    "registries",
    "last_verified",
    "confidence",
    "data_types",
    "captcha",
    "cloudflare",
)


def _sync_contacts(broker: dict) -> None:
    """Keep method steps aligned when an override corrects a published address."""
    methods = [dict(method) for method in broker.get("methods") or []]
    email = broker.get("email")
    phone = broker.get("phone")
    postal = broker.get("postal")
    if email:
        email_method = next((method for method in methods if method.get("type") == "email"), None)
        steps = [
            "Copy the deletion letter. LeaveMeAlone does not send it.",
            f"Email it from your own mailbox to {email}.",
            "If the page says you have been blocked, stop. Do not try to get around that wall. This email is the request.",
            "Keep the sent mail. The deadline starts the day you send it.",
        ]
        if email_method:
            email_method["email"] = email
            email_method["steps"] = steps
        else:
            methods.append({"type": "email", "url": None, "email": email, "phone": None, "postal": None, "requires_id": False, "requires_listing_url": False, "required_fields": ["full_name", "email"], "steps": steps, "notes": None})
    if phone and not any(method.get("type") == "phone" for method in methods):
        methods.append({
            "type": "phone",
            "url": None,
            "email": None,
            "phone": phone,
            "postal": None,
            "requires_id": False,
            "requires_listing_url": False,
            "required_fields": ["full_name"],
            "steps": [
                f"Call {phone}.",
                "Ask them to delete the listing and stop selling it. Write down the name of the person you spoke with.",
            ],
            "notes": None,
        })
    if postal and not any(method.get("type") == "postal" for method in methods):
        methods.append({
            "type": "postal",
            "url": None,
            "email": None,
            "phone": None,
            "postal": postal,
            "requires_id": False,
            "requires_listing_url": False,
            "required_fields": ["full_name"],
            "steps": [
                "Print the same deletion letter.",
                f"Mail it to {postal}.",
                "Mark it sent on the day it goes in the box.",
            ],
            "notes": None,
        })
    broker["methods"] = methods


def _norm_host(value: str) -> str:
    host = (value or "").strip().lower()
    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.split("/")[0].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


class Catalog:
    def __init__(self, payload: dict):
        self.source = payload.get("source", "")
        self.source_url = payload.get("source_url", "")
        self.generated = payload.get("generated", "")
        self.disclaimer = payload.get("disclaimer", "")
        self.brokers = []
        for raw in payload.get("brokers") or []:
            broker = dict(raw)
            extra = OVERRIDES.get(broker["id"])
            if extra:
                broker.update(extra)
                if any(key in extra for key in ("email", "phone", "postal")):
                    _sync_contacts(broker)
            self.brokers.append(broker)
        self.by_id = {b["id"]: b for b in self.brokers}
        self.clusters = payload.get("clusters") or []
        self.cluster_by_id = {c["id"]: c for c in self.clusters}
        self.by_domain: dict[str, dict] = {}
        for broker in self.brokers:
            host = _norm_host(broker.get("domain") or "")
            if host:
                self.by_domain[host] = broker
            for alias in broker.get("aliases") or []:
                if "." in str(alias):
                    self.by_domain[_norm_host(str(alias))] = broker

    def get(self, broker_id: str) -> dict | None:
        return self.by_id.get(broker_id)

    def summary(self, broker: dict) -> dict:
        return {key: broker.get(key) for key in SUMMARY_FIELDS}

    def list(self, q: str = "", category: str = "", priority: int | None = None, include_defunct: bool = False) -> list[dict]:
        needle = (q or "").strip().lower()
        rows = []
        for broker in self.brokers:
            if broker.get("defunct") and not include_defunct:
                continue
            if category and broker.get("category") != category:
                continue
            if priority is not None and broker.get("priority") != priority:
                continue
            if needle:
                hay = " ".join(
                    [
                        broker.get("name") or "",
                        broker.get("domain") or "",
                        broker.get("id") or "",
                        " ".join(broker.get("aliases") or []),
                        broker.get("category") or "",
                    ]
                ).lower()
                if needle not in hay:
                    continue
            rows.append(self.summary(broker))
        return rows

    def active(self) -> list[dict]:
        return [b for b in self.brokers if not b.get("defunct")]

    def match_host(self, host: str) -> dict | None:
        host = _norm_host(host)
        if not host:
            return None
        if host in self.by_domain:
            return self.by_domain[host]
        parts = host.split(".")
        while len(parts) > 2:
            parts = parts[1:]
            candidate = ".".join(parts)
            if candidate in self.by_domain:
                return self.by_domain[candidate]
        return None

    def stats(self) -> dict:
        active = self.active()
        categories: dict[str, int] = {}
        for broker in active:
            categories[broker["category"]] = categories.get(broker["category"], 0) + 1
        return {
            "brokers": len(self.brokers),
            "active": len(active),
            "scannable": sum(1 for b in active if b.get("scannable")),
            "emailable": sum(1 for b in active if b.get("email")),
            "people_search": categories.get("people-search", 0),
            "priority": sum(1 for b in active if b.get("priority") == 1),
            "categories": categories,
            "clusters": len(self.clusters),
            "source_url": self.source_url,
            "generated": self.generated,
            "disclaimer": self.disclaimer,
        }


@lru_cache(maxsize=1)
def load_catalog() -> Catalog:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return Catalog(payload)
