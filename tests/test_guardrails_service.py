"""Unit tests for the guardrail checks and the "fall back to template on any
failure" contract exercised through the generation service.
"""
import unittest

from revops_copilot.models import Account, Lead
from revops_copilot.services import content_library_service, generation_service
from revops_copilot.services import guardrails_service as g


def _valid_rep_brief():
    return {
        "account_summary": "Acme is a Higher Education organization with 500 employees.",
        "key_signals": ["Budget confirmed"],
        "likely_objections": [{"objection": "Too pricey", "suggested_response": "Show ROI"}],
        "next_best_action": "Book a discovery call.",
        "recommended_talk_track": "Lead with outcomes.",
        "confidence_notes": "High confidence.",
    }


class TestRepBriefGuardrails(unittest.TestCase):
    def test_valid_brief_passes(self):
        ok, failures = g.validate_rep_brief(_valid_rep_brief(), "Acme 500 employees Higher Education")
        self.assertTrue(ok, failures)

    def test_missing_key_fails(self):
        data = _valid_rep_brief()
        del data["next_best_action"]
        ok, failures = g.validate_rep_brief(data, "context")
        self.assertFalse(ok)

    def test_pii_leak_fails(self):
        data = _valid_rep_brief()
        data["confidence_notes"] = "SSN is 123-45-6789 for the contact."
        ok, failures = g.validate_rep_brief(data, "context")
        self.assertFalse(ok)
        self.assertTrue(any("PII" in f for f in failures))

    def test_ungrounded_number_fails(self):
        data = _valid_rep_brief()
        data["account_summary"] = "They have exactly 987654 employees."
        ok, failures = g.validate_rep_brief(data, "context with no such number")
        self.assertFalse(ok)
        self.assertTrue(any("ungrounded" in f for f in failures))


class TestEmailGuardrails(unittest.TestCase):
    def test_pricing_in_email_fails(self):
        data = {
            "subject": "Hi",
            "body": "We can do this for $5,000 per year.",
            "call_to_action": "Let's talk",
        }
        ok, failures = g.validate_email(data, "context $5,000")
        self.assertFalse(ok)
        self.assertTrue(any("pricing" in f.lower() for f in failures))


class TestProposalGuardrails(unittest.TestCase):
    def test_fabricated_block_id_fails(self):
        valid_id = next(iter(content_library_service.valid_block_ids()))
        data = {
            "sections": [
                {"title": "Overview", "content": "text", "content_block_ids": [valid_id]},
                {"title": "Fake", "content": "text", "content_block_ids": ["CB-DOES-NOT-EXIST"]},
            ],
            "needs_pricing_followup": True,
        }
        ok, failures = g.validate_proposal(data)
        self.assertFalse(ok)
        self.assertTrue(any("fabricated" in f for f in failures))

    def test_unapproved_dollar_figure_fails(self):
        valid_id = next(iter(content_library_service.valid_block_ids()))
        data = {
            "sections": [
                {"title": "Pricing", "content": "Only $999,999.", "content_block_ids": [valid_id]},
            ],
            "needs_pricing_followup": True,
        }
        ok, failures = g.validate_proposal(data)
        self.assertFalse(ok)

    def test_template_proposal_passes_its_own_guardrails(self):
        lead = Lead(Company="Riverside CCD", RequestType="RFP Request")
        account = Account(Name="Riverside CCD", Type="Higher Education")
        draft = generation_service._template_proposal(lead, account)
        ok, failures = g.validate_proposal({"sections": draft.sections})
        self.assertTrue(ok, failures)
        self.assertTrue(draft.needs_human_review)  # always forced


class TestGenerationFallbackContract(unittest.TestCase):
    def test_template_rep_brief_passes_guardrails(self):
        lead = Lead(
            Company="Acme University",
            Industry="Higher Education",
            NumberOfEmployees=500,
            Title="Dean",
            LeadSource="Webinar",
        )
        account = Account(Name="Acme University", Type="Higher Education", TechStack=["Canvas"])
        # Call the template function directly (not the public generate_rep_brief
        # dispatcher) so this test stays deterministic and free regardless of
        # whether a real ANTHROPIC_API_KEY happens to be set in the environment.
        brief = generation_service._template_rep_brief(lead, account, None, None, None)
        payload = generation_service._context_payload(lead, account, None, None, None)
        ctx = generation_service._context_text(payload)
        ok, failures = g.validate_rep_brief(
            {
                "account_summary": brief.account_summary,
                "key_signals": brief.key_signals,
                "likely_objections": brief.likely_objections,
                "next_best_action": brief.next_best_action,
                "recommended_talk_track": brief.recommended_talk_track,
                "confidence_notes": brief.confidence_notes,
            },
            ctx,
        )
        self.assertTrue(ok, failures)


if __name__ == "__main__":
    unittest.main()
