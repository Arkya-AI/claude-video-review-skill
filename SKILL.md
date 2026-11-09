---
name: video-review
description: Independent review of any finished video (reel, Short, explainer, lecture, AI avatar or AI animated film) before it is published. Measures the file, checks every frame, has Gemini watch it with sound and GPT check stills, then gives a SHIP, FIX, REJECT or INCONCLUSIVE verdict and a timestamped repair list. Use after rendering any video and before showing or publishing it.
---

# Video review

Version 2.4 · November 2026 · MIT licence · https://www.arkya.ai/claude-video-review-skill

Claude cannot play a video file with its sound, and the session that built a video cannot judge it, because it knows what it meant to make. This skill gets the finished file watched and heard by models that know nothing about the build, measures what models cannot see or hear reliably, and returns confirmed findings with fixes. It judges the story as told, the characters and design consistency, acting and expressions, motion, staging, pace and editing, transitions, voice, sound design, music, lip sync, text and captions, cliches and AI tells, and platform finish. The question is not only "is it technically clean" but "is this a good video for a person to watch", from the viewer's chair and from the editor's chair.

Run it on every video a person outside the session will watch, before you show it or publish it.

**Scope: the story is fixed.** The premise, theme, taste and what the characters choose to do are the creator's decisions. The review never judges whether a story is suitable or the right story, and never proposes a different one. It judges only how well the story is told and made.

**Why several layers.** On an AI avatar reel, Gemini correctly judged the presenter as "an AI avatar, a digital puppet", but it also reported "no clicks, glitches or jump cuts". The measurements found 11 audible clicks, judder from duplicated frames, frame-jump spikes at 11.0, 17.7 and 19.7 s, and loudness 3 LU low. GPT on stills confirmed the face jumps at 11.0 and 17.7 s. Models give the viewer's gut reaction; measurements catch fine audio and timing; neither is enough alone.

Paths below assume the skill lives in `~/.claude/skills/video-review`:

```bash
S=~/.claude/skills/video-review; PY=python3; OUT=<video-dir>/.video-review/<video-name>-<YYYYMMDD-HHMM>
```

## Step 1: Write the brief

Create `$OUT` and write `brief.md`:

- **format:** reel | short | long
- **type:** animated | lecture | avatar | graphics | mixed
- **audience:** who watches it, in their own words ("founders who watch LinkedIn on their phone")
- **purpose:** what it must achieve for them
- **platform:** Instagram Reels, YouTube Shorts, YouTube, LinkedIn, website
- **presenter brief:** "must look like a real filmed person" | "stylised character" | "no presenter"
- **story card** (story films): who, wants what, why they cannot get it, what they do, why it fails, how it ends, and the one point of the film. Used only to score the retell test; never given to the blind passes.
- **personas:** the target viewer, plus the craft personas in pass G. For personal films (birthday, wedding, gift) add the person shown and the person receiving it.
- **reference sheets** of every character and key prop: for the every-frame pass only, never given to passes A, E or F.
- **loudness target:** -14 LUFS integrated for social and YouTube unless stated.
- optional, for measurements only: the narration script (for ASR read-back). Never give it to the external reviewers.

## Step 2: Measure (L0, always)

```bash
$PY $S/scripts/tech_qc.py <video> $OUT --script <script.txt> --target-lufs -14
$PY $S/scripts/frame_use.py <video> $OUT/frame_use.json
```

`tech_qc.py` writes `tech_qc.json`, `contact_sheet.jpg` and `seams/` (before and after frame pairs at every frame-jump spike) and prints an `inspect` list: duplicated-frame share (judder), frame-jump spikes, frozen or black frames, silences, integrated loudness and true peak, click candidates, audio and video length mismatch, delivery resolution, and the transcript read back against the script. `frame_use.py` reports how much of the frame height carries content and any empty band held for 4 s or more.

Also measure where you have the tools, and mark UNKNOWN where you do not:
- **Shot table:** every cut with its time and length, from the frame-jump spikes; average shot length per third of the film.
- **Speed changes:** any shot not at 1.0x and any freeze hold over 0.5 s, from the edit data or duplicated-frame runs.
- **Phone check:** the mix through a phone-speaker filter (high-pass about 300 Hz) for intelligibility, and whether impacts still land.
- **Music map:** where the music starts, stops, peaks and goes silent (RMS every 0.5 s), laid against the shot table.

Measurements nominate moments to inspect. They are not findings until Step 6 confirms them.

## Step 2b: Check every frame (L0F, every video)

A 30-second film at 24 fps is 720 frames. The worst AI defects (a smeared contact frame, a flashed reference image, a face jump at a seam) last 1 to 4 frames, so sampling at 5 fps misses them. This pass sends every frame, with the frame before it and the reference sheets of that shot's cast, to Jev by TypeSafe through `scripts/typesafe_client.py`. Bring your own key: `TYPESAFE_API_KEY` in the environment or in the skill folder's `.env` (create one at https://console.typesafe.ai). Image requests send the `TypeSafe-Danger-Zone-Images` header that the API requires. To use another vision model, set `TYPESAFE_CLI` to a command that accepts `evaluate --request <json> --output <json>`.

```bash
$PY $S/scripts/jev_frames.py prep   <config.json>             # extract every frame; local duplicate and freeze measurement
$PY $S/scripts/jev_frames.py run    <config.json> --workers 8  # one request per frame, cached and retried
$PY $S/scripts/jev_frames.py report <config.json>             # frames.csv, summary.json, repair_list.md, flagged_sheet.jpg
$PY $S/scripts/jev_frames.py box    <config.json> --top 12    # locate the defect on the worst frames
```

The config names the video, an output folder, the setting, each character's sheet and a one-line description, and every shot with start and end seconds, cast, other people allowed, the one key action to look for, whether the shot is silent, and its playback speed if not 1.0. See `examples/config.character-film.json`. For videos without characters (boards, cards, screenshots), leave the cast empty and add the questions in `references/jev-graphics-questions.json` as `extra_questions`; see `examples/config.graphics.json`.

Per frame the checker answers: people count, unexpected person, likeness and outfit against the sheet, expression (lively, comic, frozen), mouth (closed, smile, talking), hand, face and body defects, garbled text, whether the key action is visible, and whether anything jumped against the previous frame. The report turns these into a repair list: shot, time, frame numbers, issue, suggested fix and severity. Flags use each shot's own baseline, because absolute defect scores sit around 0.5 to 0.7 even on clean frames. Runs are what matter:

- a face reading "talking" for 0.4 s or more in a silent shot. Example: a character's mouth moving for four seconds in a shot with no dialogue reads as panting.
- three or more frames not matching the sheet. Example: an adult character rendering as a child for half a second.
- 10% or more near-repeat frames in a shot, which means it was slowed. Example: a shot slowed to 0.72x to fit the music showed 25% near-repeats against 0% in shots at normal speed.
- a picture frozen for 0.5 s or more. Example: the last shot held 3.5 s under a title, measured on the top 60% of the frame so the title does not hide it.
- a key action never seen. Example: a rocket meant to leave on its own is never clearly visible, so the rescue beat reads weakly.

Cost and time: about 30,000 input tokens per frame; a 30-second film takes a few minutes with 8 workers. The checker judges single frames only; motion quality, timing, acting over time and sound stay with the passes below. Every repair item is a candidate until Step 6 confirms it, because labels can be wrong even when the moment is right (a face hidden behind a prop labelled as "face distortion" is a staging problem).

## Step 3: Talking-head metrics (L1, avatar and mixed only)

Run what is installed and mark the rest UNKNOWN; never skip silently.
- **Lip sync:** SyncNet offset and confidence per speech-only window (`joonson/syncnet_python`). SyncNet resamples to 25 fps, so offsets come in 40 ms steps.
- **Blinks:** MediaPipe eye-aspect-ratio blinks per minute and their regularity.
- **Identity:** ArcFace similarity per second against real photos of the presenter.

## Step 4: Blind passes

Each pass is a fresh call with no conversation, no project files and no explanation of the build. Every viewing prompt (A, B, E, F, G and H) carries this line after its first sentence: "SCOPE: The story, its premise, its theme and what the characters choose to do are the creator's decisions and are fixed. Do not judge whether the premise or story is suitable, safe, in good taste or the right story, and do not suggest a different story. Judge only how well this story is told and made." Fill the `{...}` fields in the prompt files from the brief. Run A before B so the first reaction is not primed by a rubric.

```bash
P=$S/prompts; W="$PY $S/scripts/gemini_watch.py"                     # GEMINI_API_KEY from env or $S/.env
$W <video> $OUT/a.txt $OUT/pass_a.md --fps 2                          # A: first reaction
$W <video> $OUT/b.txt $OUT/pass_b.json --fps 5 --json                 # B: rubric with timestamps
ffmpeg -v error -i <video> -vn -c:a aac -b:a 192k $OUT/audio.m4a
$W $OUT/audio.m4a $OUT/c.txt $OUT/pass_c.json --json                  # C: audio only
$PY $S/scripts/sample_frames.py <video> $OUT/frames --at <seam and flag times> --random 8
mkdir -p /tmp/blind-d && cd /tmp/blind-d
IMGS=$(ls $OUT/frames/*.jpg | grep -v _phone | paste -sd, -)
codex exec -s read-only --skip-git-repo-check -C /tmp/blind-d -i "$IMGS" < $OUT/d.txt > $OUT/pass_d.json   # D: GPT on stills
```

Gotchas: the `gemini` CLI fails on video uploads, so use `gemini_watch.py` (REST File API). With `-i`, Codex takes the prompt from stdin; a prompt passed as an argument after `-i` is read as an image path. Run Codex from an empty folder: started inside a project it reads project files and earlier reports, which breaks the blind pass.

- **A and B, Gemini** (`gemini-3.1-pro-preview` by default): the frontier API that takes video with its audio and answers with timestamps. fps 5 for videos up to 60 s, fps 2 up to 5 minutes. For long-form, review overlapping 3-minute chunks (15 s overlap) at fps 2, and run pass A once on the whole video. Record which seconds each pass covered.
- **C, audio only:** removes the picture so the model cannot hear with its eyes. With narration it judges voice naturalness, pronunciation and mix. For a wordless film, ask instead: "List every sound in order with MM:SS.s: what it is, where it starts and stops, how loud it is against the rest. Then list every stretch where the track goes thin or dead, every sound that piles on another, and every vocal and the emotion it carries." It cannot hear fine clicks; those come from Step 2.
- **D, GPT via Codex on stills:** a second company's model. It gets random frames mixed with flagged ones without being told which, plus face crops and phone-size copies, and judges anatomy, fingers, skin, eyes, teeth, legibility, safe zones and face consistency between consecutive frames. For graphics videos use `prompts/pass_d_graphics.txt`. It never judges motion, timing or sound.
- **E, retell:** "Watch this once. Then tell me the story in order in five sentences or fewer: who it is about, what they want, what goes wrong, what they do, how it ends. Then say the one feeling you were left with. If you could not follow something, say where (MM:SS)." PASS when who, want, obstacle and ending match the story card. Example of a PASS: "A girl wants to jump into the pool, her parents say no, she does it anyway and soaks them."
- **F, sound off:** the video with audio removed (`ffmpeg -i <video> -an -c:v copy <out>`). "With no sound, what happens, who holds power in each scene, and where were you confused (MM:SS)?" Fails when story beats or gags only work with sound; most feeds play muted.
- **G, persona panel:** pass A once per persona, changing only `{AUDIENCE}`: (1) the target viewer; (2) a scroller who decides in 3 seconds; (3) a film editor judging pace, holds, cut points, transitions and screen direction; (4) an animation director judging acting, expressions, eyes, timing, staging and consistency; (5) a sound designer and composer judging layers, silence, music entry and build, mix and phone playback; (6) a jaded critic who has seen thousands of AI videos, asked to name every cliche, AI tell and generic choice; (7) for personal films, the person shown and the person receiving it. Each returns keep watching or not, three things that worked, three that did not with MM:SS, and a score from 1 to 5. A persona score driven by the premise rather than the execution is out of scope: re-run that persona with the scope line.
- **H, sound-to-picture map** (films with effects or vocals): every on-screen action that should make a sound has it within 2 frames; no stretch of 0.5 s or more with effects and voice both below -50 dB while something on screen should be heard; every vocal plays on the face that makes it; no doubled event; the biggest hit lands on the frame where the action peaks.
- **I, expression-to-beat:** from the story card, the one emotion each visible character should show in each shot. Mark any run of 0.3 s or more where a face shows a different emotion (smiling during danger), any expression that flips with no cause, and any face frozen 0.8 s or more with no blink or eye move.
- **N, new viewer:** `prompts/pass_n_new_viewer.txt`. Every unbridged jump, every term used before it is explained, every missing step the viewer needs to act. Example of a FAIL: a reel that jumps from "three routes to sit the exam" to "80 supplier documents" with no bridge.

Never use Claude as an external reviewer of a video Claude built, and never accept an LLM verdict on lip sync without the Step 3 measurement.

## Step 5: Content review

Review the words separately: the ASR transcript, the on-screen text in order with timestamps, and the post caption, read by a different model from the one that wrote them. Its findings go into the report under group 2.

## Step 6: Confirm, adjudicate, score

Walk the perceptual defect catalogue (`references/perceptual-defects.md`) line by line: each defect gets PASS, FAIL or UNKNOWN with the check that decided it. Then go through `references/checklist.md` group by group. Every item ends as PASS, FAIL, UNKNOWN or N/A, and every group gets a viewer score and an editor score from 1 to 5. An item no pass or tool covered is UNKNOWN; any UNKNOWN in groups 1, 4, 7, 8, 9 or 10 makes the verdict INCONCLUSIVE.

A finding is **confirmed** when one of these holds, with the evidence file linked in the report:
1. a measurement and an external model point to the same moment;
2. two independent external passes report it (B and D, or C and Step 2);
3. the frames, frame-step strip or audio snippet you extracted at that moment show it (save it to `$OUT/evidence/`).

Unconfirmed measurement flags stay in an **inspect** list as UNKNOWN. When you believe an external finding is wrong, mark it **DISPUTED** with the evidence and keep it in the report; never drop an external finding on your own. Comments that judge the premise or propose a different story are out of scope and do not move a score.

Severity: **blocker** (a viewer stops watching, loses trust or is misled), **major** (most viewers notice; looks unprofessional), **minor** (an attentive viewer may notice). "Looks like an AI avatar" is a blocker only when the presenter brief says real filmed person and passes A or B and D agree.

## Step 7: Verdict and report

- **SHIP:** no confirmed blocker or major, every applicable group PASS or N/A, full coverage.
- **FIX:** confirmed majors, no blockers.
- **REJECT:** any confirmed blocker.
- **INCONCLUSIVE:** a tool failed, coverage has gaps, or a disputed blocker is unresolved. Never round it up to SHIP.

Write `$OUT/report.md` and `report.json`: verdict; brief; coverage (seconds and fps per pass, which tools ran); a table per checklist group; confirmed findings with timestamp, evidence, viewer impact and fix; the inspect list; disputed findings; up to three things to keep; tokens per pass. Each fix names the suspected stage (script, voice, generation, compositing, edit, mix, export) and an instruction a builder agent can carry out.

## Step 8: Fix and review again

Fix every confirmed blocker and major, render, and run the whole review again on the new file. Stop after three rounds; anything still open goes to the person who asked for the video. Never re-run passes on an unchanged file to get a better verdict.

Tell the user in three or four lines: the verdict, which models reviewed it, the top confirmed issues and fixes, and anything UNKNOWN or disputed. Send the report and the contact sheet.

## Make it automatic

Add this line to any skill or CLAUDE.md that builds video:

> Before delivering any video, run the video-review skill. If the verdict is SHIP, deliver the video. If it is FIX or REJECT, fix every confirmed blocker and major problem, render again and review again, up to three rounds. If it is INCONCLUSIVE, find what the missing check needs, resolve it and run the review again. If the video still does not reach SHIP, show the report and explain what needs to happen next.

For videos built from a script, also run the script gate and the visuals gate in `references/staged-reviews.md` before voicing and before rendering.
