"""Unit tests for the scoring service: rule engine, mock AI confidence, blend,
and combined-score clamping. Includes the engineered disagreement lead (#4).
"""
import unittest

from revops_copilot import config
from revops_copilot.clients.salesforce_client import MockSalesforceClient
from revops_copilot.models import Lead
from revops_copilot.services import scoring_service


class TestRuleEngine(unittest.TestCase):
    def test_high_fit_enterprise_scores_high(self):
        lead = Lead(
            Company="Big U",
            Industry="Higher Education",
            NumberOfEmployees=18000,
            AnnualRevenue=900_000_000,
            LeadSource="Partner Referral",
            Timeline__c="This Quarter",
            Budget_Confirmed__c=True,
            DecisionMakerIdentified__c=True,
        )
        result = scoring_service.compute_rule_score(lead)
        # 20 emp + 20 rev + 15 icp + 12 ls + 12 timeline + 8 + 8 = 95
        self.assertEqual(result.rule_score, 95.0)
        self.assertEqual(result.rule_breakdown["icp_industry"], config.SCORING_WEIGHTS["icp_industry_match"])

    def test_low_fit_smb_scores_low(self):
        lead = Lead(
            Company="Tiny Co",
            Industry="Consumer Services",
            NumberOfEmployees=15,
            AnnualRevenue=800_000,
            LeadSource="Content Download",
            Timeline__c="No Timeline",
        )
        result = scoring_service.compute_rule_score(lead)
        # 0 emp + 2 rev + 0 icp + 7 ls + 0 timeline = 9
        self.assertEqual(result.rule_score, 9.0)

    def test_rule_score_clamped_to_100(self):
        lead = Lead(
            Industry="Higher Education",
            NumberOfEmployees=999999,
            AnnualRevenue=10_000_000_000,
            LeadSource="RFP Request",
            Timeline__c="This Quarter",
            Budget_Confirmed__c=True,
            DecisionMakerIdentified__c=True,
        )
        result = scoring_service.compute_rule_score(lead)
        self.assertLessEqual(result.rule_score, 100.0)


class TestAiConfidenceAndBlend(unittest.TestCase):
    def test_positive_description_raises_confidence(self):
        lead = Lead(Description="Board approved budget; urgent, ready to buy; decision maker engaged.")
        r = scoring_service.compute_mock_ai_confidence(lead)
        self.assertGreater(r.ai_confidence, 0.7)

    def test_negative_description_lowers_confidence(self):
        lead = Lead(Description="Just researching, no budget, exploring, maybe next year, not sure.")
        r = scoring_service.compute_mock_ai_confidence(lead)
        self.assertLessEqual(r.ai_confidence, 0.1)

    def test_blend_formula(self):
        lead = Lead(
            Industry="Higher Education",
            NumberOfEmployees=18000,
            AnnualRevenue=900_000_000,
            LeadSource="Partner Referral",
            Timeline__c="This Quarter",
            Budget_Confirmed__c=True,
            DecisionMakerIdentified__c=True,
            Description="Board approved budget; urgent, ready to buy; decision maker engaged; immediate expansion.",
        )
        result = scoring_service.score_lead(lead)
        expected = config.RULE_BLEND * result.rule_score + config.AI_BLEND * result.ai_confidence_pct
        self.assertAlmostEqual(result.combined_score, min(100.0, expected), places=4)

    def test_explicit_ai_confidence_overrides_mock(self):
        lead = Lead(NumberOfEmployees=100, Description="anything")
        result = scoring_service.score_lead(lead, ai_confidence=0.9, ai_mode="live")
        self.assertEqual(result.ai_mode, "live")
        self.assertAlmostEqual(result.ai_confidence, 0.9)


class TestEngineeredDisagreementLead(unittest.TestCase):
    def test_sample_lead_4_rule_ai_disagree_by_more_than_30(self):
        sf = MockSalesforceClient()
        lead = sf.get_lead("00Q000000000004")
        self.assertIsNotNone(lead)
        result = scoring_service.score_lead(lead)
        disagreement = abs(result.rule_score - result.ai_confidence_pct)
        self.assertGreater(disagreement, config.DISAGREEMENT_THRESHOLD)


if __name__ == "__main__":
    unittest.main()
