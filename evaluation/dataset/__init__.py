from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

VALID_CATEGORIES = {"legitimate", "scam", "impersonation", "ambiguous"}
VALID_INPUT_TYPES = {"message", "email", "url"}


@dataclass(frozen=True)
class EvaluationSample:
    id: str
    category: str
    input_type: str
    content: str
    expected_verdict: str
    expected_evidence_characteristics: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvaluationSample":
        required = {"id", "category", "input_type", "content", "expected_verdict"}
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(f"Sample is missing required fields: {', '.join(missing)}")

        category = str(payload["category"])
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Unsupported category: {category}")

        input_type = str(payload["input_type"])
        if input_type not in VALID_INPUT_TYPES:
            raise ValueError(f"Unsupported input type: {input_type}")

        characteristics = payload.get("expected_evidence_characteristics", [])
        if characteristics is None:
            characteristics = []
        if not isinstance(characteristics, list):
            raise ValueError(f"expected_evidence_characteristics must be a list for sample {payload.get('id')}")

        return cls(
            id=str(payload["id"]),
            category=category,
            input_type=input_type,
            content=str(payload["content"]),
            expected_verdict=str(payload["expected_verdict"]),
            expected_evidence_characteristics=tuple(str(item) for item in characteristics),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["expected_evidence_characteristics"] = list(self.expected_evidence_characteristics)
        return data


def _repeat_templates(category: str, templates: Iterable[str], count: int, input_type: str) -> list[EvaluationSample]:
    samples: list[EvaluationSample] = []
    template_list = list(templates)
    if not template_list:
        raise ValueError(f"No templates configured for {category}")

    for index in range(count):
        template = template_list[index % len(template_list)]
        sample = EvaluationSample(
            id=f"{category}-{index + 1:03d}",
            category=category,
            input_type=input_type,
            content=template,
            expected_verdict={
                "legitimate": "SAFE",
                "scam": "CRITICAL",
                "impersonation": "HIGH",
                "ambiguous": "SUSPICIOUS",
            }[category],
            expected_evidence_characteristics={
                "legitimate": ("routine_security_notice", "trusted_domain", "no_credential_request"),
                "scam": ("urgency", "credential_request", "suspicious_url"),
                "impersonation": ("identity_claim", "credential_request", "mismatched_sender"),
                "ambiguous": ("security_wording", "uncertain_action", "limited_evidence"),
            }[category],
        )
        samples.append(sample)
    return samples


def build_default_dataset() -> list[EvaluationSample]:
    legitimate_templates = [
        "Your security settings were updated. Review recent changes at https://github.com/settings/security.",
        "A routine activity check completed successfully. Open https://github.com/settings/security to inspect the latest summary.",
        "No action is required. See the updated security overview at https://github.com/settings/security.",
        "Your account review is now complete. Open https://github.com/settings/notifications for a summary.",
        "Recent account activity was reviewed and no unusual behavior was found. Visit https://github.com/settings/security.",
        "This is a standard account notice. Details are available in your GitHub security dashboard: https://github.com/settings/security.",
        "The system completed a scheduled security check. Review the updated report at https://github.com/settings/security.",
        "Your account has no open security alerts. See https://github.com/settings/security for the latest status.",
        "You do not need to change any settings. Review the account summary at https://github.com/settings/security.",
        "This is a confirmation email for your normal account activity. Open https://github.com/settings/security to review details.",
    ]
    scam_templates = [
        "URGENT: Your GitHub account has been compromised. Verify immediately at https://github-security-check.zip and enter your password and verification code.",
        "Final notice: Your bank account is restricted. Open https://secure-bank-alert.top and transfer funds to restore access.",
        "Action required: your account is suspended. Sign in now at https://verify-portal.click and provide your OTP.",
        "Your package delivery is blocked. Confirm your details at https://shipment-secure.xyz and provide your payment information.",
        "Security alert: update your credentials today at https://account-verify.live before access is disabled.",
    ]
    impersonation_templates = [
        "This is Daniel from the executive office. Please approve a vendor payment immediately and send the verification code to https://finance-portal.click.",
        "I am the IT director. Your payroll system is under review. Log in at https://it-helpdesk.zip and share your password.",
        "From the legal team: confirm the settlement transfer with our partner. Enter the OTP at https://legal-security.top.",
        "Alicia from procurement needs you to authorize a rush payment. Use https://vendor-approval.xyz and submit your credentials.",
        "This is your CFO. There is a critical payroll issue. Visit https://payroll-security.click and enter the code immediately.",
    ]
    ambiguous_templates = [
        "We need a quick review of your account. Please click the secure portal in the message and confirm recent updates.",
        "Your login looks unusual. Open the link below and check whether a security review is required for your account.",
        "An access review is pending. Please look at the attached security portal and confirm whether the activity is yours.",
        "Action may be needed for recent payment activity. Review the link in this message and verify the request through your usual channel.",
        "We are validating recent access attempts. Visit the security portal to confirm whether the activity was expected.",
    ]

    dataset: list[EvaluationSample] = []
    dataset.extend(_repeat_templates("legitimate", legitimate_templates, 50, "email"))
    dataset.extend(_repeat_templates("scam", scam_templates, 50, "message"))
    dataset.extend(_repeat_templates("impersonation", impersonation_templates, 25, "email"))
    dataset.extend(_repeat_templates("ambiguous", ambiguous_templates, 25, "message"))
    return dataset


def load_dataset(path: str | Path) -> list[EvaluationSample]:
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"Dataset file not found: {target}")

    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Dataset payload must be a list of sample objects")

    return [EvaluationSample.from_dict(item) for item in payload]


def save_dataset(path: str | Path, dataset: list[EvaluationSample]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps([sample.to_dict() for sample in dataset], indent=2),
        encoding="utf-8",
    )
