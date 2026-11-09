# Perceptual defect catalogue

Defects a viewer notices on a phone, each with the check that finds it. A defect with no check that ran is UNKNOWN in the report, never PASS.
Measured checks come first; model passes confirm or catch what measurement cannot. Thresholds are for 1080x1920 reels; scale for 16:9.
Why it exists: a review of a graphics reel passed defects a person saw at once on a phone (blocks too close, text cut inside
blocks, captions touching content, arrows short of their boxes, an outline offset from the card it marks, an empty bottom third).
"Layout lint" checks need a linter for videos built from HTML (not included); without one, the Jev and pass D checks cover the same defects.
"pace_report.py" is not included; use words per minute from the tech_qc transcript.

## Visual: layout and text

| Defect | What the viewer sees | Check | Threshold |
|---|---|---|---|
| Crowding | two cards, rows or options almost touching | layout lint CROWDED; Jev `crowding` | gap under 40 px between blocks, 24 px side by side |
| Caption too close | caption pill touching or covering the picture | layout lint CAPTION_CLOSE; Jev `caption_clearance` | under 56 px from any block |
| Text cut or overflowing | a word running out of its tile, a line half hidden | layout lint TEXT_OVERFLOW, WORD_BROKEN; Jev `text_defect` | any |
| Code or word split across lines | "NCA-" / "GENL" | layout lint WORD_BROKEN | any |
| Screenshot text sliced at a frame edge | half a line at the top of a scrolling browser | layout lint EDGE_SLICE; Jev `text_defect` | any hard cut; a soft fade passes |
| Covering | a card or label over a screenshot or over what it points at | layout lint OVERLAP; Jev `covering` | more than 2% of the label's area |
| Pointer on the label | cursor or click ring over the text it clicks | Jev `covering`; frames | any |
| Marker misaligned | highlight or outline offset from the thing it marks | Jev `marker_alignment`; frames | visible offset |
| Connector gap | arrow or line stopping short of its box, or starting off its source | layout lint ARROW_GAP; Jev `connector` | over 14 px |
| Row misalignment | two pills or tiles on one row at different heights | layout lint ROW_MISALIGNED | centres over 6 px apart |
| Small text | text needing a zoom to read on a phone | layout lint SMALL_TEXT; Jev `small_text` | under 26 px body, 24 px chrome |
| Safe zone | text under the top bar, the description or the button rail | layout lint SAFE_ZONE | outside x 60-1020, y 220-1480; rail x over 960 at y 900-1500 |
| Empty frame | a band of the safe area left blank; everything stacked at the top | frame_use.py; layout lint EMPTY_BAND; Jev `composition` | band over 16% of the safe area for 4 s, or 20% of the frame for 2 s |
| Unbalanced composition | all weight on one side or the top; big dead corner | Jev `composition`; persona 4 | opinion, confirm on frames |
| Placeholder text | template names, "sample", debug labels | Jev `placeholder`; content-review | any in a release |
| Low contrast | grey text on a tinted card, text on a busy image | Jev `contrast`; pass D | below 4.5:1 for body text |
| Edge and corner glitches | clipped shadows, cards cut by the frame by accident, jagged borders | pass D; Jev `text_defect` | any |
| Inconsistent styling | different radii, shadows or type sizes for the same element type | persona 4; pass D | any |

## Visual: motion and time

| Defect | Check | Threshold |
|---|---|---|
| Frozen hold | tech_qc duplicated frames; Jev freeze runs | still picture over 1.5 s with no narration reason |
| Flash or stray frame | Jev glitch question; tech_qc frame-jump spikes | any |
| Jank or stutter in a move | tech_qc duplicated-frame share in moving spans | over 5% duplicates in a move |
| Too fast to read | layout lint text timing (words on screen per second); pass B | under 0.3 s per word for new text |
| Element pops without easing, or eases inconsistently | persona 4 (motion designer) | opinion |
| Cursor path robotic or wrong | persona 3, frames | straight-line teleports, overshoot |
| Pointless motion (everything moves at once) | persona 4, pass B | opinion |

## Audio (only when the video has sound)

| Defect | Check | Threshold |
|---|---|---|
| Loudness off target | tech_qc | outside -14 LUFS plus or minus 1 LU; true peak over -1 dBTP |
| Clicks, pops, warble, dropouts | tech_qc click candidates; pass C | any confirmed |
| Music masks the voice | stems: voice minus music loudness during speech | under 15 LU apart |
| Abrupt music start, stop or loop seam | tech_qc music map; pass C | level jump over 6 dB in 50 ms not on a cut |
| Dead air | tech_qc silences | over 0.7 s unplanned |
| Harsh sibilance or plosives | pass C; 5-8 kHz and under-100 Hz bursts | any confirmed |
| Mispronounced name or term | ASR read-back; pass C | any |
| Unnatural pace or rhythm | pace_report.py; pass C | outside 140-185 words per minute for a reel |
| Captions out of sync | caption times against ASR word times | more than 150 ms off |
| Captions with no voice | ASR finds no speech while captions run | any |
| Sound without a cause, or a visible action with no sound | pass H | per the H rules |
| Mix thin or muddy on a phone | tech_qc phone check | intelligibility drop after a 300 Hz high-pass |

## Checks not built yet (report UNKNOWN until they are)

- Text timing in the layout lint (new text on screen long enough to read).
- Caption sync: caption word times against ASR word times.
- Voice-over-music gap from the stems (the kit's music mix sets it; nothing measures the final file yet).
- Sibilance and plosive burst detection in tech_qc.
