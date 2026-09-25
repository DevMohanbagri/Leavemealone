"""Exposure score, coverage, and the labels shown on the desk."""

from __future__ import annotations

HOT = {"exposed", "possible"}
RANK = {
    "exposed": 5,
    "possible": 4,
    "clear": 3,
    "inconclusive": 2,
    "blocked": 1,
    "unreachable": 0,
    "skipped": 0,
}


def effective_status(sighting: dict) -> str:
    return sighting.get("user_status") or sighting.get("status") or "inconclusive"


def exposure_score(sightings: list[dict]) -> int:
    points = 0
    blocked = 0
    for sighting in sightings:
        status = effective_status(sighting)
        if status in {"clear", "ignore"}:
            continue
        evidence = sighting.get("evidence") or {}
        if sighting.get("source") == "breach" and status == "exposed":
            points += 7
            continue
        if status == "exposed":
            points += 9
            if evidence.get("phone"):
                points += 3
            if evidence.get("address") or evidence.get("city"):
                points += 2
        elif status == "possible":
            points += 3
        elif status == "blocked":
            blocked += 1
    points += min(blocked, 6)
    return max(0, min(100, points))


def exposure_label(score: int) -> str:
    if score <= 0:
        return "Quiet"
    if score < 16:
        return "Thin"
    if score < 36:
        return "Leaking"
    if score < 61:
        return "Exposed"
    return "Wide open"


def coverage(removals: list[dict], universe: int) -> int:
    if not universe:
        return 0
    done = sum(1 for row in removals if row.get("status") in {"submitted", "confirmed"})
    return max(0, min(100, round(100 * done / universe)))


def should_replace(old_status: str, old_source: str, new_status: str, new_source: str) -> bool:
    if old_status == new_status:
        return True
    if (
        old_status == "clear"
        and old_source == "probe"
        and new_source == "web"
        and new_status in HOT
    ):
        return False
    return RANK.get(new_status, 0) >= RANK.get(old_status, 0)


def transition(previous: str | None, new: str) -> str | None:
    if new in HOT and previous in {None, "clear", "inconclusive", "unreachable", "blocked", "skipped"}:
        if previous == "clear":
            return "reappeared"
        if previous is None or previous in {"inconclusive", "unreachable", "blocked", "skipped"}:
            return "new"
    if previous in HOT and new == "clear":
        return "cleared"
    return None
