# MentionAlert — User Manual

MentionAlert listens to the audio **playing on your PC** (your Teams meeting), turns it into text
on your PC, and when someone says **your name** it pops up an alert with a short explanation of
why you were mentioned. Nothing is sent anywhere.

---
## 1. Quick start (3 steps)
1. **Double-click `run.bat`** (in `CoolRoute\MentionAlert\`). A console and the app window open.
2. In the window: check your name(s) → **tick the consent box** → click **Start**.
   First start takes ~10–20 s ("LOADING MODEL…"), then it shows **● LISTENING**.
3. Join your Teams meeting as usual. When your name is said, a pop-up appears on top of everything
   with a beep, first showing what was heard, then (a few seconds later) the summary.

Stop with **Stop** (or close the window). Everything is already installed; you do not need `setup.bat`
unless you move the folder to another PC.

Before the first real meeting: **get your employer's approval and tell participants** (see §9).

## 2. The window
| Item | Meaning |
|---|---|
| Consent tick-box | Start stays disabled until you tick it. You are confirming approval/consent. |
| My name(s) + **Save** | Comma-separated names/variants, e.g. `Alex, Lex`. Only editable while stopped. |
| Status line | `○ STOPPED`, `◔ LOADING MODEL…`, `● LISTENING` (red), `❚❚ PAUSED`. |
| **Start / Pause / Stop** | Pause = stop listening but keep the model loaded; buffers are wiped. Stop = also unloads everything. |
| Stats | Audio chunks processed; "dropped" = chunks discarded because the PC couldn't keep up. |
| Live transcript box | Optional (tick to show). Display only, kept in memory, never saved. |
| Recent alerts | Last 20 saved alerts (decrypted for display). |
| **Purge expired now** | Removes alerts older than 24 h immediately. |
| **Delete ALL data** | Deletes every saved alert **and** the encryption key. |

Auto-stop: capture stops by itself after **10 min of silence**, or **1 min after Teams closes**
(only if Teams was seen running during the session).

## 3. How it works (the pipeline)
```
Teams audio on speakers ─► loopback capture (RAM, 5 s chunks) ─► Whisper speech-to-text (local)
   ─► name matching ─► [pop-up with the heard sentence] ─► wait ~8 s for follow-up words
   ─► Ollama LLM (local) writes a 1–2 sentence summary ─► pop-up updates ─► encrypted alert saved
```
- Audio is **never written to disk**. Each 5-second chunk is transcribed and discarded.
- The last 45 s of transcript text is kept **in memory only** (as context) and wiped on Pause/Stop.
- A 30 s cooldown prevents repeated alerts for the same moment.

## 4. Models used (and why)
| Job | Model | Size | Where stored |
|---|---|---|---|
| Speech-to-text | **Whisper `base.en`** via faster-whisper (CPU, int8) | ~141 MB | `MentionAlert\models\` |
| Summary | **Ollama `qwen2.5:3b`** (Qwen 2.5, 3 B parameters) | 1.9 GB | `%USERPROFILE%\.ollama\models\` |

Why: small CPU-friendly models were chosen. `base.en` is English-only and fast; `qwen2.5:3b` follows
instructions well at small size and doesn't emit "thinking" text.
Upgrades (edit `config.json`): `"whisper_model": "small.en"` (more accurate, slower; re-run
`.\.venv\Scripts\python -m mentionalert download-models`), or another Ollama model
(`ollama pull <name>` then set `"ollama_model"`). For non-English, use a multilingual model (`"base"`) and
set `"language"` to the code or `""` for auto.

If Ollama isn't running, summaries fall back to a plain extract: *Mentioned in: "…the sentence…"*.
If even that is empty: *"Your name was mentioned; review the meeting context."*

## 5. Where everything is saved
All paths are under the MentionAlert project folder unless noted.

| What | Location | Notes |
|---|---|---|
| Settings | `config.json` | Plain text; no secrets in it |
| Whisper model | `models\` | Downloaded once |
| Alert history | `data\events.enc` | **Encrypted** (Fernet/AES). Holds only: time, the matched sentence(s) (≤300 chars), the summary. Auto-deleted after 24 h |
| Encryption key | `data\key.bin` | Wrapped with **Windows DPAPI** — only usable by your Windows login on this PC |
| Audio | *nowhere* | RAM only |
| Full transcript | *nowhere* | RAM only (last 45 s); optionally displayed on screen, never saved |
| Python environment | `.venv\` | Libraries |
| Ollama program / models | `%LOCALAPPDATA%\Programs\Ollama`, `%USERPROFILE%\.ollama` | Outside the project folder |

⚠ `data\events.enc` is encrypted and the key is DPAPI-bound, so synced copies are unreadable elsewhere,
but the *encrypted file itself* may still sync. Keep the project data folder out of shared sync locations
if that matters for your setup.

## 6. Privacy & security — nothing hidden
- **Network:** at start the app enables an in-code guard (`netguard.py`) that raises an error for any
  connection to anything other than `127.0.0.1`/`localhost`. Verify with
  `.\.venv\Scripts\python -m mentionalert check` ("netguard blocks external network access").
- The only internet use was **one-time downloads**: the Whisper model (Hugging Face), the Ollama installer
  and `qwen2.5:3b` (ollama.com).
- **Ollama itself is separate software.** It runs a local server on `127.0.0.1:11434` and its tray app starts
  with Windows. MentionAlert's guard doesn't control Ollama's own behaviour (e.g. it may check for updates).
  Quit it from the tray icon if you want it off; the app still works with the offline fallback.
- **What audio is captured:** *all sound going to your default output device* (Teams, but also music,
  videos, other apps). Your own voice is not captured (it's a microphone, not an output). The app does not
  touch your microphone.
- **Visible:** while running, the window shows a red **● LISTENING**, and a console window stays open.
  It never starts by itself, never auto-runs at Windows startup, and needs the consent tick each launch.
- **Logs:** the app writes no transcript logs.
- Third-party code: faster-whisper, soundcard, cryptography, numpy (all open source, installed from PyPI).

## 7. Settings (`config.json`)
| Key | Default | Meaning |
|---|---|---|
| `names` | [] | Names to react to (the first is used in the summary prompt) |
| `fuzzy_threshold` | 0.84 | Tolerance to speech-recognition spelling errors (names under 5 letters must match exactly). Lower = more alerts/false alarms |
| `whisper_model`, `language` | base.en, en | Speech model and language |
| `chunk_seconds` | 5 | Audio chunk length (lower = faster alerts, less accurate) |
| `silence_rms` | 0.004 | Volume below which a chunk is treated as silence and skipped |
| `queue_max_chunks` | 6 | Max audio chunks waiting; oldest dropped when full (bounds memory) |
| `context_seconds` | 45 | How much recent transcript is used for the summary |
| `post_roll_seconds` | 8 | Wait after the name to capture what's asked of you |
| `cooldown_seconds` | 30 | Minimum gap between alerts |
| `ollama_enabled`, `ollama_url`, `ollama_model`, `ollama_timeout_seconds` | true, http://127.0.0.1:11434, qwen2.5:3b, 90 | Summary LLM |
| `save_events` | true | Set false to save **nothing at all** (alerts only on screen) |
| `retention_hours` | 24 | Auto-delete age for saved alerts |
| `speaker_name` | "" | Part of the output device name to capture; "" = Windows default |
| `auto_stop_silence_minutes` | 10 | Auto-stop after this much silence (0 = off) |
| `stop_when_teams_closed` | true | Auto-stop 1 min after Teams closes |
| `show_live_transcript_default` | false | Tick the transcript box at startup |

Edit while the app is stopped, then restart it.

## 8. Commands (optional)
Run from `MentionAlert\` in PowerShell (`.\.venv\Scripts\python -m mentionalert <command>`):
| Command | Does |
|---|---|
| `gui` (default) | Open the app (same as `run.bat`) |
| `check` | Verifies network guard, model, Ollama and audio devices |
| `list-devices` | Lists output devices (use a part of a name in `speaker_name`) |
| `text "some sentence"` | Tests name detection + summary without audio |
| `file C:\path\test.wav` | Runs a WAV through the whole pipeline |
| `download-models` | (Re)download the Whisper model |
Tests: `.\.venv\Scripts\python -m pytest -q`.

## 9. Compliance — please read
This records/transcribes other people's speech, even though only on your PC. Before real use: get
written approval from your employer/IT/security, follow local recording and privacy law, and tell the
participants (or have consent). Do not use it to evade organisational controls. For first tests use
synthetic audio (see `steps.md`).

## 10. Limitations / honest notes
- **Accuracy:** small models make mistakes, especially with accents, crosstalk, or unusual names. Listing
  spelling variants in `names` and `initial_prompt` biasing help. The summary is only as good as the
  transcript; if unclear it says so. Treat alerts as a prompt to check, not as fact.
- **Delay:** roughly 5–10 s for the pop-up, ~10–15 s more for the summary (CPU).
- **No speaker names:** it can't tell you *who* said your name.
- **Output device:** you must hear the meeting on the device it captures. If Teams uses another device than
  the Windows default, set `speaker_name`. Loopback captures what is sent to the device; I did not test
  how it behaves with muted/zero volume, so keep the meeting audible.
- **Audio device:** capture works when the meeting is playing through the selected output device.
- **Heavy CPU:** transcription uses CPU while a meeting is on; if "dropped" grows, switch to `tiny.en` or a longer `chunk_seconds`.
- Pop-ups are set to stay on top, but I did not test them over full-screen shared content.

## 11. Troubleshooting
| Problem | Fix |
|---|---|
| Start is greyed out | Tick the consent box; make sure status is STOPPED or PAUSED |
| "Could not load speech model" | Run `setup.bat` (re-downloads model) |
| No alerts, stats "Chunks processed" not rising | Wrong output device → `list-devices`, set `speaker_name` |
| Chunks rise but no alert | Tick "Show live transcript" to see what's heard; add spelling variants to names; lower `fuzzy_threshold` slightly (e.g. 0.8) |
| Summary only shows the sentence | Ollama is not running → start "Ollama" from the Start menu; check with `check` |
| Too many "dropped" | Use `tiny.en`, or close heavy apps |
| Want to wipe everything | **Delete ALL data** button, or delete `data\` |
| Uninstall | Delete the `MentionAlert` folder; uninstall Ollama from Windows Settings → Apps; delete `%USERPROFILE%\.ollama` |

## 12. Moving to another PC
Copy the folder without `.venv`, `models`, `data`, then run `setup.bat` (needs Python 3.11+ and internet once).
