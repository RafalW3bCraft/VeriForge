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