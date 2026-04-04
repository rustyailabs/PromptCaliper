"""
Content guardrails applied before/after LiteLLM calls.

Supported guardrail_type values:
    keyword_block     — block/flag/rewrite if any keyword appears in content
    regex_filter      — block/flag/rewrite if a regex pattern matches
    pii_redaction     — redact PII patterns (email, phone, SSN, card numbers)
    content_filter    — block/flag/rewrite on pre-defined harm categories
    prompt_injection  — detect and block/rewrite jailbreak & injection attempts

Supported action_on_trigger values:
    block   — raise HTTP 400 (input) or replace with policy message (output)
    flag    — mark as triggered but allow through unchanged
    redact  — replace matched content in-place (PII scrubbing)
    rewrite — strip/neutralise the offending portion and allow through
"""
import logging
import re
import threading

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.models.guardrail_config import GuardrailConfig

logger = logging.getLogger(__name__)

# ── PII redaction patterns ────────────────────────────────────────────────────
PII_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b\d{16}\b"), "[CARD]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
]

# ── Content-filter category keywords ─────────────────────────────────────────
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "violence":  ["kill", "murder", "attack", "bomb", "weapon", "shoot", "stab"],
    "adult":     ["porn", "nude", "explicit", "sexual"],
    "hate":      ["hate speech", "slur", "racist", "sexist"],
    "self-harm": ["suicide", "self-harm", "cut myself"],
}

# ── Prompt-injection / jailbreak detection patterns ───────────────────────────
# Each pattern targets a distinct injection strategy. All are case-insensitive.
PROMPT_INJECTION_PATTERNS: list[re.Pattern] = [p for p in [
    # Classic "ignore instructions" family — allow up to 4 modifier words between verb and noun
    re.compile(r"ignore\s+(?:\w+\s+){0,4}instructions", re.I),
    re.compile(r"disregard\s+(?:\w+\s+){0,4}instructions", re.I),
    re.compile(r"forget\s+(everything|your\s+training|what\s+I\s+said|all\s+instructions)", re.I),
    re.compile(r"override\s+(?:\w+\s+){0,3}settings", re.I),
    re.compile(r"bypass\s+(?:\w+\s+){0,3}filter", re.I),
    re.compile(r"bypass\s+(?:\w+\s+){0,3}guard(rail|s)?", re.I),

    # Role-swap jailbreaks
    re.compile(r"\byou\s+are\s+now\s+(DAN|a\s+|an\s+)", re.I),
    re.compile(r"\bact\s+as\s+(if\s+you\s+are\s+|a\s+|an\s+)", re.I),
    re.compile(r"\bpretend\s+(you\s+are|to\s+be)", re.I),
    re.compile(r"\bdo\s+anything\s+now\b", re.I),
    re.compile(r"\bjailbreak\b", re.I),
    re.compile(r"\bDAN\s+mode\b", re.I),

    # System-prompt extraction
    re.compile(r"(repeat|print|output|show|reveal|tell\s+me)\s+(your\s+)?(system\s+prompt|initial\s+instructions)", re.I),
    re.compile(r"what\s+(are|were)\s+your\s+(original\s+|initial\s+|system\s+)?instructions", re.I),

    # Instruction injection via role labels
    re.compile(r"<\s*(system|SYSTEM)\s*>", re.I),
    re.compile(r"\[SYSTEM\]", re.I),
    re.compile(r"###\s*system\b", re.I),
]]

# Replacement used when rewriting detected injection attempts
_INJECTION_REPLACEMENT = "[prompt injection attempt removed]"

# Maximum time (seconds) allowed for a single regex match (ReDoS protection)
_REGEX_TIMEOUT_SECONDS = 1


def _safe_regex_search(pattern_str: str, text: str, name: str) -> bool:
    """
    Run re.search with a hard timeout to prevent ReDoS attacks from
    maliciously crafted patterns stored in guardrail config_json.
    """
    result = [False]
    error: list[Exception] = []

    def _run():
        try:
            result[0] = bool(re.search(pattern_str, text, re.IGNORECASE))
        except re.error as exc:
            error.append(exc)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=_REGEX_TIMEOUT_SECONDS)

    if t.is_alive():
        logger.warning(
            "Regex in guardrail '%s' timed out after %ds — possible ReDoS pattern. "
            "Treating as no-match.",
            name, _REGEX_TIMEOUT_SECONDS,
        )
        return False

    if error:
        logger.warning("Invalid regex in guardrail '%s': %s", name, error[0])
        return False

    return result[0]


def _redact_pii(text: str) -> str:
    for pattern, replacement in PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _strip_injection(text: str) -> str:
    """Remove detected prompt injection patterns from text, replacing with a safe placeholder."""
    for pattern in PROMPT_INJECTION_PATTERNS:
        text = pattern.sub(_INJECTION_REPLACEMENT, text)
    return text


def _messages_to_text(messages: list[dict]) -> str:
    return " ".join(m.get("content", "") or "" for m in messages if isinstance(m, dict))


def _detect_prompt_injection(text: str) -> bool:
    """Return True if any injection pattern matches."""
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


async def apply_input_guardrails(
    messages: list[dict], db: AsyncSession
) -> tuple[list[dict], bool, list[str]]:
    """
    Apply all active input guardrails.

    Returns:
        (processed_messages, any_triggered, triggered_by_names)

    Actions:
        block   — raises HTTP 400 immediately
        flag    — marks triggered, passes through unchanged
        rewrite — strips/neutralises offending content, continues
        redact  — replaces PII in-place (pii_redaction type only)
    """
    result = await db.execute(
        select(GuardrailConfig).where(
            GuardrailConfig.is_active == True,
            GuardrailConfig.applies_to.in_(["input", "both"]),
        )
    )
    configs = result.scalars().all()

    triggered = False
    triggered_by: list[str] = []

    for config in configs:
        text = _messages_to_text(messages)
        cfg = config.config_json or {}
        action = config.action_on_trigger

        if config.guardrail_type == "keyword_block":
            keywords = cfg.get("keywords", [])
            for kw in keywords:
                if kw.lower() in text.lower():
                    if action == "block":
                        raise HTTPException(
                            status_code=400,
                            detail=f"Request blocked by guardrail: '{config.name}'",
                        )
                    if action == "rewrite":
                        messages = [
                            {**m, "content": re.sub(re.escape(kw), "[REDACTED]", m.get("content") or "", flags=re.I)}
                            if isinstance(m, dict) else m
                            for m in messages
                        ]
                    triggered = True
                    if config.name not in triggered_by:
                        triggered_by.append(config.name)

        elif config.guardrail_type == "regex_filter":
            pattern_str = cfg.get("pattern", "")
            if pattern_str and _safe_regex_search(pattern_str, text, config.name):
                if action == "block":
                    raise HTTPException(
                        status_code=400,
                        detail=f"Request blocked by guardrail: '{config.name}'",
                    )
                if action == "rewrite":
                    messages = [
                        {**m, "content": re.sub(pattern_str, "[REDACTED]", m.get("content") or "", flags=re.I)}
                        if isinstance(m, dict) else m
                        for m in messages
                    ]
                triggered = True
                if config.name not in triggered_by:
                    triggered_by.append(config.name)

        elif config.guardrail_type == "pii_redaction":
            if action in ("redact", "block", "rewrite"):
                messages = [
                    {**m, "content": _redact_pii(m.get("content") or "")}
                    if isinstance(m, dict) else m
                    for m in messages
                ]
                triggered = True
                if config.name not in triggered_by:
                    triggered_by.append(config.name)

        elif config.guardrail_type == "content_filter":
            categories = cfg.get("categories", [])
            for cat in categories:
                keywords = CATEGORY_KEYWORDS.get(cat, [cat])
                for kw in keywords:
                    if kw.lower() in text.lower():
                        if action == "block":
                            raise HTTPException(
                                status_code=400,
                                detail=f"Request blocked by content filter '{config.name}': {cat}",
                            )
                        if action == "rewrite":
                            messages = [
                                {**m, "content": re.sub(re.escape(kw), "[REDACTED]", m.get("content") or "", flags=re.I)}
                                if isinstance(m, dict) else m
                                for m in messages
                            ]
                        triggered = True
                        if config.name not in triggered_by:
                            triggered_by.append(config.name)
                        break

        elif config.guardrail_type == "prompt_injection":
            if _detect_prompt_injection(text):
                if action == "block":
                    raise HTTPException(
                        status_code=400,
                        detail=f"Request blocked by guardrail: '{config.name}' (prompt injection detected)",
                    )
                if action == "rewrite":
                    # Strip the injection patterns and let the sanitised request through
                    messages = [
                        {**m, "content": _strip_injection(m.get("content") or "")}
                        if isinstance(m, dict) else m
                        for m in messages
                    ]
                    logger.info("Prompt injection rewritten by guardrail '%s'", config.name)
                triggered = True
                if config.name not in triggered_by:
                    triggered_by.append(config.name)

    return messages, triggered, triggered_by


async def apply_output_guardrails(
    content: str, db: AsyncSession
) -> tuple[str, bool, list[str]]:
    """
    Apply all active output guardrails.

    Returns:
        (processed_content, any_triggered, triggered_by_names)
    """
    result = await db.execute(
        select(GuardrailConfig).where(
            GuardrailConfig.is_active == True,
            GuardrailConfig.applies_to.in_(["output", "both"]),
        )
    )
    configs = result.scalars().all()

    triggered = False
    triggered_by: list[str] = []

    for config in configs:
        cfg = config.config_json or {}
        action = config.action_on_trigger

        if config.guardrail_type == "pii_redaction" and action in ("redact", "rewrite"):
            content = _redact_pii(content)
            triggered = True
            if config.name not in triggered_by:
                triggered_by.append(config.name)

        elif config.guardrail_type == "keyword_block":
            keywords = cfg.get("keywords", [])
            for kw in keywords:
                if kw.lower() in content.lower():
                    if action == "block":
                        content = "[Response blocked by content policy]"
                    elif action == "rewrite":
                        content = re.sub(re.escape(kw), "[REDACTED]", content, flags=re.I)
                    triggered = True
                    if config.name not in triggered_by:
                        triggered_by.append(config.name)
                    break

        elif config.guardrail_type == "regex_filter":
            pattern_str = cfg.get("pattern", "")
            if pattern_str and _safe_regex_search(pattern_str, content, config.name):
                if action == "block":
                    content = "[Response blocked by content policy]"
                elif action == "rewrite":
                    content = re.sub(pattern_str, "[REDACTED]", content, flags=re.I)
                triggered = True
                if config.name not in triggered_by:
                    triggered_by.append(config.name)

        elif config.guardrail_type == "prompt_injection":
            # On output: if the model echoes back an injection attempt, strip it
            if _detect_prompt_injection(content):
                if action == "block":
                    content = "[Response blocked by content policy]"
                elif action == "rewrite":
                    content = _strip_injection(content)
                triggered = True
                if config.name not in triggered_by:
                    triggered_by.append(config.name)

    return content, triggered, triggered_by
