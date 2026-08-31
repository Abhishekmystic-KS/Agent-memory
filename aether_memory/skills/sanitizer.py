"""Prompt-injection sanitizer for memory ingestion.

Strips well-known prompt-injection patterns before content reaches the LLM or memory store.
"""

from __future__ import annotations
import logging
import re
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Pattern configuration categories: instruction-override, system-tag, role-marker, jailbreak, memory-attack
_INJECTION_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    # Direct instruction overrides
    (
        re.compile(
            r"\b(?:ignore|disregard)\s+(?:all\s+)?(?:previous|prior|above|earlier|the)\s+(?:instructions?|prompts?|messages?|context|rules?)\b",
            re.IGNORECASE,
        ),
        "instruction-override",
    ),
    (
        re.compile(
            r"\bforget\s+(?:everything\s+)?(?:previous|prior|the\s+above|all\s+instructions?|what\s+(?:I|you)\s+(?:said|told))\b",
            re.IGNORECASE,
        ),
        "instruction-override",
    ),
    # Explicit "new instructions" override
    (
        re.compile(
            r"\b(?:your\s+)?new\s+(?:instructions?|task|directive|role)\s+(?:is|are)\b",
            re.IGNORECASE,
        ),
        "instruction-override",
    ),
    # System-prompt injection markers
    (re.compile(r"<\s*/?\s*system\s*>", re.IGNORECASE), "system-tag"),
    (re.compile(r"\[\s*/?\s*system\s*\]", re.IGNORECASE), "system-tag"),
    (re.compile(r"<\s*/?\s*\|im_start\|\s*>", re.IGNORECASE), "system-tag"),
    (re.compile(r"<\s*/?\s*\|im_end\|\s*>", re.IGNORECASE), "system-tag"),
    # Role injection at start of line
    (
        re.compile(r"^\s*(?:system|assistant)\s*:\s", re.IGNORECASE | re.MULTILINE),
        "role-marker",
    ),
    # Common jailbreak vocabulary
    (re.compile(r"\bDAN\s+mode\b", re.IGNORECASE), "jailbreak"),
    (re.compile(r"\bdeveloper\s+mode\b", re.IGNORECASE), "jailbreak"),
    (re.compile(r"\bjailbreak\b", re.IGNORECASE), "jailbreak"),
    # Memory-targeted destructive actions
    (
        re.compile(
            r"\b(?:delete|remove|drop|wipe|erase)\s+(?:all\s+)?(?:my\s+)?(?:memories|memory|facts|data|history|records?)\b",
            re.IGNORECASE,
        ),
        "memory-attack",
    ),
]

REDACT_MARKER = "[REDACTED]"

def detect_injection(text: str) -> List[str]:
    """Return categories of injection patterns found in text. Empty list if none."""
    if not text:
        return []
    found: List[str] = []
    for pattern, category in _INJECTION_PATTERNS:
        if pattern.search(text):
            found.append(category)
    return found

def sanitize(text: str, redact_marker: str = REDACT_MARKER) -> Tuple[str, List[str]]:
    """Strip known prompt-injection patterns and replace them with the redact marker."""
    if not text:
        return text, []
    sanitized = text
    found: List[str] = []
    for pattern, category in _INJECTION_PATTERNS:
        if pattern.search(sanitized):
            found.append(category)
            sanitized = pattern.sub(redact_marker, sanitized)
    if found:
        logger.warning("Prompt-injection patterns sanitized: %s", found)
    return sanitized, found
