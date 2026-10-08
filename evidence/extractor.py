import re
from urllib.parse import urlparse

URL_RE = re.compile(r"https?://[^\s<>()]+", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")

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

def extract_claims(content: str) -> dict:
    url_content = re.sub(r"\[[^\]]*\]\((https?://[^)]+)\)", r"\1", content)
    urls = [clean_url(u) for u in URL_RE.findall(url_content)]
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

    return {
        "urls": urls,
        "domains": domains,
        "emails": emails,
        "urgency_terms": sorted(w for w in URGENCY_WORDS if w in lower),
        "credential_terms": sorted(w for w in CREDENTIAL_WORDS if w in lower),
        "financial_terms": sorted(w for w in FINANCIAL_WORDS if w in lower),
        "requests_credentials": any(w in lower for w in CREDENTIAL_WORDS),
        "requests_financial_action": any(w in lower for w in FINANCIAL_WORDS),
    }
