"""Unit tests for routing bands and the override priority order:
out-of-territory > existing-customer > disagreement(>30) > RFP flag.
"""
import unittest

from revops_copilot.models import Lead, ScoreResult
from revops_copilot.services import routing_service, scoring_service
from revops_copilot.clients.salesforce_client import MockSalesforceClient


def _score(rule, ai_pct, combined=None):
    ai = ai_pct / 100.0
    if combined is None:
        combined = 0.6 * rule + 0.4 * ai_pct
    return ScoreResult(rule_score=rule, ai_confidence=ai, combined_score=combined)


class TestBands(unittest.TestCase):
    def test_ae_band(self):
        d = routing_service.route_lead(Lead(Territory__c="NAMER"), _score(90, 90))
        self.assertEqual(d.band, "AE")
        self.assertEqual(d.routing_outcome, "Route to AE")

    def test_sdr_band(self):
        d = routing_service.route_lead(Lead(Territory__c="NAMER"), _score(60, 60))
        self.assertEqual(d.band, "SDR")

    def test_nurture_band(self):
        d = routing_service.route_lead(Lead(Industry="Higher Education", Territory__c="NAMER"), _score(30, 30))
        self.assertEqual(d.band, "Nurture")
        self.assertTrue(d.nurture_segment)  # segment set for nurture

    def test_low_priority_nurture(self):
        d = routing_service.route_lead(Lead(Territory__c="NAMER"), _score(10, 10))
        self.assertEqual(d.band, "Nurture (Low Priority)")


class TestOverridePriority(unittest.TestCase):
    def test_out_of_territory_beats_everything(self):
        # High score AND existing customer AND disagreement -- territory still wins.
        lead = Lead(Territory__c="EMEA", ExistingCustomer__c=True, Industry="Higher Education")
        d = routing_service.route_lead(lead, _score(95, 10, combined=95))
        self.assertIn("Out of Territory", d.routing_outcome)
        self.assertFalse(d.needs_human_review)

    def test_existing_customer_beats_disagreement(self):
        lead = Lead(Territory__c="NAMER", ExistingCustomer__c=True)
        d = routing_service.route_lead(lead, _score(90, 10, combined=60))
        self.assertEqual(d.routing_outcome, "Route to AE (Existing Account)")
        self.assertEqual(d.band, "AE")

    def test_disagreement_forces_human_review(self):
        lead = Lead(Territory__c="NAMER")
        d = routing_service.route_lead(lead, _score(80, 20, combined=56))
        self.assertTrue(d.needs_human_review)
        self.assertEqual(d.routing_outcome, "Needs Human Review")

    def test_small_disagreement_does_not_flag(self):
        lead = Lead(Territory__c="NAMER")
        d = routing_service.route_lead(lead, _score(70, 60, combined=66))
        self.assertFalse(d.needs_human_review)

    def test_rfp_sets_independent_proposal_flag(self):
        lead = Lead(Territory__c="NAMER", RequestType="RFP Request")
        d = routing_service.route_lead(lead, _score(80, 80))
        self.assertTrue(d.proposal_required)
        self.assertEqual(d.band, "AE")  # RFP does not change the band


class TestSampleLeadsEndToEnd(unittest.TestCase):
    def setUp(self):
        self.sf = MockSalesforceClient()

    def _route(self, lead_id):
        lead = self.sf.get_lead(lead_id)
        score = scoring_service.score_lead(lead)
        return lead, routing_service.route_lead(lead, score)

    def test_lead1_hot_enterprise_to_ae(self):
        _, d = self._route("00Q000000000001")
        self.assertEqual(d.routing_outcome, "Route to AE")

    def test_lead4_ambiguous_needs_human_review(self):
        _, d = self._route("00Q000000000004")
        self.assertTrue(d.needs_human_review)

    def test_lead6_out_of_territory_forced_nurture(self):
        _, d = self._route("00Q000000000006")
        self.assertIn("Out of Territory", d.routing_outcome)

    def test_lead8_existing_customer(self):
        _, d = self._route("00Q000000000008")
        self.assertEqual(d.routing_outcome, "Route to AE (Existing Account)")


if __name__ == "__main__":
    unittest.main()
