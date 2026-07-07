"""Unit tests for intake hygiene: missing-field flags, normalization, and the
difflib-based duplicate-company detection (sample lead #2 near-duplicate).
"""
import unittest

from revops_copilot.models import Lead
from revops_copilot.services import data_quality_service as dq
from revops_copilot.clients.salesforce_client import MockSalesforceClient


class TestMissingFields(unittest.TestCase):
    def test_flags_missing_critical_fields(self):
        lead = Lead(Company="Acme", Email="", AnnualRevenue=0, NumberOfEmployees=0)
        result = dq.check_lead(lead)
        joined = " ".join(result.flags)
        self.assertIn("Email", joined)
        self.assertIn("AnnualRevenue", joined)
        self.assertIn("NumberOfEmployees", joined)
        self.assertFalse(result.passed)

    def test_complete_lead_passes(self):
        lead = Lead(Company="Acme", Email="a@b.com", AnnualRevenue=1_000_000, NumberOfEmployees=100)
        result = dq.check_lead(lead)
        self.assertTrue(result.passed)


class TestNormalization(unittest.TestCase):
    def test_email_normalized(self):
        lead = Lead(Company="Acme", Email="  A.B@Example.COM ", AnnualRevenue=1, NumberOfEmployees=1)
        result = dq.check_lead(lead)
        self.assertEqual(result.normalized_fields.get("Email"), "a.b@example.com")

    def test_phone_normalized_from_bare_digits(self):
        lead = Lead(Company="Acme", Email="a@b.com", Phone="5095551188", AnnualRevenue=1, NumberOfEmployees=1)
        result = dq.check_lead(lead)
        self.assertEqual(result.normalized_fields.get("Phone"), "(509) 555-1188")


class TestDuplicateCompany(unittest.TestCase):
    def test_near_duplicate_detected(self):
        # "BrightPath Tutoring LLC" vs known "BrightPath Tutoring, Inc."
        match = dq.find_duplicate_company(
            "BrightPath Tutoring LLC",
            ["BrightPath Tutoring, Inc.", "Some Other College"],
        )
        self.assertEqual(match, "BrightPath Tutoring, Inc.")

    def test_distinct_company_not_flagged(self):
        match = dq.find_duplicate_company(
            "Cedar Valley Unified School District",
            ["BrightPath Tutoring, Inc.", "Northgate Technical College"],
        )
        self.assertIsNone(match)

    def test_exact_same_raw_name_is_not_a_dup(self):
        match = dq.find_duplicate_company("Acme Inc.", ["Acme Inc."])
        self.assertIsNone(match)

    def test_sample_lead_2_trips_duplicate_flag(self):
        sf = MockSalesforceClient()
        lead = sf.get_lead("00Q000000000002")
        result = dq.check_lead(lead, sf.known_account_names())
        self.assertTrue(result.duplicate_of)
        self.assertTrue(any("duplicate company" in f.lower() for f in result.flags))


if __name__ == "__main__":
    unittest.main()
