# Review checklist

Each item says what good looks like, then how it is checked. Tags: **[L0F]** every-frame pass (Step 2b), **[L0]** measurement, **[L1]** face and lip metrics, **[AV]** Gemini passes A and B, **[AU]** audio-only pass C, **[FR]** GPT stills pass D, **[RT]** retell pass E, **[SO]** sound-off pass F, **[P:n]** persona n from pass G, **[CR]** content review, **[REF]** comparison with reference sheets. **V** marks a viewer question, **E** an editor check.

## 0. Brief fit
- V: Does the video do what the brief says for this audience, on this platform? [P:1, AV]
- E: Length, aspect ratio and format match the brief. [L0]

## 1. Story and comprehension
- V: Can a first-time viewer retell who it is about, what they want, what goes wrong and how it ends? Example of a PASS: "A girl wants to jump into the pool, her parents say no, she does it anyway and soaks them." [RT]
- V: Is the one point clear (comedy, warmth or action), not three things at once? [P:1, P:4]
- V: Does the opening shot promise something worth watching within 3 seconds? [P:2, AV]
- E: Information arrives in an order that makes the viewer care. Example: Finding Nemo moved the loss to the opening so viewers liked Marlin. [RT, P:3]
- E: The ending comes from the character's own action, not luck; the ending image pays off the opening. [RT, P:4]
- V: Does the story still read with the sound off? [SO]

## 2. Hook and first frame
- First frame works as a thumbnail and is not black, blurred or mid-blink. [L0, FR]
- The first spoken line or first image names the subject and why it matters. [CR, AV]
- The unprimed viewer would keep watching at 1 s and 3 s. [AV, P:2]

## 3. Characters and design consistency
- E: Each character matches its reference sheet in every shot: face, hair, glasses, build, outfit. Example of a FAIL: an adult character renders as a child for several frames. [L0F, REF, FR]
- E: Props keep their state across shots (a taken or broken object stays taken or broken). [REF, FR]
- E: Style, lighting and colour stay in one film; no shot looks like another film. [FR, P:4]
- E: Cast is right: no extra or missing person in a shot. [L0F, REF]
- V: Does anything look out of place for the period or setting (a padlock on an ancient seal)? [REF, P:6]

## 4. Acting and expressions
- V: Do the characters seem to think and decide, or only move? Example of a PASS: "she notices the cake, hesitates, then grins". [P:4, AV]
- E: Every character on screen has something to do; listeners react with a thought, lips closed. [P:4, FR]
- E: No mouth movement without a story reason. Talking, panting or mumbling in a silent film is a blocker. [L0F, L1, AV]
- E: Eyes and brows carry the expression; eyes lead head turns; eyeline holds on its target; blinks present, not mechanical. [L1, P:4]
- E: No symmetric, frozen or plastic faces in close-ups; no reversion to a neutral face in the last second of a shot. [FR, P:4]
- E: Acting register fits the beat: snappy comic poses for gags, small physical cues for tender beats. [P:4]

## 5. Actions, motion and physics
- E: Every shot plays at natural speed: no slow motion, ramps or freeze holds used to fill time. Example of a FAIL: a shot slowed to 0.72x to fit the music. [L0, L0F]
- E: No near-static shots that read as slow motion. [L0, confirm on frames]
- E: Anticipation before big moves, follow-through after; contact has weight (feet plant, hands grip, a splash lands). [P:4]
- V: Does each action read in one look, with the payoff large enough on a phone? [P:1, FR]
- E: No morphing limbs, wrong finger counts, sliding feet or floating characters. [L0F, FR]

## 6. Staging, camera, light and colour
- E: One idea per shot, clear silhouette, nothing competing for the eye. [FR, P:3]
- E: Shot size and angle carry meaning (the powerful character larger or closer; a lonely character small in a big space). [P:3, P:4]
- E: Screen direction holds; characters do not swap sides unless the move is shown. [P:3]
- V: Does the light and colour support the feeling of each scene? [P:4, AV]

## 7. Pace and editing
- V: Did any part drag or rush? Where (MM:SS)? [P:1, P:2, AV]
- E: Cuts judged in Walter Murch's order: emotion, story, rhythm, eye trace, screen direction, continuity. [P:3]
- E: Key reactions get time before and after; cuts happen on action or on a change in the eyes. [P:3]
- E: Shot lengths shorten into the climax and lengthen after it; a breath after an action peak. [L0 shot table, P:3]
- E: No unintended dead air over 0.7 s; no line finished with a character standing idle. [L0]

## 8. Scene-to-scene transitions and continuity
- E: Seams between generated clips are invisible: no face jump, colour shift, lighting jump or audio change. [L0 seams, L0F, FR, AU]
- E: Each new location is introduced clearly; its sound starts before or with its picture. [P:3, P:5]
- E: Transition type fits the moment: hard cut inside a scene, motion or match cut for flow, fade only for time passing. [P:3]
- E: No accidental jump cuts (two near-identical framings in a row). [L0, FR]
- E: No flashed reference image or stray frame at clip ends. [L0, L0F]

## 9. Audio: voice and sound design
- V: Does the voice sound like a person talking to another person; are names pronounced right? [AU, L0 ASR]
- E: Four layers present: ambience, effects, music, voice; no scene sounds empty. [AU, P:5]
- E: Every visible action that should make a sound does, on the frame (footsteps, splash, door); no sound without a cause. [AV, P:5, H]
- E: A planned silence or drop before the main payoff. [L0 music map, P:5]
- E: No clicks, warble, dropouts or robotic artefacts. [L0, AU]
- E: Loudness within 1 LU of the target (-14 LUFS for social), true peak at or below -1 dBTP; impacts keep weight on a phone speaker. [L0]

## 10. Music
- V: Does the music fit the feeling of each part, without fighting the picture? [P:1, P:5]
- E: Music enters on the story turn or the reaction, not on a random cut; it builds from quiet; one hard hit on the payoff. [L0 music map, P:5]
- E: Music sits under voice and key effects; no stray vocals; no abrupt start or stop. [AU]
- E: The picture was not slowed or the score stretched to make them fit; one theme runs through instead of a new tune per shot. [L0, P:5]

## 11. Lip sync and audio-video sync
- Lip sync inside about 45 ms audio early and 125 ms audio late, confirmed by stepping frames on a b, p or m sound. An LLM opinion alone never confirms lip sync. [L1, frames]
- Silent mouths stay closed in pauses of 300 ms or more. [L1, L0F, AV]
- Sound effects and music hits land on the frame they belong to. [AV, H]

## 12. Text, captions and graphics
- Captions match the spoken words; readable at phone size; inside safe zones; never over a face. [L0 ASR, FR]
- No garbled generated text anywhere in frame. [L0F, FR]

## 13. Cliches and AI tells
- V (critic persona): Name every choice that feels generic or seen before: stock music swell, slow-motion hero walk, glossy everything, random camera orbits, everyone smiling at the lens, the same push-in on every shot. Each one is a finding unless the brief asks for it. [P:6]
- E: AI tells: plastic skin, waxy hair, symmetric faces, floaty motion, background people frozen or moving in sync, morphing hands, text gibberish, sudden style shifts. [P:6, FR, AV]
- E: Design inconsistencies between shots that a viewer would notice (outfit colour, prop size, set layout). [REF, P:4]

## 14. Platform finish
- Aspect, length, end card, brand colours and logo correct; re-check the platform-transcoded file when available. [L0, FR]
- The decision is bound to the exact final file (hash recorded). [L0]

## 15. Persona verdicts
- Every persona answers: would you keep watching, would you share or send it, score 1 to 5. Report them side by side. A film with any persona below 3 needs a stated reason in the report, even when the verdict is SHIP.

## Hard blockers (any confirmed one means FIX or REJECT)
Decode failure; missing or truncated narration; unintelligible speech; story fails the retell test; a gag or key beat that does not happen; confirmed lip sync outside the window; mouth moving through silence; identity drift or face jump at a cut; a character missing or wrong in a shot; slowed or frozen shots used to fill time; audible clicks or warble; visible judder; wrong finger count or a gesture that contradicts the words; a caption that changes the meaning; unreadable essential text; hazardous flashing; for a photoreal brief, both external models judge the presenter as AI.
