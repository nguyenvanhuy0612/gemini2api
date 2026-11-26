# Customizations & Upstream Tracking

This repository is a customized fork/monorepo built on top of `xwteam/gemini2api`.

## Upstream Sources

1. **Backend Service (upstream)**: https://github.com/xwteam/gemini2api (currently synced to `v1.6.57`, commit `fc8936a`)
2. **Chrome Extension**: https://github.com/xwteam/gemini2api-plugin (`v1.4.0`, commit `c932706`)

## Changes Compared to Upstream

1. **Forked from Upstream (`xwteam/gemini2api`)**:
   - Kept `upstream` pointing to `https://github.com/xwteam/gemini2api.git` and `origin` pointing to `https://github.com/nguyenvanhuy0612/gemini2api.git`.

2. **Default English README & Web Console Locale**:
   - Set root `README.md` to English by default (derived from `docs/en/README.md`).
   - Changed default Web Console language in `static/app/i18n.js` from `zh-CN` to `en-US` (keeping upstream source files/comments untouched to minimize merge conflicts).

3. **Bundled Chrome Extension (`extension/`)**:
   - Cloned `xwteam/gemini2api-plugin` (`v1.4.0`) into `extension/` and set `default_locale: "en"` in `extension/manifest.json`.
   - Removed `extension/` from `.gitignore` so both backend and extension are tracked in one monorepo.

4. **DevTools Application Tab TSV Cookie Fallback**:
   - Added upfront TSV format detection in `app/core/fingerprint/cookie_jar.py` (`_parse_tsv_cookie_table`) and `static/app/app.js` (`_cookieFromHeader`), allowing users to paste cookie tables copied directly from Chrome DevTools `Application -> Storage -> Cookies` without breaking standard HTTP `Cookie:` header parsing.

5. **Playground Session Continuation & Plain Single-Turn Prompt Fixes**:
   - `static/app/app.js`: Generates and reuses a UUID for `_pgConversationId` in `sendPlaygroundRequest()` across turns until `New Chat` is clicked, keeping a single Gemini Web session instead of opening a new session on every message.
   - `app/utils/prompt.py` + routers (`openai.py`, `claude.py`, `gemini.py`, `responses.py`): Added `build_initial_prompt()` so a single-turn user message without `system` instructions or `tool_prompt` is sent as plain text without the `"Human: "` prefix.
   - `app/utils/tools.py`: `estimate_tokens()` returns `max(1, len(text) // 4)` for non-empty strings.

6. **JSON `response_format` Mode & Repair**:
   - `app/utils/json_mode.py` + `app/routers/openai.py`: Added `json_object` / `json_schema` prompt wrapping, markdown fence stripping, control-character escaping, and single-shot repair retry on Gemini Web.
   - `docs/PORTING_NOTES.md`: Reference notes from `ntthanh2603/gemini-web-to-api` for Canvas (`-canvas`), Video, Music (`-music`), and Redo stream retry.
