"""Prompt-injection screening and evidence sanitization.

Message content is attacker-controlled. Before it reaches any LLM prompt
or memory store, we screen for instruction-override patterns and flag the
content as untrusted. Screening never blocks analysis — it downgrades
trust and records the flag, consistent with the H-MEM rule that unverified,
untrusted content must not enter high-trust memory.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (name, re.compile(pattern, re.IGNORECASE | re.DOTALL))
    for name, pattern in (
        ("ignore_instructions", r"\bignore\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|prompts?|rules?)\b"),
        ("role_override", r"\byou\s+are\s+now\b|\bact\s+as\s+(an?\s+)?(ai|assistant|system|admin)\b|\bnew\s+instructions?\b"),
        ("system_prompt_probe", r"\b(reveal|show|print|repeat|disclose)\b.*\b(system\s+prompt|instructions?|prompt)\b"),
        ("delimiter_escape", r"<\s*/?\s*(system|im_start|im_end|instruction)\s*>|```\s*system|\[\s*INST\s*\]"),
        ("exfiltration", r"\b(send|post|forward|upload|exfiltrate)\b[\s\S]{0,80}\b(memory|memories|secrets?|keys?|tokens?|system\s+prompt|credentials?|contents?)\b[\s\S]{0,80}\b(webhook|endpoint|server|url|http)\b|\b(webhook|endpoint)\b[\s\S]{0,80}\b(memory|secrets?|keys?|tokens?|contents?)\b"),
    )
)

MAX_SNIPPET_CHARS = 240


@dataclass(frozen=True)
class ScreeningResult:
    flagged: bool
    patterns: tuple[str, ...]
    trust: str  # "trusted" | "untrusted"


def screen_content(content: str) -> ScreeningResult:
    """Screen attacker-controlled content for prompt-injection patterns."""
    hits = tuple(name for name, pattern in INJECTION_PATTERNS if pattern.search(content))
    return ScreeningResult(
        flagged=bool(hits),
        patterns=hits,
        trust="untrusted" if hits else "trusted",
    )


def sanitize_snippet(text: str, limit: int = MAX_SNIPPET_CHARS) -> str:
    """Bound a snippet for prompt/memory inclusion. Strips control chars."""
    cleaned = "".join(ch for ch in text if ch.isprintable() or ch in "\n\t")
    return cleaned[:limit]
