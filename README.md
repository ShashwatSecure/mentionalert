# MentionAlert

MentionAlert is a small local app for meetings that answers the timeless question: **"Wait, did they just say my name?"**

It listens to the audio coming out of your computer, turns short bits of speech into text with Whisper, and watches for your name. When it hears it, the app pops up an alert showing what was said. A local Ollama model then gives you a short summary of the context, so you can figure out whether someone needs you, mentioned you in passing, or was simply discussing the alphabet.

Everything happens on your PC:

- Audio is processed in short chunks and is not saved.
- Speech recognition uses a local Whisper model.
- Summaries use a local Ollama model.
- Alerts are stored locally and encrypted, with old alerts cleaned up automatically.

It is mainly designed for Teams meetings, but it can listen to any audio playing through the selected Windows output device. Start it with `run.bat`, tick the consent box, and let it quietly keep one ear on the meeting while you get on with your work.

For the step-by-step usage guide, setup details, troubleshooting, and other useful information, see [`manual.md`](manual.md).

One important grown-up footnote: this app processes other people's speech. Get the right approval, follow your workplace rules and local privacy laws, and tell meeting participants before using it in a real meeting. For testing, use synthetic audio.
