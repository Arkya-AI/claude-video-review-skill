# Staged reviews

For videos built from a script (explainers, tutorials, lectures, graphics reels), review at three stages, not only on the finished file, so each problem is caught where it is cheapest to fix.

## Stage 1: script gate (before voicing)

Inputs: the script (narration plus the planned on-screen text per part) and the brief. Runs:
- A content review of the script by a different model from the one that wrote it.
- Pass N, new viewer, on the script text: `prompts/pass_n_new_viewer.txt` with {MATERIAL} = "video script, with the text that will appear on screen for each part".

Gate: no blocker or major open; pass N clarity and completeness 4 or more; no unbridged jump.

Examples:
- FAIL: the script jumps from "three routes to sit the exam" to "80 supplier documents" with no bridge, and uses "partner" before explaining it.
- FAIL: "Book through Skilljar" before the script says what Skilljar is; pass N lists "Skilljar" as unexplained.
- PASS: every part ends on a sentence that leads into the next, and pass N's summary matches the brief's one point.

## Stage 2: visuals gate (after boards are built, before rendering)

Inputs: one settled still per board plus phone-size copies, and the script. Runs:
- Pass D graphics (`prompts/pass_d_graphics.txt`) on the stills.
- Pass N on the storyboard: stills in order plus the narration for each, {MATERIAL} = "storyboard (one picture per part, with the narration under each)".

Gate: no major from pass D; pass N finds no picture that contradicts or lags its narration.

Examples:
- FAIL: a caption 6 px under a browser window and list rows 14 px apart.
- FAIL: a board showing step 3 while the narration is still on step 2.
- PASS: every board has one focal point and the caption clears the content by 56 px.

## Stage 3: final review (rendered and mixed file)

The full review (Steps 1 to 8 in SKILL.md), with the every-frame pass and pass N on the video ({MATERIAL} = "short video").

Examples:
- FAIL: pass N's summary names a different next action from the brief's call to action.
- FAIL: pass N cannot explain the main point to a colleague.
- PASS: the retell pass and pass N agree with the brief, and no persona reports confusion.
