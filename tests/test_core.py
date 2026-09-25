import tempfile
import unittest
from pathlib import Path

from app.catalog import load_catalog
from app.db import DB
from app.letters import build_letter, full_name
from app.scanner import classify_page, fill_search_url
from app.scoring import exposure_label, exposure_score, should_replace, transition


PROFILE = {
    "first_name": "Avery",
    "last_name": "Quinn",
    "middle_name": "",
    "aliases": [],
    "emails": ["avery.quinn.sample@example.net"],
    "phones": ["5125550148"],
    "addresses": [{"street": "1847 Cedar Lane", "city": "Austin", "state": "TX", "zip": "78704", "current": True}],
    "residence_state": "TX",
    "country": "US",
    "include_dob": False,
    "dob": "1990-01-02",
    "scan_phone": False,
}


class CatalogTests(unittest.TestCase):
    def test_directory_loads(self):
        catalog = load_catalog()
        self.assertGreater(len(catalog.brokers), 500)
        spokeo = catalog.get("spokeo")
        self.assertIn("spokeo.com/optout", spokeo["optout_url"])
        walled = catalog.get("truepeoplesearch")
        self.assertTrue(walled["cloudflare"])
        self.assertEqual(walled["email"], "support@truepeoplesearch.com")
        self.assertEqual(walled["phone"], "888-838-4803")
        self.assertIn("94120-7775", walled["postal"])
        email_method = next(method for method in walled["methods"] if method["type"] == "email")
        self.assertEqual(email_method["email"], "support@truepeoplesearch.com")
        self.assertNotIn("contact@truepeoplesearch.com", email_method["steps"][1])
        self.assertTrue(catalog.stats()["emailable"] > 100)
        self.assertIsNone(catalog.get("not-a-broker"))

    def test_peopleconnect_cluster(self):
        catalog = load_catalog()
        cluster = catalog.cluster_by_id["peopleconnect"]
        self.assertIn("intelius", cluster["members"])
        self.assertIn("truthfinder", cluster["members"])


class LetterTests(unittest.TestCase):
    def test_texas_cites_chapter_541_and_omits_dob(self):
        letter = build_letter(PROFILE, {"name": "Spokeo", "domain": "spokeo.com", "email": "privacy@spokeo.com", "legal_max_days": 45})
        self.assertIn("541", letter["body"])
        self.assertNotIn("1990-01-02", letter["body"])
        self.assertIn("Avery Quinn", letter["body"])
        self.assertIn("Spokeo", letter["body"])

    def test_california_cites_deletion_section(self):
        profile = {**PROFILE, "residence_state": "CA"}
        letter = build_letter(profile, None, "deletion")
        self.assertIn("1798.105", letter["body"])
        self.assertIn("1798.120", letter["body"])
        self.assertEqual(letter["days"], 45)

    def test_gdpr_for_uk(self):
        profile = {**PROFILE, "country": "GB", "residence_state": ""}
        letter = build_letter(profile, None, "deletion")
        self.assertIn("Article 17", letter["body"])
        self.assertEqual(letter["days"], 30)

    def test_followup_mentions_deadline(self):
        letter = build_letter(
            PROFILE,
            {"name": "Epsilon", "domain": "epsilon.com", "legal_max_days": 45},
            "followup",
            {"submitted_at": "2026-01-01T00:00:00+00:00", "deadline_at": "2026-02-15"},
        )
        self.assertIn("2026-02-15", letter["body"])
        self.assertIn("2026-01-01", letter["body"])


class ScanTests(unittest.TestCase):
    def test_search_url_uses_full_state_for_spokeo_and_never_dob(self):
        url = fill_search_url(
            "https://www.spokeo.com/{first_name}-{last_name}/{state}/{city}",
            PROFILE,
        )
        self.assertIn("avery-quinn", url)
        self.assertIn("texas", url)
        self.assertIn("austin", url)
        self.assertNotIn("1990", url)

    def test_phone_stays_out_of_url_unless_asked(self):
        url = fill_search_url("https://example.com/search?phone={phone}&name={first_name}", PROFILE)
        self.assertNotIn("5125550148", url)
        opted = {**PROFILE, "scan_phone": True}
        url = fill_search_url("https://example.com/search?phone={phone}", opted)
        self.assertIn("5125550148", url)

    def test_classify_block_clear_and_exposed(self):
        blocked = classify_page(200, "<html>Just a moment... checking your browser</html>", PROFILE, [])
        self.assertEqual(blocked["status"], "blocked")
        clear = classify_page(200, "<html><body>No results found for that search</body></html>", PROFILE, ["No results found"])
        self.assertEqual(clear["status"], "clear")
        exposed = classify_page(
            200,
            "<html><body>Avery Quinn lives in Austin and can be reached.</body></html>",
            PROFILE,
            [],
        )
        self.assertEqual(exposed["status"], "exposed")
        weak = classify_page(200, "<html><body>Avery Quinn, age unknown.</body></html>", PROFILE, [])
        self.assertEqual(weak["status"], "possible")


class ScoreTests(unittest.TestCase):
    def test_clear_does_not_score_and_cap_holds(self):
        sightings = [{"status": "clear", "source": "probe", "user_status": None, "evidence": {}}] * 10
        self.assertEqual(exposure_score(sightings), 0)
        self.assertEqual(exposure_label(0), "Quiet")
        hot = [{"status": "exposed", "source": "probe", "user_status": None, "evidence": {"phone": True, "city": "Austin"}}] * 20
        self.assertEqual(exposure_score(hot), 100)

    def test_user_clear_overrides(self):
        sightings = [{"status": "exposed", "source": "probe", "user_status": "clear", "evidence": {"phone": True}}]
        self.assertEqual(exposure_score(sightings), 0)

    def test_transitions(self):
        self.assertEqual(transition("clear", "exposed"), "reappeared")
        self.assertEqual(transition(None, "exposed"), "new")
        self.assertEqual(transition("exposed", "clear"), "cleared")
        self.assertIsNone(transition("blocked", "blocked"))
        self.assertFalse(should_replace("clear", "probe", "exposed", "web"))
        self.assertTrue(should_replace("blocked", "probe", "exposed", "web"))


class DbTests(unittest.TestCase):
    def test_reappearance_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = DB(Path(tmp) / "t.db")
            now = "2026-09-01T00:00:00+00:00"
            profile = database.insert_profile(
                {
                    "label": "Avery Quinn",
                    "first_name": "Avery",
                    "last_name": "Quinn",
                    "emails": ["a@example.net"],
                    "phones": [],
                    "addresses": [],
                    "aliases": [],
                    "residence_state": "TX",
                    "country": "US",
                    "sample": False,
                    "flags": {},
                },
                now,
            )
            finding = {
                "broker_id": "spokeo",
                "source": "probe",
                "status": "clear",
                "url": "https://spokeo.com/x",
                "title": "Spokeo",
                "snippet": "none",
                "evidence": {},
                "fingerprint": "probe:spokeo",
            }
            self.assertIsNone(database.record_sighting(profile["id"], finding, now))
            again = {**finding, "status": "exposed", "snippet": "back"}
            change = database.record_sighting(profile["id"], again, "2026-09-20T00:00:00+00:00")
            self.assertEqual(change["kind"], "reappeared")
            self.assertEqual(full_name(profile), "Avery Quinn")
            database.close()


if __name__ == "__main__":
    unittest.main()
