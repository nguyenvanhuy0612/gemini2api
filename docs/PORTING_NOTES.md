# Porting Notes from `ntthanh2603/gemini-web-to-api`

Reference notes captured from `https://github.com/ntthanh2603/gemini-web-to-api` for features not yet ported into this fork.

---

## 1. Canvas (`-canvas` model suffix)

- **Model routing**: Strip `-canvas` suffix (e.g. `gemini-auto-canvas`, `gemini-pro-canvas`) and enable Canvas tool mode in `StreamGenerate`.
- **Payload layout (`applyWebClientInner` + `applyCanvasInner`)**:
  - Extend `inner` array in `f.req` to length `99`.
  - Base web client fields:
    - `inner[30] = [4, 16]`
    - `inner[68] = 2`
    - `inner[91] = 0`
    - `inner[96] = 0`
    - `inner[98] = 1`
  - Canvas tool mode fields:
    - `inner[49] = 2` (`geminiCanvasToolMode`)
    - `inner[67] = 0`
- **Response parsing (`extractCanvases`)**:
  - Read `candidate[30]`, where each entry is `[id, _, title, _, content, ..., fileName(9), kind(10), ..., details(14), ...]`.
  - `kind == 2` means `code`, otherwise `document`.
  - `details[1]` or `details[4]` holds the language name.
  - Note: `gemini2api` already parses `last_canvases` in `generate_stream`, so only the `-canvas` suffix routing + `inner[49] = 2` payload extension is needed to trigger it explicitly.

---

## 2. Video Generation (`client.videos` / `generate_videos`)

- **Payload layout**:
  - Apply `applyWebClientInner(inner)`.
  - `inner[49] = 11` (`geminiVideoToolMode`).
  - Aspect ratio at `inner[0][9][6][0][3]`: `1` = Landscape (`16:9`, 1280x720), `2` = Portrait (`9:16`, 720x1280).
- **Async Polling**:
  - Gemini Web generates video asynchronously. After `StreamGenerate` returns conversation IDs (`cid`, `rid`, `rcid`), poll the conversation every ~10 seconds (timeout 5–10 minutes) using `batchexecute?rpcids=hNvQHb` (`geminiReadConversationRPC`).
- **Response extraction**:
  - Read `candidate[12]` -> JSPB field `60` (`geminiVideoCardField`, index 59 or sparse map key `"60"`).
  - Download the MP4 using the active session cookies (max ~100 MB).

---

## 3. Music Generation (`-music` model suffix / `client.audio.speech`)

- **Payload layout (`applyMusicInner`)**:
  - Apply `applyWebClientInner(inner)`.
  - `inner[45] = nil` (allow recovery from saved conversation if stream fails).
  - `inner[49] = 21` (`geminiMusicToolMode`).
  - `inner[67] = 0`.
  - Option codes in `inner[0][9][6] = [null, null, [lengthCode, vocalsCode]]` and chip IDs in `inner[55] = [[chipIDs]]`:
    - Length: `short` -> `[4, 42]`, `standard` -> `[5, 43]`.
    - Vocals: `instrumental` -> `[1, 26]`, `vocals` -> `[2, 27]`.
    - Genre chips: `pop: 44`, `hip-hop: 45`, `rock: 46`, `k-pop: 40`, `latin: 55`, `electronic: 47`, `r&b: 48`, `country: 49`, `afrobeats: 56`, `reggae: 57`, `jazz: 50`, `classical: 52`, `folk: 54`, `lo-fi: 51`, `acoustic: 53`, `cinematic: 36`, `ambient: 68`.
- **Async Polling & Download**:
  - Same `batchexecute?rpcids=hNvQHb` polling loop (~10s interval, 5 min timeout), then download audio with session cookies (max ~50 MB).

---

## 4. Redo Retry on Stalled Streams (`_reqid` refresh)

- **What `gemini2api` already has**:
  - `app/core/gemini_client.py` (`generate_stream`) tracks `GenerationStalled` using per-family timeout budgets that ignore Google's empty `wrb.fr` keepalive frames, and `account_pool` fails over / retries on `GenerationStalled` and canned refusal replies.
- **Additional enhancement from `ntthanh2603`**:
  - Separate configurable `first_response_timeout` (e.g. 180s) vs `stream_idle_timeout` (e.g. 60s after first content frame) in `readGenerateStream`, and always incrementing/generating a fresh `_reqid` on every retry attempt (matching Gemini Web's "Redo" button).
