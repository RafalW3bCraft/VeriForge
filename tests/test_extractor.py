from evidence.extractor import extract_claims
from models import ExtractionResult


def test_extract_claims_returns_typed_evidence_with_source_snippets():
    message = (
        "URGENT: verify your account at "
        "[https://github-security-check.zip](https://github-security-check.zip) "
        "and enter your password."
    )

    result = extract_claims(message)

    assert isinstance(result, ExtractionResult)
    assert result.urls == ["https://github-security-check.zip"]
    assert result.domains == ["github-security-check.zip"]
    assert result.requests_credentials is True
    assert {item.kind for item in result.evidence} >= {
        "url", "domain", "urgency_term", "credential_term"
    }
    assert all(item.snippet and len(item.snippet) <= 240 for item in result.evidence)


def test_extraction_ids_are_stable_and_duplicate_urls_are_collapsed():
    message = "https://example.test and https://example.test."

    first = extract_claims(message)
    second = extract_claims(message)

    assert first.urls == ["https://example.test"]
    assert [item.id for item in first.evidence] == [item.id for item in second.evidence]


def test_short_message_snippets_do_not_copy_the_full_body():
    message = "URGENT: enter password at https://example.zip"

    result = extract_claims(message)

    assert all(item.snippet != message for item in result.evidence)


def test_real_credential_requests_are_detected_but_negated_mentions_are_not():
    malicious = "The security team needs your password and OTP now."
    safe = "The security team will never ask for your password. Review through the official site."

    malicious_result = extract_claims(malicious)
    safe_result = extract_claims(safe)

    assert malicious_result.requests_credentials is True
    assert safe_result.requests_credentials is False


def test_real_financial_requests_are_detected_but_payment_success_is_not():
    malicious = "Wire $8,400 immediately to the updated account."
    safe = "Your payment was completed successfully. No action is required."

    malicious_result = extract_claims(malicious)
    safe_result = extract_claims(safe)

    assert malicious_result.requests_financial_action is True
    assert safe_result.requests_financial_action is False