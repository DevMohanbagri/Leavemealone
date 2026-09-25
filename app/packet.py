"""Printable removal record. The user prints or saves it; nothing is filed for them."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from app.letters import build_letter, full_name, state_name


def render_packet(profile: dict, removals: list[dict], catalog) -> str:
    name = escape(full_name(profile))
    today = datetime.now(timezone.utc).date().isoformat()
    residence = escape(state_name(profile.get("residence_state")) or profile.get("country") or "")
    rows = []
    counts = {"queued": 0, "submitted": 0, "confirmed": 0, "reappeared": 0, "skipped": 0}
    for removal in removals:
        counts[removal["status"]] = counts.get(removal["status"], 0) + 1
        broker = catalog.get(removal["broker_id"])
        broker_name = escape(broker["name"] if broker else removal["broker_id"])
        domain = escape((broker or {}).get("domain") or "")
        rows.append(
            "<tr>"
            f"<td>{broker_name}<div class='sub'>{domain}</div></td>"
            f"<td>{escape(removal['status'])}</td>"
            f"<td>{escape((removal.get('submitted_at') or '')[:10])}</td>"
            f"<td>{escape(removal.get('deadline_at') or '')}</td>"
            f"<td>{escape(removal.get('method') or '')}</td>"
            "</tr>"
        )
    letter = build_letter(profile, None, "deletion")
    body = escape(letter["body"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>LeaveMeAlone removal record — {name}</title>
<style>
  body {{ font: 15px/1.45 Georgia, serif; color: #1c1915; margin: 40px auto; max-width: 820px; }}
  h1 {{ font-weight: 500; font-size: 32px; margin-bottom: 0; }}
  .kicker {{ letter-spacing: .16em; text-transform: uppercase; font: 11px/1 ui-monospace, monospace; color: #8a5a12; }}
  table {{ width: 100%; border-collapse: collapse; margin: 24px 0 40px; font: 13px/1.4 ui-sans-serif, sans-serif; }}
  th, td {{ text-align: left; border-bottom: 1px solid #e4dccb; padding: 8px 6px; vertical-align: top; }}
  th {{ font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: #7a7166; }}
  .sub {{ color: #7a7166; }}
  pre {{ white-space: pre-wrap; font: 13px/1.5 Georgia, serif; background: #f6f1e7; padding: 18px; }}
  .note {{ color: #5c564c; font-size: 13px; }}
  @media print {{ body {{ margin: 0; }} pre {{ background: none; }} }}
</style>
</head>
<body>
<p class="kicker">LeaveMeAlone · removal record · {today}</p>
<h1>{name}</h1>
<p class="note">Residence: {residence}. This is a log of requests you sent or still owe. It is not a court order, not a certificate, and not legal advice. Brokers can put a suppressed record back. Public records held by a court or county recorder are not erased by a broker opt-out.</p>
<p class="note">Queued {counts.get('queued', 0)} · Sent {counts.get('submitted', 0)} · Confirmed {counts.get('confirmed', 0)} · Came back {counts.get('reappeared', 0)} · Skipped {counts.get('skipped', 0)}</p>
<table>
<thead><tr><th>Broker</th><th>Status</th><th>Sent</th><th>Deadline</th><th>How</th></tr></thead>
<tbody>
{''.join(rows) or '<tr><td colspan="5">No requests logged yet.</td></tr>'}
</tbody>
</table>
<p class="kicker">Blanket letter</p>
<pre>{body}</pre>
</body>
</html>"""
