"""A fictional dossier so the desk can be learned without typing a real name."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db import DB


def _iso(moment: datetime) -> str:
    return moment.replace(microsecond=0).isoformat()


def install_sample(db: DB) -> dict:
    for profile in db.list_profiles():
        if profile["sample"]:
            return profile
    now = datetime.now(timezone.utc)
    profile = db.insert_profile(
        {
            "label": "Avery Quinn",
            "first_name": "Avery",
            "last_name": "Quinn",
            "middle_name": "",
            "aliases": [{"first": "A.", "last": "Quinn"}],
            "emails": ["avery.quinn.sample@example.net"],
            "phones": ["5125550148"],
            "addresses": [
                {
                    "street": "1847 Cedar Lane",
                    "city": "Austin",
                    "state": "TX",
                    "zip": "78704",
                    "current": True,
                }
            ],
            "residence_state": "TX",
            "country": "US",
            "dob": None,
            "include_dob": False,
            "scan_phone": False,
            "sample": True,
            "flags": {},
        },
        _iso(now - timedelta(days=46)),
    )
    pid = profile["id"]
    stories = [
        ("spokeo", "exposed", "https://www.spokeo.com/Avery-Quinn/Texas/Austin", "Avery Quinn, 30s, Austin, TX. Relatives and a past address are listed.", 12),
        ("whitepages", "exposed", "https://www.whitepages.com/name/Avery-Quinn/Austin-TX", "Avery Quinn · Austin, TX · (512) 555-0148", 9),
        ("fast-people-search", "exposed", "https://www.fastpeoplesearch.com/name/avery-quinn_austin-tx", "Avery Quinn of Austin, TX. Current address on 1847 Cedar Lane.", 6),
        ("family-tree-now", "possible", "https://www.familytreenow.com/search/genealogy/results?first=Avery&last=Quinn", "Avery Quinn appears in a relative list. City was not on the snippet.", 6),
        ("mylife", "possible", "https://www.mylife.com/avery-quinn", "Avery Quinn — public records overview. Could be a namesake.", 20),
        ("beenverified", "blocked", "https://www.beenverified.com/people/avery-quinn/tx/", "Automated check was stopped by a human check.", 2),
        ("radaris", "blocked", "https://radaris.com/p/Avery/Quinn/", "Automated check was stopped by a human check.", 2),
        ("intelius", "possible", "https://www.intelius.com/people-search/Avery-Quinn/Texas", "Avery Quinn in Texas. Open it to see if the age matches.", 8),
        ("thatsthem", "clear", "https://thatsthem.com/name/Avery-Quinn/Austin-TX", "No results for this name and city.", 4),
        ("clustrmaps", "exposed", "https://clustrmaps.com/persons/Avery-Quinn", "Avery Quinn mapped to an Austin address.", 15),
    ]
    for broker_id, status, url, snippet, days in stories:
        db.record_sighting(
            pid,
            {
                "broker_id": broker_id,
                "source": "probe",
                "status": status,
                "url": url,
                "title": broker_id,
                "snippet": snippet,
                "evidence": {"city": "Austin"} if status == "exposed" else {},
                "fingerprint": f"probe:{broker_id}",
            },
            _iso(now - timedelta(days=days)),
        )
    db.record_sighting(
        pid,
        {
            "broker_id": "truepeoplesearch",
            "source": "probe",
            "status": "clear",
            "url": "https://www.truepeoplesearch.com/results?name=Avery%20Quinn&citystatezip=Austin%20TX",
            "title": "TruePeopleSearch",
            "snippet": "No results",
            "evidence": {},
            "fingerprint": "probe:truepeoplesearch",
        },
        _iso(now - timedelta(days=40)),
    )
    db.record_sighting(
        pid,
        {
            "broker_id": "truepeoplesearch",
            "source": "probe",
            "status": "exposed",
            "url": "https://www.truepeoplesearch.com/results?name=Avery%20Quinn&citystatezip=Austin%20TX",
            "title": "TruePeopleSearch",
            "snippet": "Avery Quinn, Austin, TX — listing republished after a removal.",
            "evidence": {"city": "Austin", "phone": True},
            "fingerprint": "probe:truepeoplesearch",
        },
        _iso(now - timedelta(days=1)),
    )
    db.record_sighting(
        pid,
        {
            "broker_id": None,
            "source": "breach",
            "status": "exposed",
            "url": "https://xposedornot.com/",
            "title": "SampleForum",
            "snippet": "avery.quinn.sample@example.net appeared in a fictional breach called SampleForum. Passwords were in the dump. This is not a real incident.",
            "evidence": {"email": True, "sample": True},
            "fingerprint": "breach:avery.quinn.sample@example.net:SampleForum",
        },
        _iso(now - timedelta(days=30)),
    )

    def removal(broker_id, status, method, submitted_days=None, deadline_days=None, confirmed_days=None, notes=""):
        row = db.ensure_removal(pid, broker_id)
        fields = {"status": status, "method": method, "notes": notes}
        if submitted_days is not None:
            fields["submitted_at"] = _iso(now - timedelta(days=submitted_days))
        if deadline_days is not None:
            fields["deadline_at"] = (now + timedelta(days=deadline_days)).date().isoformat()
        if confirmed_days is not None:
            fields["confirmed_at"] = _iso(now - timedelta(days=confirmed_days))
        db.update_removal(row["id"], fields)

    removal("acxiom", "submitted", "web_form", 18, 27, notes="Filed on the Acxiom opt-out form.")
    removal("epsilon", "submitted", "email", 60, -15, notes="Emailed privacy@epsilon.com. No reply.")
    removal("spokeo", "confirmed", "web_form", 21, 24, 9, "Listing was gone on a manual check.")
    removal("whitepages", "queued", None)
    removal("truepeoplesearch", "reappeared", "web_form", 28, 17, notes="Came back after a removal.")
    removal("intelius", "submitted", "web_form", 11, 34, notes="PeopleConnect suppression. Covers the sister sites.")
    removal("beenverified", "queued", None)
    removal("fast-people-search", "queued", None)
    removal("data-axle", "queued", None)
    removal("lexisnexis", "queued", None)
    removal("clustrmaps", "queued", None)
    removal("radaris", "queued", None)

    db.add_alert(
        pid,
        "reappeared",
        "TruePeopleSearch put Avery back",
        "A listing that had been removed is showing the Austin address and phone again. File it once more, then shorten the watch.",
        _iso(now - timedelta(days=1)),
        "truepeoplesearch",
    )
    db.add_alert(
        pid,
        "breach",
        "Sample breach on the sample email",
        "SampleForum is fictional, here so you can see how a real breach alert looks. A breach cannot be deleted. Change the password and turn on a second factor.",
        _iso(now - timedelta(days=30)),
        None,
    )
    db.add_alert(
        pid,
        "overdue",
        "Epsilon missed the deadline",
        "The request was sent 60 days ago. Deadline was 15 days ago. Write the follow-up, then a complaint draft if they stay silent.",
        _iso(now - timedelta(days=2)),
        "epsilon",
    )

    history = [(40, 78, 4), (24, 61, 11), (10, 44, 18), (1, 76, 22)]
    for days, score, cover in history:
        started = _iso(now - timedelta(days=days, hours=1))
        scan_id = db.create_scan(pid, "priority", started)
        db.finish_scan(
            scan_id,
            "done",
            _iso(now - timedelta(days=days)),
            score,
            cover,
            {"exposed": 4, "possible": 2, "blocked": 2, "sample": True},
        )
    return db.get_profile(pid)
