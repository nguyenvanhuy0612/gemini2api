"""Tests for JSON response_format prompt wrapping, extraction, validation, and 1-shot repair."""

import pytest

from app.utils.json_mode import (
    build_json_mode_prompt,
    ensure_json_reply,
    extract_json_reply,
    parse_response_format,
    validate_json_reply,
)


def test_parse_response_format():
    assert parse_response_format(None) == (False, None)
    assert parse_response_format({"type": "text"}) == (False, None)
    assert parse_response_format({"type": "json_object"}) == (True, None)
    schema = {"type": "object", "required": ["answer"]}
    assert parse_response_format({"type": "json_schema", "json_schema": {"schema": schema}}) == (True, schema)


def test_extract_json_reply_strips_fence_and_prose():
    raw = 'Here is your JSON:\n```json\n{"ok": true, "n": 1}\n```'
    assert extract_json_reply(raw) == '{"ok": true, "n": 1}'


def test_extract_json_reply_escapes_raw_newlines():
    raw = '{"msg": "line1\nline2"}'
    assert extract_json_reply(raw) == '{"msg": "line1\\nline2"}'


def test_validate_json_reply_checks_schema_required_keys():
    schema = {"type": "object", "required": ["id", "name"]}
    cleaned, err = validate_json_reply('{"id": 1}', schema)
    assert cleaned == ""
    assert 'missing required key "name"' in err

    cleaned2, err2 = validate_json_reply('{"id": 1, "name": "a"}', schema)
    assert err2 is None
    assert cleaned2 == '{"id": 1, "name": "a"}'


@pytest.mark.anyio
async def test_ensure_json_reply_repairs_once_on_invalid_json():
    calls = []

    async def fake_regen(repair_prompt: str) -> str:
        calls.append(repair_prompt)
        return '{"fixed": true}'

    prompt = build_json_mode_prompt("return json")
    out = await ensure_json_reply(prompt, "not json at all", None, fake_regen)
    assert out == '{"fixed": true}'
    assert len(calls) == 1


@pytest.mark.anyio
async def test_ensure_json_reply_returns_raw_after_failed_repair():
    async def fake_regen(_prompt: str) -> str:
        return "still broken"

    out = await ensure_json_reply("p", "raw bad", None, fake_regen)
    assert out == "raw bad"
