"""Best-effort JSON mode (OpenAI response_format) for Gemini Web."""

import json
import logging
import re
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^\s*```(?:[a-zA-Z0-9_-]+)?\s*\n([\s\S]*?)\n?\s*```\s*$")


def parse_response_format(response_format: dict | None) -> tuple[bool, dict | None]:
    """Return (enabled, schema) for OpenAI response_format."""
    if not isinstance(response_format, dict):
        return False, None
    fmt_type = str(response_format.get("type") or "").strip().lower()
    if fmt_type == "json_object":
        return True, None
    if fmt_type == "json_schema":
        js = response_format.get("json_schema")
        schema = js.get("schema") if isinstance(js, dict) else None
        return True, schema if isinstance(schema, dict) else None
    return False, None


def build_json_mode_prompt(base_prompt: str, schema: dict | None = None) -> str:
    """Wrap a chat prompt with strict JSON-only output instructions."""
    lines = [
        "You are an OpenAI-compatible assistant running behind a bridge to Gemini web.",
        "Respond with JSON only. Do not use markdown code fences and do not write any text outside the JSON.",
    ]
    if schema:
        lines.append("The reply must be a single JSON value that matches this JSON Schema:")
        lines.append(json.dumps(schema, ensure_ascii=False))
        lines.append("Set every required property.")
    else:
        lines.append("The reply must be a single JSON object, with the fields the conversation asks for.")
    lines.append("")
    lines.append("Conversation:")
    lines.append(base_prompt)
    return "\n".join(lines)


def repair_json_prompt(base_prompt: str, cause: str, schema: dict | None = None) -> str:
    """Build a single-shot repair prompt explaining why the previous JSON was invalid."""
    suffix = (
        f", matching this JSON Schema: {json.dumps(schema, ensure_ascii=False)}"
        if schema
        else ", as a single JSON object"
    )
    return (
        f"{base_prompt}\n\nYour previous reply could not be used: {cause}. "
        f"Reply again with JSON only, with no markdown code fences and no text outside the JSON{suffix}."
    )


def _strip_code_fence(text: str) -> str:
    m = _FENCE_RE.match(text)
    return m.group(1).strip() if m else text


def _escape_string_control_chars(doc: str) -> str:
    """Escape raw control characters (like unescaped newlines) inside JSON string literals."""
    out: list[str] = []
    in_string = False
    escaped = False
    for ch in doc:
        if in_string:
            if escaped:
                out.append(ch)
                escaped = False
                continue
            if ch == "\\":
                out.append(ch)
                escaped = True
                continue
            if ch == '"':
                out.append(ch)
                in_string = False
                continue
            if ch == "\n":
                out.append("\\n")
                continue
            if ch == "\r":
                out.append("\\r")
                continue
            if ch == "\t":
                out.append("\\t")
                continue
            if ord(ch) < 0x20:
                out.append(f"\\u{ord(ch):04x}")
                continue
            out.append(ch)
        else:
            if ch == '"':
                in_string = True
            out.append(ch)
    return "".join(out)


def _valid_json(doc: str) -> str:
    try:
        json.loads(doc)
        return doc
    except Exception:
        pass
    escaped = _escape_string_control_chars(doc)
    if escaped != doc:
        try:
            json.loads(escaped)
            return escaped
        except Exception:
            pass
    return ""


def _extract_first_json_object(text: str) -> str:
    if not text.startswith("{"):
        return ""
    depth = 0
    in_string = False
    escaped = False
    for idx, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[: idx + 1]
    return ""


def extract_json_reply(text: str) -> str:
    """Extract a valid JSON document from a model reply, stripping code fences or surrounding prose."""
    trimmed = (text or "").strip()
    if not trimmed:
        return ""
    forms = [trimmed]
    unfenced = _strip_code_fence(trimmed)
    if unfenced and unfenced != trimmed:
        forms.append(unfenced)

    for form in forms:
        doc = _valid_json(form)
        if doc:
            return doc

    for form in forms:
        rest = form
        while True:
            start = rest.find("{")
            if start < 0:
                break
            obj = _extract_first_json_object(rest[start:])
            if not obj:
                break
            doc = _valid_json(obj)
            if doc:
                return doc
            rest = rest[start + len(obj):]
    return ""


def _json_type_of(value) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "boolean"
    if value is None:
        return "null"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return ""


def validate_json_reply(text: str, schema: dict | None = None) -> tuple[str, str | None]:
    """Validate reply against response_format. Returns (cleaned_json, error_message)."""
    cleaned = extract_json_reply(text)
    if not cleaned:
        return "", "the reply is not valid JSON"
    parsed = json.loads(cleaned)
    actual = _json_type_of(parsed)

    if not schema:
        if actual != "object":
            return "", f"the reply is a JSON {actual}, not a JSON object"
        return cleaned, None

    want = str(schema.get("type") or "").strip().lower()
    if want:
        matches = (want == actual) or (want == "number" and actual == "integer")
        if not matches:
            return "", f"the reply is a JSON {actual}, want {want}"

    required = schema.get("required")
    if isinstance(required, list) and required:
        if not isinstance(parsed, dict):
            return "", f"the reply is a JSON {actual}, want a JSON object with {', '.join(map(str, required))}"
        for key in required:
            if key not in parsed:
                return "", f'the reply is missing required key "{key}"'

    return cleaned, None


async def ensure_json_reply(
    prompt: str,
    text: str,
    schema: dict | None,
    regenerate: Callable[[str], Awaitable[str]],
) -> str:
    """Validate reply and issue at most one repair request if invalid; falls back to raw text."""
    cleaned, err = validate_json_reply(text, schema)
    if err is None:
        return cleaned

    logger.debug("response_format reply was not valid JSON: %s", err)
    try:
        repaired = await regenerate(repair_json_prompt(prompt, err, schema))
    except Exception as regen_err:
        logger.warning("response_format repair request failed; returning raw reply: %s", regen_err)
        return text

    cleaned_retry, retry_err = validate_json_reply(repaired, schema)
    if retry_err is not None:
        logger.warning(
            "Gemini reply still does not match response_format after one repair attempt; returning raw reply: %s",
            retry_err,
        )
        return text
    return cleaned_retry
