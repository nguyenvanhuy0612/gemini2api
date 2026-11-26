"""Tests for build_initial_prompt (no Human: prefix on single user turn) and Playground session ID."""

from pathlib import Path

from app.utils.prompt import build_initial_prompt


class TestBuildInitialPrompt:
    def test_single_user_string_omits_human_prefix(self):
        out = build_initial_prompt([{"role": "user", "content": "Hello Gemini"}])
        assert out == "Hello Gemini"

    def test_single_user_multimodal_list_omits_human_prefix(self):
        out = build_initial_prompt([
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Line 1"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}},
                    {"type": "text", "text": "Line 2"},
                ],
            }
        ])
        assert out == "Line 1\nLine 2"

    def test_with_system_keeps_role_prefixes(self):
        out = build_initial_prompt([{"role": "user", "content": "hi"}], system="Be concise")
        assert out == "System: Be concise\n\nHuman: hi"

    def test_multi_turn_keeps_role_prefixes(self):
        out = build_initial_prompt([
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
        ])
        assert out == "Human: u1\n\nAssistant: a1\n\nHuman: u2"

    def test_with_tool_prompt_keeps_role_prefixes(self):
        out = build_initial_prompt([{"role": "user", "content": "x"}], tool_prompt="TOOLS")
        assert out == "Human: x\n\nTOOLS"


def test_playground_generates_conversation_id():
    repo_root = Path(__file__).resolve().parents[2]
    app_js = (repo_root / "static" / "app" / "app.js").read_text(encoding="utf-8")
    assert "if (!_pgConversationId)" in app_js
    assert "crypto.randomUUID" in app_js
