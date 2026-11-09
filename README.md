# Claude Video Review Skill

Claude Code can make a video, but it cannot watch or hear the result. This Claude Code skill reviews the finished video before you publish it with three AI reviewers: **Jev by TypeSafe AI** checks every frame, **Gemini** watches the video with its sound, and **GPT** reviews still frames. Measurement scripts check what models miss, and Claude receives a verdict and a list of problems with timestamps and a fix for each one.

**Install guide, sample report and the full method: https://www.arkya.ai/claude-video-review-skill**

## How Jev, Gemini and GPT review your video

| Layer | Tools | What it catches |
|---|---|---|
| 1. Measure | ffmpeg, Python, OpenCV, Whisper | loudness against -14 LUFS, true peak, clicks, silences, black and frozen frames, duplicated frames (judder), jumps at clip seams, transcript against the script |
| 2. Check every frame | Jev by TypeSafe AI | wrong face against the reference sheet, extra person, mouth talking in a silent shot, broken hands, garbled text, a key action that never happens |
| 3. Watch and listen, blind | Gemini with sound, GPT on still frames | first reaction, timestamped rubric, audio-only pass, story retell, sound-off watch, seven personas |
| 4. Confirm and decide | Claude | confirms a problem when a measurement and a reviewer agree, two reviews agree, or the frames show it; verdict SHIP, FIX, REJECT or INCONCLUSIVE |

A 30-second video at 24 fps has 720 frames, and most AI generation glitches last one to four frames, so the skill checks every frame instead of a sample. It finds problems such as a mouth moving in a shot with no dialogue, a clip slowed down to fit the music, a face that changes for a few frames, clicks at edits, and captions that cover a face.

The reviewers never see the script or the build history. Claude coordinates the review and makes the fixes; independent models do the judging.

## Bring your own keys

The skill runs on your machine with your own accounts. It ships with no keys, and you pay each provider directly for your own use.

| Service | What it does | How to connect it |
|---|---|---|
| Gemini (required) | Watches the full video with its sound | `GEMINI_API_KEY` in the skill folder's `.env` ([create a key](https://aistudio.google.com/apikey)) |
| Jev by TypeSafe AI (recommended) | Checks every frame against the character reference sheets | `TYPESAFE_API_KEY` in the same `.env` ([create a key](https://console.typesafe.ai)) |
| GPT through the Codex CLI (recommended) | Reviews still frames as a second reviewer | your own OpenAI sign-in: `codex login` |

Copy `.env.example` to `.env` and fill in your keys. `.env` is in `.gitignore`, so your keys stay out of version control.

## Other requirements

- Claude Code
- Python 3.10+ and ffmpeg

## Quick install

```bash
git clone https://github.com/Arkya-AI/claude-video-review-skill ~/.claude/skills/video-review
cd ~/.claude/skills/video-review && pip install -r requirements.txt
cp .env.example .env    # then add your GEMINI_API_KEY and TYPESAFE_API_KEY
```

Then ask Claude Code: "Review final.mp4 with the video-review skill. Audience: founders who watch LinkedIn on their phone. Platform: LinkedIn feed."

The step-by-step guide, the brief template and a real repair list are on the [project page](https://www.arkya.ai/claude-video-review-skill).

## What is in the repo

- `SKILL.md`: the review, step by step
- `references/checklist.md`: 16 groups, each judged from the viewer's chair and the editor's chair, plus the hard blockers
- `references/perceptual-defects.md`: every defect a viewer notices on a phone and the check that finds it
- `references/staged-reviews.md`: script and visuals gates for scripted videos
- `prompts/`: the blind pass prompts
- `scripts/`: `tech_qc.py`, `frame_use.py`, `gemini_watch.py`, `sample_frames.py`, `jev_frames.py`
- `examples/`: every-frame configs for a character film and a graphics reel

## Author

Built by Poorna Reddy at Arkya AI. [LinkedIn](https://www.linkedin.com/in/poornareddy/) · [Instagram: Poorna's AI Playbook](https://www.instagram.com/theaiplaybook26/)

MIT licence.
