# Local Teams Mention Alert — Mini Project Plan

## Goal

Build a small Windows desktop companion that runs locally, detects when my name
is spoken during a Microsoft Teams meeting, and shows a short local
notification explaining the surrounding context.

## Security and compliance boundary

- Obtain written approval from the employer and meeting owner before testing.
- Follow applicable recording, monitoring, privacy, and data-retention laws.
- Show a clear **Start**, **Pause**, and **Stop** control; never run hidden or
  automatically at Windows startup.
- Process meeting audio only on the local machine. Do not use cloud APIs,
  third-party meeting bots, Teams Graph transcript storage, telemetry, or
  external analytics.
- Display a visible notice while capture is active, and stop immediately when
  the meeting ends or the user presses Stop.
- Keep only a short in-memory rolling buffer. Save nothing by default.
- If an alert is generated, retain only the minimum text needed, encrypt it
  locally, and delete it automatically after 24 hours.
- Do not bypass Teams security controls or disable organizational recording
  indicators. Treat this as a personal assistant, not a covert recorder.

## Minimal design

1. **Audio input:** capture Teams output through an approved Windows loopback
   or accessibility interface; do not capture the microphone unless required.
2. **Speech-to-text:** run a local Whisper/faster-whisper model.
3. **Mention detection:** normalize the transcript and match my name plus
   approved variants; require confirmation in a short context window to reduce
   false alerts.
4. **Context summary:** send only the matched local transcript window to a
   local Ollama model and request a 1–2 sentence factual summary. The model
   must not invent actions, decisions, or names.
5. **Alert:** show a Windows notification containing the speaker-independent
   summary, timestamp, and a link to the local event if one was retained.

## Build sequence

1. Create a Python 3.11 virtual environment and install only the required
   local audio, speech-to-text, notification, and Ollama packages.
2. Implement audio capture with an explicit permission/status indicator.
3. Add local transcription with a bounded queue and back-pressure; never let
   audio accumulate without limit.
4. Add name matching, context-window extraction, and duplicate-alert cooldown.
5. Add local summarization with a strict prompt and a safe fallback:
   **“Your name was mentioned; review the meeting context.”**
6. Add encrypted, 24-hour temporary event storage and a **Delete all data**
   control.
7. Package a local configuration file for name variants, model paths, buffer
   duration, retention, and notification preferences. Keep secrets out of it.

## Verification checklist

- Confirm network access is blocked or absent while the app is running.
- Confirm no raw audio or transcript remains after Stop and retention cleanup.
- Test exact, partial, repeated, and similar-name mentions.
- Test false positives, silence, noisy audio, model failure, and Teams ending.
- Confirm alerts contain no more transcript than necessary and no fabricated
  explanation.
- Confirm the app cannot start capture without the user pressing Start.
- Obtain final employer/privacy approval before real meetings; use synthetic
  audio for development.

## Definition of done

The app runs locally, detects a test mention within a few seconds, produces a
short accurate notification, survives expected failures without data buildup,
and passes the verification checklist with no network transmission or
unapproved persistence.
