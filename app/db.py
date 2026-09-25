"""Local SQLite. The dossier never leaves this machine unless a scan you start calls out."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from app.scoring import should_replace, transition

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "leavemealone.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
  id INTEGER PRIMARY KEY,
  label TEXT NOT NULL,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  middle_name TEXT DEFAULT '',
  aliases_json TEXT DEFAULT '[]',
  emails_json TEXT DEFAULT '[]',
  phones_json TEXT DEFAULT '[]',
  addresses_json TEXT DEFAULT '[]',
  residence_state TEXT DEFAULT '',
  country TEXT DEFAULT 'US',
  dob TEXT,
  include_dob INTEGER DEFAULT 0,
  scan_phone INTEGER DEFAULT 0,
  sample INTEGER DEFAULT 0,
  flags_json TEXT DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scans (
  id INTEGER PRIMARY KEY,
  profile_id INTEGER NOT NULL,
  scope TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  exposure_score INTEGER,
  coverage INTEGER,
  summary_json TEXT DEFAULT '{}',
  error TEXT,
  FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS scan_events (
  id INTEGER PRIMARY KEY,
  scan_id INTEGER NOT NULL,
  seq INTEGER NOT NULL,
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  FOREIGN KEY(scan_id) REFERENCES scans(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS sightings (
  id INTEGER PRIMARY KEY,
  profile_id INTEGER NOT NULL,
  broker_id TEXT,
  source TEXT NOT NULL,
  status TEXT NOT NULL,
  url TEXT,
  title TEXT,
  snippet TEXT,
  evidence_json TEXT DEFAULT '{}',
  fingerprint TEXT NOT NULL,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  user_status TEXT,
  FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS sightings_fp ON sightings(profile_id, fingerprint);
CREATE TABLE IF NOT EXISTS removals (
  id INTEGER PRIMARY KEY,
  profile_id INTEGER NOT NULL,
  broker_id TEXT NOT NULL,
  status TEXT NOT NULL,
  method TEXT,
  listing_url TEXT,
  submitted_at TEXT,
  deadline_at TEXT,
  confirmed_at TEXT,
  notes TEXT DEFAULT '',
  FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
  UNIQUE(profile_id, broker_id)
);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY,
  profile_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  broker_id TEXT,
  created_at TEXT NOT NULL,
  read INTEGER DEFAULT 0,
  FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS monitor (
  profile_id INTEGER PRIMARY KEY,
  enabled INTEGER DEFAULT 0,
  interval_hours INTEGER DEFAULT 24,
  last_run TEXT,
  next_run TEXT,
  FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
"""


def _loads(value, fallback):
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


class DB:
    def __init__(self, path: Path | None = None):
        self.path = path or DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    def _one(self, sql, args=()):
        with self._lock:
            row = self.conn.execute(sql, args).fetchone()
            return dict(row) if row else None

    def _all(self, sql, args=()):
        with self._lock:
            return [dict(row) for row in self.conn.execute(sql, args).fetchall()]

    def _write(self, sql, args=()):
        with self._lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur

    def setting(self, key: str, default: str = "") -> str:
        row = self._one("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self._write(
            "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    # --- profiles ---
    def insert_profile(self, data: dict, now: str) -> dict:
        cur = self._write(
            """INSERT INTO profiles
            (label, first_name, last_name, middle_name, aliases_json, emails_json, phones_json,
             addresses_json, residence_state, country, dob, include_dob, scan_phone, sample,
             flags_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["label"],
                data["first_name"],
                data["last_name"],
                data.get("middle_name") or "",
                json.dumps(data.get("aliases") or []),
                json.dumps(data.get("emails") or []),
                json.dumps(data.get("phones") or []),
                json.dumps(data.get("addresses") or []),
                data.get("residence_state") or "",
                data.get("country") or "US",
                data.get("dob") or None,
                1 if data.get("include_dob") else 0,
                1 if data.get("scan_phone") else 0,
                1 if data.get("sample") else 0,
                json.dumps(data.get("flags") or {}),
                now,
                now,
            ),
        )
        self._write(
            "INSERT INTO monitor(profile_id, enabled, interval_hours) VALUES (?, 0, 24)",
            (cur.lastrowid,),
        )
        return self.get_profile(cur.lastrowid)

    def update_profile(self, profile_id: int, data: dict, now: str) -> dict | None:
        current = self.get_profile(profile_id)
        if not current:
            return None
        merged = {**current, **data}
        self._write(
            """UPDATE profiles SET label=?, first_name=?, last_name=?, middle_name=?, aliases_json=?,
               emails_json=?, phones_json=?, addresses_json=?, residence_state=?, country=?, dob=?,
               include_dob=?, scan_phone=?, flags_json=?, updated_at=? WHERE id=?""",
            (
                merged["label"],
                merged["first_name"],
                merged["last_name"],
                merged.get("middle_name") or "",
                json.dumps(merged.get("aliases") or []),
                json.dumps(merged.get("emails") or []),
                json.dumps(merged.get("phones") or []),
                json.dumps(merged.get("addresses") or []),
                merged.get("residence_state") or "",
                merged.get("country") or "US",
                merged.get("dob") or None,
                1 if merged.get("include_dob") else 0,
                1 if merged.get("scan_phone") else 0,
                json.dumps(merged.get("flags") or {}),
                now,
                profile_id,
            ),
        )
        return self.get_profile(profile_id)

    def get_profile(self, profile_id: int) -> dict | None:
        row = self._one("SELECT * FROM profiles WHERE id = ?", (profile_id,))
        return self._profile(row) if row else None

    def list_profiles(self) -> list[dict]:
        return [self._profile(row) for row in self._all("SELECT * FROM profiles ORDER BY id")]

    def delete_profile(self, profile_id: int) -> None:
        self._write("DELETE FROM profiles WHERE id = ?", (profile_id,))

    def _profile(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "label": row["label"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "middle_name": row["middle_name"] or "",
            "aliases": _loads(row["aliases_json"], []),
            "emails": _loads(row["emails_json"], []),
            "phones": _loads(row["phones_json"], []),
            "addresses": _loads(row["addresses_json"], []),
            "residence_state": row["residence_state"] or "",
            "country": row["country"] or "US",
            "dob": row["dob"],
            "include_dob": bool(row["include_dob"]),
            "scan_phone": bool(row["scan_phone"]),
            "sample": bool(row["sample"]),
            "flags": _loads(row["flags_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # --- scans ---
    def create_scan(self, profile_id: int, scope: str, now: str) -> int:
        cur = self._write(
            "INSERT INTO scans(profile_id, scope, status, started_at) VALUES (?, ?, 'running', ?)",
            (profile_id, scope, now),
        )
        return cur.lastrowid

    def add_event(self, scan_id: int, kind: str, payload: dict) -> int:
        with self._lock:
            row = self.conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 AS n FROM scan_events WHERE scan_id = ?", (scan_id,)).fetchone()
            seq = row["n"]
            self.conn.execute(
                "INSERT INTO scan_events(scan_id, seq, kind, payload_json) VALUES (?, ?, ?, ?)",
                (scan_id, seq, kind, json.dumps(payload)),
            )
            self.conn.commit()
            return seq

    def scan_events(self, scan_id: int, after: int = 0) -> list[dict]:
        rows = self._all(
            "SELECT seq, kind, payload_json FROM scan_events WHERE scan_id = ? AND seq > ? ORDER BY seq",
            (scan_id, after),
        )
        return [{"seq": r["seq"], "kind": r["kind"], "payload": _loads(r["payload_json"], {})} for r in rows]

    def get_scan(self, scan_id: int) -> dict | None:
        return self._one("SELECT * FROM scans WHERE id = ?", (scan_id,))

    def finish_scan(self, scan_id: int, status: str, now: str, score: int, coverage: int, summary: dict, error: str = "") -> None:
        self._write(
            """UPDATE scans SET status=?, finished_at=?, exposure_score=?, coverage=?, summary_json=?, error=?
               WHERE id=?""",
            (status, now, score, coverage, json.dumps(summary), error, scan_id),
        )

    def scan_history(self, profile_id: int, limit: int = 12) -> list[dict]:
        rows = self._all(
            """SELECT id, scope, status, started_at, finished_at, exposure_score, coverage, summary_json
               FROM scans WHERE profile_id = ? AND status = 'done' ORDER BY id DESC LIMIT ?""",
            (profile_id, limit),
        )
        for row in rows:
            row["summary"] = _loads(row.pop("summary_json"), {})
        return list(reversed(rows))

    def running_scan(self, profile_id: int) -> dict | None:
        return self._one(
            "SELECT * FROM scans WHERE profile_id = ? AND status = 'running' ORDER BY id DESC LIMIT 1",
            (profile_id,),
        )

    # --- sightings ---
    def list_sightings(self, profile_id: int) -> list[dict]:
        rows = self._all(
            "SELECT * FROM sightings WHERE profile_id = ? ORDER BY last_seen DESC, id DESC",
            (profile_id,),
        )
        return [self._sighting(r) for r in rows]

    def get_sighting(self, sighting_id: int) -> dict | None:
        row = self._one("SELECT * FROM sightings WHERE id = ?", (sighting_id,))
        return self._sighting(row) if row else None

    def _sighting(self, row: dict) -> dict:
        return {
            "id": row["id"],
            "profile_id": row["profile_id"],
            "broker_id": row["broker_id"],
            "source": row["source"],
            "status": row["status"],
            "url": row["url"],
            "title": row["title"],
            "snippet": row["snippet"],
            "evidence": _loads(row["evidence_json"], {}),
            "fingerprint": row["fingerprint"],
            "first_seen": row["first_seen"],
            "last_seen": row["last_seen"],
            "user_status": row["user_status"],
        }

    def record_sighting(self, profile_id: int, finding: dict, now: str) -> dict | None:
        fingerprint = finding["fingerprint"]
        existing = self._one(
            "SELECT * FROM sightings WHERE profile_id = ? AND fingerprint = ?",
            (profile_id, fingerprint),
        )
        evidence = json.dumps(finding.get("evidence") or {})
        if not existing:
            self._write(
                """INSERT INTO sightings
                (profile_id, broker_id, source, status, url, title, snippet, evidence_json, fingerprint, first_seen, last_seen, user_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
                (
                    profile_id,
                    finding.get("broker_id"),
                    finding["source"],
                    finding["status"],
                    finding.get("url"),
                    finding.get("title") or "",
                    finding.get("snippet") or "",
                    evidence,
                    fingerprint,
                    now,
                    now,
                ),
            )
            kind = transition(None, finding["status"])
            return {"kind": kind, "broker_id": finding.get("broker_id"), "status": finding["status"]} if kind else None

        if not should_replace(existing["status"], existing["source"], finding["status"], finding["source"]):
            self._write("UPDATE sightings SET last_seen = ? WHERE id = ?", (now, existing["id"]))
            return None
        previous = existing["user_status"] or existing["status"]
        new_user = existing["user_status"]
        if finding["status"] in {"exposed", "possible", "clear"}:
            new_user = None
        self._write(
            """UPDATE sightings SET broker_id=?, source=?, status=?, url=?, title=?, snippet=?, evidence_json=?,
               last_seen=?, user_status=? WHERE id=?""",
            (
                finding.get("broker_id") or existing["broker_id"],
                finding["source"],
                finding["status"],
                finding.get("url") or existing["url"],
                finding.get("title") or existing["title"],
                finding.get("snippet") if finding.get("snippet") is not None else existing["snippet"],
                evidence,
                now,
                new_user,
                existing["id"],
            ),
        )
        if existing["user_status"] == "ignore":
            return None
        kind = transition(previous, finding["status"])
        if not kind:
            return None
        return {"kind": kind, "broker_id": finding.get("broker_id") or existing["broker_id"], "status": finding["status"]}

    def set_sighting_status(self, sighting_id: int, user_status: str | None, now: str) -> dict | None:
        self._write(
            "UPDATE sightings SET user_status = ?, last_seen = ? WHERE id = ?",
            (user_status, now, sighting_id),
        )
        return self.get_sighting(sighting_id)

    # --- removals ---
    def list_removals(self, profile_id: int) -> list[dict]:
        return self._all("SELECT * FROM removals WHERE profile_id = ? ORDER BY id", (profile_id,))

    def get_removal(self, removal_id: int) -> dict | None:
        return self._one("SELECT * FROM removals WHERE id = ?", (removal_id,))

    def ensure_removal(self, profile_id: int, broker_id: str) -> dict:
        existing = self._one(
            "SELECT * FROM removals WHERE profile_id = ? AND broker_id = ?",
            (profile_id, broker_id),
        )
        if existing:
            return existing
        self._write(
            "INSERT INTO removals(profile_id, broker_id, status, notes) VALUES (?, ?, 'queued', '')",
            (profile_id, broker_id),
        )
        return self._one(
            "SELECT * FROM removals WHERE profile_id = ? AND broker_id = ?",
            (profile_id, broker_id),
        )

    def update_removal(self, removal_id: int, fields: dict) -> dict | None:
        current = self.get_removal(removal_id)
        if not current:
            return None
        merged = {**current, **fields}
        self._write(
            """UPDATE removals SET status=?, method=?, listing_url=?, submitted_at=?, deadline_at=?,
               confirmed_at=?, notes=? WHERE id=?""",
            (
                merged["status"],
                merged.get("method"),
                merged.get("listing_url"),
                merged.get("submitted_at"),
                merged.get("deadline_at"),
                merged.get("confirmed_at"),
                merged.get("notes") or "",
                removal_id,
            ),
        )
        return self.get_removal(removal_id)

    def removal_for_broker(self, profile_id: int, broker_id: str) -> dict | None:
        return self._one(
            "SELECT * FROM removals WHERE profile_id = ? AND broker_id = ?",
            (profile_id, broker_id),
        )

    def mark_reappeared(self, profile_id: int, broker_id: str) -> None:
        self._write(
            """UPDATE removals SET status = 'reappeared'
               WHERE profile_id = ? AND broker_id = ? AND status IN ('submitted', 'confirmed', 'queued')""",
            (profile_id, broker_id),
        )

    # --- alerts ---
    def add_alert(self, profile_id: int, kind: str, title: str, body: str, now: str, broker_id: str | None = None) -> int:
        cur = self._write(
            """INSERT INTO alerts(profile_id, kind, title, body, broker_id, created_at, read)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (profile_id, kind, title, body, broker_id, now),
        )
        return cur.lastrowid

    def list_alerts(self, profile_id: int, limit: int = 80) -> list[dict]:
        return self._all(
            "SELECT * FROM alerts WHERE profile_id = ? ORDER BY id DESC LIMIT ?",
            (profile_id, limit),
        )

    def unread_count(self, profile_id: int) -> int:
        row = self._one("SELECT COUNT(*) AS n FROM alerts WHERE profile_id = ? AND read = 0", (profile_id,))
        return row["n"] if row else 0

    def read_alert(self, alert_id: int) -> None:
        self._write("UPDATE alerts SET read = 1 WHERE id = ?", (alert_id,))

    def read_all_alerts(self, profile_id: int) -> None:
        self._write("UPDATE alerts SET read = 1 WHERE profile_id = ?", (profile_id,))

    def has_recent_alert(self, profile_id: int, kind: str, broker_id: str | None) -> bool:
        row = self._one(
            """SELECT id FROM alerts WHERE profile_id = ? AND kind = ? AND IFNULL(broker_id, '') = IFNULL(?, '')
               ORDER BY id DESC LIMIT 1""",
            (profile_id, kind, broker_id),
        )
        return bool(row)

    # --- monitor ---
    def get_monitor(self, profile_id: int) -> dict:
        row = self._one("SELECT * FROM monitor WHERE profile_id = ?", (profile_id,))
        if not row:
            self._write(
                "INSERT INTO monitor(profile_id, enabled, interval_hours) VALUES (?, 0, 24)",
                (profile_id,),
            )
            row = self._one("SELECT * FROM monitor WHERE profile_id = ?", (profile_id,))
        row["enabled"] = bool(row["enabled"])
        return row

    def set_monitor(self, profile_id: int, enabled: bool, interval_hours: int, next_run: str | None, last_run: str | None = None) -> dict:
        self.get_monitor(profile_id)
        if last_run is None:
            self._write(
                "UPDATE monitor SET enabled=?, interval_hours=?, next_run=? WHERE profile_id=?",
                (1 if enabled else 0, interval_hours, next_run, profile_id),
            )
        else:
            self._write(
                "UPDATE monitor SET enabled=?, interval_hours=?, next_run=?, last_run=? WHERE profile_id=?",
                (1 if enabled else 0, interval_hours, next_run, last_run, profile_id),
            )
        return self.get_monitor(profile_id)

    def due_monitors(self, now: str) -> list[dict]:
        return self._all(
            """SELECT * FROM monitor WHERE enabled = 1 AND next_run IS NOT NULL AND next_run <= ?""",
            (now,),
        )
