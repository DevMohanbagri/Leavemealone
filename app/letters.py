"""Deletion letters. Not legal advice — a clear request the user sends themselves."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

US_STATES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "DC": "District of Columbia",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}

# Statute text is included only where the citation is standard. Other states are
# named without a section number rather than risk a wrong cite.
LAWS = {
    "CA": {
        "title": "California Consumer Privacy Act (CCPA/CPRA) and the Delete Act",
        "days": 45,
        "text": (
            "I reside in California. Delete my personal information under Cal. Civ. Code § 1798.105 "
            "and opt me out of the sale and sharing of my personal information under § 1798.120. "
            "If you are a data broker, the Delete Act (Cal. Civ. Code § 1798.99.80 et seq.) requires "
            "you to delete personal information in response to a consumer deletion request and to treat "
            "an unverifiable deletion request as an opt-out of sale and sharing. This letter is that request."
        ),
    },
    "VA": {
        "title": "Virginia Consumer Data Protection Act",
        "days": 45,
        "text": (
            "I reside in Virginia. Under the Virginia Consumer Data Protection Act (Va. Code § 59.1-575 et seq.), "
            "delete my personal data and stop selling it or using it for targeted advertising."
        ),
    },
    "CO": {
        "title": "Colorado Privacy Act",
        "days": 45,
        "text": (
            "I reside in Colorado. Under the Colorado Privacy Act (C.R.S. § 6-1-1301 et seq.), delete my "
            "personal data and opt me out of the sale of my personal data and of targeted advertising."
        ),
    },
    "CT": {
        "title": "Connecticut Data Privacy Act",
        "days": 45,
        "text": (
            "I reside in Connecticut. Under the Connecticut Data Privacy Act (Conn. Gen. Stat. § 42-515 et seq.), "
            "delete my personal data and opt me out of the sale of my personal data and of targeted advertising."
        ),
    },
    "UT": {
        "title": "Utah Consumer Privacy Act",
        "days": 45,
        "text": (
            "I reside in Utah. Under the Utah Consumer Privacy Act (Utah Code § 13-61-101 et seq.), delete my "
            "personal data and opt me out of the sale of my personal data."
        ),
    },
    "TX": {
        "title": "Texas Data Privacy and Security Act",
        "days": 45,
        "text": (
            "I reside in Texas. Under the Texas Data Privacy and Security Act (Tex. Bus. & Com. Code ch. 541), "
            "delete my personal data and opt me out of the sale of my personal data and of targeted advertising."
        ),
    },
    "OR": {
        "title": "Oregon Consumer Privacy Act",
        "days": 45,
        "text": (
            "I reside in Oregon. Under the Oregon Consumer Privacy Act (ORS 646A.570 et seq.), delete my "
            "personal data and opt me out of the sale of my personal data and of targeted advertising."
        ),
    },
    "FL": {
        "title": "Florida Digital Bill of Rights",
        "days": 45,
        "text": (
            "I reside in Florida. If you are a controller covered by the Florida Digital Bill of Rights "
            "(Fla. Stat. § 501.701 et seq.), delete my personal data and opt me out of the sale of it. "
            "If you are not covered, honor this as a standing do-not-sell request anyway."
        ),
    },
    "MT": {
        "title": "Montana Consumer Data Privacy Act",
        "days": 45,
        "text": "I reside in Montana. Under the Montana Consumer Data Privacy Act, delete my personal data and opt me out of its sale, to the extent the statute gives me those rights.",
    },
    "IA": {
        "title": "Iowa Consumer Data Protection Act",
        "days": 90,
        "text": "I reside in Iowa. Under the Iowa Consumer Data Protection Act, delete my personal data and opt me out of its sale, to the extent the statute gives me those rights. Iowa's response window is longer than most states; please do not use that as a reason to ignore a simple suppression.",
    },
    "DE": {
        "title": "Delaware Personal Data Privacy Act",
        "days": 45,
        "text": "I reside in Delaware. Under the Delaware Personal Data Privacy Act, delete my personal data and opt me out of its sale and of targeted advertising, to the extent the statute gives me those rights.",
    },
    "NE": {
        "title": "Nebraska Data Privacy Act",
        "days": 45,
        "text": "I reside in Nebraska. Under the Nebraska Data Privacy Act, delete my personal data and opt me out of its sale and of targeted advertising, to the extent the statute gives me those rights.",
    },
    "NH": {
        "title": "New Hampshire Data Privacy Act",
        "days": 45,
        "text": "I reside in New Hampshire. Under the New Hampshire privacy statute, delete my personal data and opt me out of its sale and of targeted advertising, to the extent the law gives me those rights.",
    },
    "NJ": {
        "title": "New Jersey Data Privacy Act",
        "days": 45,
        "text": "I reside in New Jersey. Under the New Jersey Data Privacy Act, delete my personal data and opt me out of its sale and of targeted advertising, to the extent the statute gives me those rights.",
    },
    "TN": {
        "title": "Tennessee Information Protection Act",
        "days": 45,
        "text": "I reside in Tennessee. Under the Tennessee Information Protection Act, delete my personal data and opt me out of its sale and of targeted advertising, to the extent the statute gives me those rights.",
    },
    "MN": {
        "title": "Minnesota Consumer Data Privacy Act",
        "days": 45,
        "text": "I reside in Minnesota. Under the Minnesota Consumer Data Privacy Act, delete my personal data and opt me out of its sale and of targeted advertising, to the extent the statute gives me those rights.",
    },
    "MD": {
        "title": "Maryland Online Data Privacy Act",
        "days": 45,
        "text": "I reside in Maryland. Under the Maryland Online Data Privacy Act, delete my personal data and opt me out of its sale and of targeted advertising, to the extent the statute gives me those rights.",
    },
    "IN": {
        "title": "Indiana Consumer Data Protection Act",
        "days": 45,
        "text": "I reside in Indiana. Under the Indiana Consumer Data Protection Act, delete my personal data and opt me out of its sale, to the extent the statute gives me those rights.",
    },
    "KY": {
        "title": "Kentucky Consumer Data Protection Act",
        "days": 45,
        "text": "I reside in Kentucky. Under the Kentucky Consumer Data Protection Act, delete my personal data and opt me out of its sale, to the extent the statute gives me those rights.",
    },
    "RI": {
        "title": "Rhode Island Data Transparency and Privacy Protection Act",
        "days": 45,
        "text": "I reside in Rhode Island. Under the Rhode Island Data Transparency and Privacy Protection Act, delete my personal data and opt me out of its sale, to the extent the statute gives me those rights.",
    },
}

EU_COUNTRIES = {
    "EU",
    "EEA",
    "AT",
    "BE",
    "BG",
    "HR",
    "CY",
    "CZ",
    "DK",
    "EE",
    "FI",
    "FR",
    "DE",
    "GR",
    "HU",
    "IE",
    "IT",
    "LV",
    "LT",
    "LU",
    "MT",
    "NL",
    "PL",
    "PT",
    "RO",
    "SK",
    "SI",
    "ES",
    "SE",
    "IS",
    "LI",
    "NO",
    "GB",
    "UK",
}

COMPLAINTS = {
    "FTC": "https://reportfraud.ftc.gov/",
    "CA_AG": "https://oag.ca.gov/contact/consumer-complaint-against-business-or-company",
    "CPPA": "https://cppa.ca.gov/",
    "TX_AG": "https://www.texasattorneygeneral.gov/consumer-protection/file-consumer-complaint",
    "DROP": "https://privacy.ca.gov/drop/",
    "CA_REGISTRY": "https://cppa.ca.gov/data_broker_registry/",
}

GENERIC = (
    "I withdraw any consent to collect, use, sell, share, or license my personal information "
    "for people-search, marketing, advertising, or data-broker products. Delete it from your "
    "systems and from products you sell to others. If a public-record feed later reintroduces it, "
    "suppress it again. Do not require a paid account. If you need more information to find the "
    "right record, ask for the minimum, once."
)


def normalize_state(value: str | None) -> str:
    raw = " ".join((value or "").split())
    if not raw:
        return ""
    upper = raw.upper()
    if upper in US_STATES:
        return upper
    for code, name in US_STATES.items():
        if name.lower() == raw.lower():
            return code
    return raw[:80]


def state_name(code: str | None) -> str:
    raw = " ".join((code or "").split())
    if not raw:
        return ""
    if raw.upper() in US_STATES:
        return US_STATES[raw.upper()]
    for name in US_STATES.values():
        if name.lower() == raw.lower():
            return name
    return raw


def full_name(profile: dict) -> str:
    parts = [profile.get("first_name") or "", profile.get("middle_name") or "", profile.get("last_name") or ""]
    return " ".join(p for p in parts if p).strip()


def current_address(profile: dict) -> dict:
    addresses = profile.get("addresses") or []
    for address in addresses:
        if address.get("current"):
            return address
    return addresses[0] if addresses else {}


def applicable_laws(profile: dict) -> list[dict]:
    from app.places import normalize_country

    laws = []
    country = normalize_country(profile.get("country") or "")
    state = normalize_state(profile.get("residence_state") or current_address(profile).get("state"))
    if not country and state in US_STATES:
        country = "US"
    if country == "US" and state in LAWS:
        laws.append({"id": state, **LAWS[state]})
    if country in EU_COUNTRIES or country in {"GB", "UK", "EU"}:
        title = "UK GDPR and the Data Protection Act 2018" if country == "GB" else "GDPR"
        laws.append(
            {
                "id": "GDPR",
                "title": title,
                "days": 30,
                "text": (
                    f"I am in a place covered by the {title}. Erase my personal data under Article 17, "
                    "stop processing it for people-search and marketing under Article 21, and tell me "
                    "what you hold under Article 15. Pass this request to processors where Article 19 requires it."
                ),
            }
        )
    if country == "CA":
        laws.append(
            {
                "id": "PIPEDA",
                "title": "PIPEDA",
                "days": 30,
                "text": (
                    "I am in Canada. Under PIPEDA I withdraw consent to the collection, use, and disclosure "
                    "of my personal information for marketing and people-search products, and I ask you to delete it."
                ),
            }
        )
    return laws


def response_days(profile: dict, broker: dict | None = None) -> int:
    laws = applicable_laws(profile)
    days = min((law["days"] for law in laws), default=45)
    if broker and broker.get("legal_max_days"):
        days = min(days, int(broker["legal_max_days"]))
    return days


def deadline_from(profile: dict, start: date | None = None, broker: dict | None = None) -> str:
    start = start or datetime.now(timezone.utc).date()
    return (start + timedelta(days=response_days(profile, broker))).isoformat()


def _identifiers(profile: dict) -> list[str]:
    lines = [f"Name: {full_name(profile)}"]
    aliases = profile.get("aliases") or []
    if aliases:
        rendered = ", ".join(
            " ".join(p for p in (a.get("first"), a.get("last")) if p) for a in aliases if isinstance(a, dict)
        )
        if rendered.strip():
            lines.append(f"Also known as: {rendered}")
    emails = profile.get("emails") or []
    phones = profile.get("phones") or []
    if emails:
        lines.append("Email: " + ", ".join(emails))
    if phones:
        lines.append("Phone: " + ", ".join(_format_phone(p) for p in phones))
    address = current_address(profile)
    city = address.get("city") or ""
    state = state_name(address.get("state"))
    street = address.get("street") or ""
    zip_code = address.get("zip") or ""
    place = ", ".join(p for p in (street, city, state, zip_code) if p)
    if place:
        lines.append(f"Address: {place}")
    from app.places import country_name, normalize_country

    residence = state_name(profile.get("residence_state"))
    country = normalize_country(profile.get("country") or "")
    if country == "US" or (not country and normalize_state(profile.get("residence_state")) in US_STATES):
        if residence:
            lines.append(f"State of residence: {residence}")
    else:
        place = ", ".join(part for part in (residence, country_name(country)) if part)
        if place:
            lines.append(f"Place of residence: {place}")
    if profile.get("include_dob") and profile.get("dob"):
        lines.append(f"Date of birth: {profile['dob']}")
    return lines


def _format_phone(value: str) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return str(value)


def _law_block(profile: dict) -> str:
    laws = applicable_laws(profile)
    parts = [law["text"] for law in laws]
    parts.append(GENERIC)
    return "\n\n".join(parts)


def _requests() -> str:
    return "\n".join(
        [
            "1. Delete my personal information, including inferences and derived profiles, from people-search, marketing, and broker products.",
            "2. Opt me out of the sale and sharing of my personal information, including targeted advertising.",
            "3. Tell customers and processors who received it to delete it, where the law requires you to pass the request on.",
            "4. Suppress me again if a later data feed reintroduces the same record. Do not treat a new public-record dump as fresh consent.",
            "5. Confirm in writing what you deleted, what you kept and the legal reason, and the date the suppression was applied.",
        ]
    )


def build_letter(profile: dict, broker: dict | None = None, kind: str = "deletion", removal: dict | None = None) -> dict:
    name = full_name(profile)
    today = datetime.now(timezone.utc).date().isoformat()
    days = response_days(profile, broker)
    who = broker["name"] if broker else "Data broker privacy office"
    domain = broker.get("domain") if broker else ""
    subject = f"Deletion and opt-out request — {name}"
    if kind == "followup":
        subject = f"Follow-up: unanswered deletion request — {name}"
    elif kind == "escalation":
        subject = f"Consumer complaint: data broker did not honor a deletion request — {name}"

    ident = "\n".join(_identifiers(profile))
    if kind == "escalation":
        body = _escalation(profile, broker, removal, ident, today)
    elif kind == "followup":
        body = _followup(profile, broker, removal, ident, today, days)
    else:
        intro = f"To the privacy office at {who}" + (f" ({domain})" if domain else "") + ":"
        body = (
            f"{intro}\n\n"
            f"I am writing on {today} to demand that you delete, suppress, and stop selling or sharing my personal information.\n\n"
            "I am the person named below, or I am authorized to act for them. This is a request about my own information.\n\n"
            f"{ident}\n\n"
            "Please do all of the following:\n"
            f"{_requests()}\n\n"
            f"{_law_block(profile)}\n\n"
            f"Complete this within {days} days of {today}. "
            "If you cannot verify me, treat the request as an opt-out of sale and sharing rather than a reason to do nothing.\n\n"
            "If you do not respond by the deadline, I may file a complaint with my state attorney general"
            + (" and the California Privacy Protection Agency" if normalize_state(profile.get("residence_state")) == "CA" else "")
            + f" and with the Federal Trade Commission ({COMPLAINTS['FTC']}).\n\n"
            f"{name}\n"
            "Sent from my own mailbox, via LeaveMeAlone — a local tool that does not send this for me.\n\n"
            "This letter is a consumer request, not legal advice."
        )
    return {
        "subject": subject,
        "body": body,
        "days": days,
        "laws": applicable_laws(profile),
        "to": (broker or {}).get("email"),
        "optout_url": (broker or {}).get("optout_url"),
        "kind": kind,
    }


def _followup(profile, broker, removal, ident, today, days) -> str:
    name = full_name(profile)
    who = broker["name"] if broker else "your privacy office"
    sent = (removal or {}).get("submitted_at") or "a previous date"
    due = (removal or {}).get("deadline_at") or "the statutory deadline"
    sent_day = sent[:10]
    return (
        f"To the privacy office at {who}:\n\n"
        f"I wrote to you on {sent_day} and asked you to delete and stop selling my personal information. "
        f"The deadline was {due}. It is now {today}, and I do not have a confirmation that you did it.\n\n"
        f"{ident}\n\n"
        "Please finish the original request within 10 days. Confirm what you deleted, what you kept and why, "
        "and the date you suppressed the record. Do not ask me to buy a report to see myself.\n\n"
        f"{_law_block(profile)}\n\n"
        "If I do not hear back, I will file a complaint with my state attorney general and the Federal Trade Commission "
        f"({COMPLAINTS['FTC']}). This is a notice of that next step, not a threat of anything else.\n\n"
        f"{name}\n"
        "This letter is a consumer request, not legal advice."
    )


def _escalation(profile, broker, removal, ident, today) -> str:
    name = full_name(profile)
    who = broker["name"] if broker else "a data broker"
    domain = (broker or {}).get("domain") or ""
    sent = ((removal or {}).get("submitted_at") or "an earlier date")[:10]
    due = (removal or {}).get("deadline_at") or "the deadline in my request"
    residence = state_name(profile.get("residence_state")) or "my state"
    return (
        f"Consumer protection complaint\n{today}\n\n"
        f"I am {name}, a resident of {residence}. I am filing this myself.\n\n"
        f"On {sent} I asked {who}"
        + (f" ({domain})" if domain else "")
        + " to delete my personal information and to stop selling or sharing it. "
        f"I asked them to finish by {due}. They have not confirmed that they did.\n\n"
        f"{ident}\n\n"
        "I am asking you to review whether this company ignored a consumer deletion or opt-out request "
        "required by the privacy law of my state, or engaged in an unfair practice by continuing to sell "
        "information after a clear opt-out.\n\n"
        "I can provide the letter I sent and any reply. I am not asking you to erase a court or property record "
        "held by a government office. I am asking about a commercial broker's copy.\n\n"
        f"Federal Trade Commission complaints: {COMPLAINTS['FTC']}\n"
        f"{name}\n"
        "This draft is a starting point, not legal advice. Read it before you file."
    )


def chunked(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]
