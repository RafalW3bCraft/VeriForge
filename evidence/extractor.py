import hashlib
import re
from urllib.parse import urlparse

from models import Claim, Evidence, ExtractionResult

URL_RE = re.compile(r"https?://[^\s<>()]+", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
NEGATED_REQUEST_PATTERNS = (
    r"\bnever\s+(ask|request|want|need)\b",
    r"\bwill\s+never\s+(ask|request|want|need)\b",
    r"\bdo\s+not\s+(share|give|enter|provide|send|submit)\b",
    r"\bno\s+action\s+is\s+required\b",
    r"\bno\s+action\s+required\b",
    r"\bnot\s+required\b",
)


def clean_url(url: str) -> str:
    # Handle Markdown links:
    # [https://example.com](https://example.com)
    match = re.search(r"\]\((https?://[^)]+)\)", url)
    if match:
        url = match.group(1)
    return url.rstrip(".,;:!?")

URGENCY_WORDS = {"urgent","immediately","now","asap","suspended","final notice","expires","action required"}
CREDENTIAL_WORDS = {"password","passcode","otp","one-time code","verification code","login","sign in","credential"}
FINANCIAL_WORDS = {"payment","transfer","wire","gift card","invoice","bank account","crypto","bitcoin","usdt"}
REQUEST_VERBS = (
    "verify",
    "enter",
    "provide",
    "share",
    "submit",
    "confirm",
    "send",
    "update",
    "review",
    "log in",
    "sign in",
)


def _contains_negated_request(text: str) -> bool:
    lowered = text.casefold()
    return any(re.search(pattern, lowered) for pattern in NEGATED_REQUEST_PATTERNS)


def _has_credential_request(text: str) -> bool:
    lowered = text.casefold()
    if _contains_negated_request(text):
        return False
    for credential in CREDENTIAL_WORDS:
        if credential not in lowered:
            continue
        if re.search(rf"\b(?:need(?:s)?|need\s+to|require(?:s)?|required|must|ask(?:s)?\s+you\s+to|want(?:s)?|demand(?:s)?|verify|enter|provide|share|submit|confirm|send|update|review|log\s+in|sign\s+in)\b.*\b{re.escape(credential)}\b", lowered):
            return True
        if re.search(rf"\b{re.escape(credential)}\b.*\b(?:required|needed|need(?:s)?|need\s+to|require(?:s)?|must|ask(?:s)?\s+you\s+to|want(?:s)?|demand(?:s)?|verify|enter|provide|share|submit|confirm|send|update|review|log\s+in|sign\s+in)\b", lowered):
            return True
    return False


def _has_financial_request(text: str) -> bool:
    lowered = text.casefold()
    if _contains_negated_request(text):
        return False
    if re.search(r"\b(?:wire|transfer|send|pay|deposit|remit|move|pay out)\b", lowered):
        return True
    if re.search(r"\b(?:payment|invoice|gift\s+card|bank\s+account)\b", lowered):
        if re.search(r"\b(?:now|immediately|today|urgent|before|required|must|need|asap)\b", lowered):
            return True
    return False

def _stable_id(prefix: str, kind: str, value: str) -> str:
    digest = hashlib.sha256(f"{kind}\0{value}".encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _snippet(content: str, value: str) -> str | None:
    start = content.casefold().find(value.casefold())
    if start < 0:
        return None
    left = max(0, start - 60)
    right = min(len(content), start + len(value) + 60)
    snippet = re.sub(r"\s+", " ", content[left:right]).strip()[:240]
    normalized_content = re.sub(r"\s+", " ", content).strip()
    if snippet == normalized_content and normalized_content != value:
        return value[:240]
    return snippet


def extract_claims(content: str) -> ExtractionResult:
    url_content = re.sub(r"\[[^\]]*\]\((https?://[^)]+)\)", r"\1", content)
    urls = list(dict.fromkeys(clean_url(url) for url in URL_RE.findall(url_content)))
    emails = EMAIL_RE.findall(content)
    lower = content.lower()

    domains = []
    for u in urls:
        try:
            host = urlparse(u).hostname
            if host:
                domains.append(host)
        except Exception:
            pass

    urgency_terms = sorted(word for word in URGENCY_WORDS if word in lower)
    credential_terms = sorted(word for word in CREDENTIAL_WORDS if word in lower)
    financial_terms = sorted(word for word in FINANCIAL_WORDS if word in lower)
    requests_credentials = _has_credential_request(content)
    requests_financial_action = _has_financial_request(content)
    claims: list[Claim] = []
    evidence: list[Evidence] = []

    def add_observation(kind: str, value: str) -> None:
        snippet = _snippet(content, value)
        evidence.append(Evidence(
            id=_stable_id("evidence", kind, value),
            kind=kind,
            value=value,
            snippet=snippet,
        ))
        claims.append(Claim(
            id=_stable_id("claim", kind, value),
            kind=kind,
            value=value,
            snippet=snippet,
        ))

    for url in urls:
        add_observation("url", url)
    for domain in domains:
        add_observation("domain", domain)
    for email in emails:
        add_observation("email_address", email)
    for term in urgency_terms:
        add_observation("urgency_term", term)
    for term in credential_terms:
        add_observation("credential_term", term)
    for term in financial_terms:
        add_observation("financial_term", term)

    return ExtractionResult(
        urls=urls,
        domains=domains,
        emails=emails,
        urgency_terms=urgency_terms,
        credential_terms=credential_terms,
        financial_terms=financial_terms,
        requests_credentials=requests_credentials,
        requests_financial_action=requests_financial_action,
        claims=claims,
        evidence=evidence,
    )
