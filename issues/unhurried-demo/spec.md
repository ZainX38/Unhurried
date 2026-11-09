# Unhurried demo: an energy supplier line that doesn't cut off callers who stammer

Status: ready-for-agent

Vocabulary follows `docs/GLOSSARY.md`. Relevant ADRs: 0001 (the Endpointer consumes VAD frames, not audio; pure state machine whose only clock is the frames it is fed) and 0002 (Vosk for STT).

## Problem Statement

People who stammer are routinely failed by automated phone lines. These systems decide a caller has finished speaking after a short, fixed silence, so a Block or a repetition in the middle of a Turn is taken as the Turn end. The system talks over the caller, mishears a half-finished answer, and then loops on "Sorry, I didn't catch that". Phone menus, call screeners and help lines are often unavoidable, so callers who stammer are excluded from services that everyone else can use. The obvious fix, waiting longer for everyone, makes every fluent caller sit through dead air, so providers don't adopt it.

For this submission (Hiya internship, Accessibility track, due Wed 11 Nov 2026), the developer needs a working, locally runnable prototype that reviewers can run themselves. It must show this problem being solved, and give honest numbers proving that Cut-offs drop for callers who stammer without fluent callers waiting noticeably longer.

## Solution

Unhurried is a simulated energy supplier phone line in the browser. The caller speaks into their microphone and the system asks three Prompts: account number, date of birth, and "How can I help today?". It reads back the number and date for confirmation, recognises the caller's Intent, and never loops: at most one Re-prompt, then a Fallback.

At its core is the Endpointer. It watches the speech/silence pattern and the words so far, and judges Completeness against the expected Slot, to decide when the Turn has really ended. When an answer is clearly Complete, it replies sooner than a fixed-timeout system would. When the answer is Incomplete or Unknown, it waits longer. It also remembers earlier Turns within the Call, becoming more patient with a caller who has shown long Blocks while fluent callers never trigger the extra patience. A 5-second Ceiling guarantees nobody sits in dead air.

A Baseline / Unhurried toggle and a live timeline let anyone see the difference. A "play synthetic caller" button lets reviewers reproduce it without stammering themselves.

An evaluation harness backs up the claim. It runs both strategies over generated Timelines (1,000 Calls per Severity group), over real recorded audio with inserted Blocks passed through the real VAD and STT, and over real stammered speech from SEP-28k. It reports Cut-off rate and Wait time (median and p95) per group, and plots a fixed-timeout sweep as a trade-off curve with Unhurried as a point off the curve.

**Ownership split:** the developer writes the Endpointer rules, Completeness rules and Cleanup rules themselves (test-first). Everything else is plumbing built around those interfaces.

## User Stories

### Callers

1. As a caller who stammers, I want the line to wait through a Block in the middle of my answer, so that I am not talked over before I finish.
2. As a caller who stammers, I want the line to wait when my answer is obviously unfinished (for example, only 5 of 8 account digits), so that a pause doesn't get my half-answer accepted.
3. As a caller who stammers, I want my repetitions and fillers removed before my answer is interpreted, so that "my my my account is…" is understood as what I meant.
4. As a caller who stammers, I want the line to become more patient once it has heard me Block earlier in the Call, so that later answers go more smoothly.
5. As a caller who stammers, I want my account number read back to me, so that I can catch any mistake caused by a misheard repetition before it matters.
6. As a caller whose account number genuinely contains repeated digits (for example 44445123), I want those digits kept, so that Cleanup doesn't "fix" my real number.
7. As a caller who says "double four" or "oh" for zero, I want those understood as digits, so that I can speak naturally.
8. As a caller whose date of birth is spoken in pieces ("the twelfth of… March… nineteen ninety"), I want the line to wait until day, month and year are all present, so that I am not cut off between them.
9. As a caller, when the line couldn't understand me, I want one patient Re-prompt ("No rush. Could you say your account number again?"), so that I get a second chance without pressure.
10. As a caller, when the Re-prompt also fails, I want to be offered keypad entry or a human agent, so that I am never trapped in a voice recognition loop.
11. As a caller, if the line starts speaking while I am still talking, I want it to stop immediately and keep listening, so that a mistake doesn't become a dead end (Barge-in).
12. As a caller who has truly finished, I want a reply within at most 5 seconds of silence, so that I'm never left in dead air.
13. As a fluent caller, I want replies at least as quick as on a normal phone line, so that Unhurried doesn't make my call slower.
14. As a fluent caller giving a clearly complete answer (8 digits, a full date, "yes"), I want an even faster reply than a normal line, so that I benefit too.
15. As a caller, I want my reason for calling recognised as billing, moving home, meter reading or a power cut, so that I'm routed sensibly.
16. As a caller whose reason doesn't match a known Intent, I want the line to read back a summary of what I said and ask if it's right, so that I'm not forced into the wrong category.
17. As a caller confirming a Read-back, I want a short "yes" or "no" to be taken promptly, so that confirming isn't a chore.
18. As a caller who answers "no" to a Read-back, I want to be asked for that Slot again (counting as the one Re-prompt), so that I can correct it.

### Reviewers (Hiya)

19. As a reviewer, I want to install and run Unhurried locally with one setup step and no API keys or accounts, so that I can see it working without friction.
20. As a reviewer, I want a model download script that fetches the VAD and STT models, so that setup is repeatable.
21. As a reviewer, I want a README with setup and run instructions, so that I can start it on my machine.
22. As a reviewer, I want to talk to the line through my browser microphone, so that I can experience it live.
23. As a reviewer, I want a "play synthetic caller" button that streams a committed synthetic stammered caller in place of the mic, so that I can reproduce the demo without stammering myself.
24. As a reviewer, I want a Baseline / Unhurried toggle, so that I can play the same caller through both and see the Baseline cut them off while Unhurried waits.
25. As a reviewer, I want a live timeline of speech, silence, Blocks, words and the Endpoint marker, so that I can see *why* the system decided when it did.
26. As a reviewer, I want to re-run the evaluation with one command and get the same numbers (fixed seed), so that I can trust the reported results.
27. As a reviewer, I want results that include real audio through the real VAD and STT, not just generated events, so that I know the logic isn't only being tested against its own assumptions.
28. As a reviewer, I want the trade-off chart (fixed-timeout sweep curve with Unhurried as a point), so that I can see the balance at a glance.
29. As a reviewer, I want the sources of the generator's parameters cited, so that I can judge how realistic the synthetic callers are.
30. As a reviewer, I want an ai.md that describes which AI tools were used and how, including what the developer wrote themselves, so that I understand the split.
31. As a reviewer, I want a 1-page write-up (what, who, problem, results, next steps), so that I get the whole story quickly.
32. As a reviewer, I want a 2–3 minute demo video as backup, so that I can see it working even if my setup misbehaves.

### The developer (rule author)

33. As the rule author, I want to write the Endpointer rules test-first against a narrow interface (one VAD frame in, a Decision out), so that I can iterate rule by rule.
34. As the rule author, I want Completeness as a pure function of transcript and expected Slot, with its own tests, so that I can develop it separately from timing.
35. As the rule author, I want Cleanup as a pure function of text, with its own tests, so that I can develop it separately.
36. As the rule author, I want the Endpointer to have no clock of its own, so that my tests are deterministic and need no waiting.
37. As the rule author, I want to run the Timeline evaluation in seconds, so that I can see the effect of a rule change on the numbers immediately.
38. As the rule author, I want Baselines implemented behind the same interface as the Endpointer, so that the evaluation compares like with like.
39. As the rule author, I want per-Call records in the results (where each Cut-off happened, which Slot, which Severity group), so that I can find out why my rules failed.
40. As the rule author, I want to record a few fluent answers myself and have the tool insert Blocks at known positions, so that I get real-voice test audio with exact Turn ends.
41. As the rule author, I want a SEP-28k real-speech check, so that my rules are tested against genuine stammered speech.
42. As the rule author, I want the Call session testable with hand-written event scripts, so that I can check that the whole flow (Endpointer + Cleanup + Completeness + Dialogue) behaves as a caller would expect.
43. As the rule author, I want to understand and be able to explain every plumbing component, so that I can defend my choices at interview.

### Evaluation

44. As the evaluator, I want Cut-off rate and Wait time (median and p95) reported separately for fluent, mild and severe Severity groups, so that the limits of the system are visible.
45. As the evaluator, I want Cut-offs counted even when Barge-in would have recovered them live, so that the headline metric isn't softened.
46. As the evaluator, I want a severe group that deliberately includes some Blocks longer than the Ceiling, so that the evaluation shows where the system reaches its limit.
47. As the evaluator, I want words in Timelines to arrive with a realistic STT delay (about 250 ms), so that the rules don't look better than they would live.
48. As the evaluator, I want a success target checked automatically (fluent median Wait time ≤ 900 ms; stammered Cut-off rate < 5%), so that "balance" can be tested.
49. As the evaluator, I want results written as JSON alongside the chart, so that they are easy to inspect and cite.

## Implementation Decisions

### Modules

- **Frames.** The shared input to every endpointing strategy is one call per 32 ms VAD frame (512 samples at 16 kHz):
  - `is_speech`: the VAD's speech/silence label for the frame
  - `frame_ms`: how much time the frame covers (32); this is the only way time moves forward
  - `transcript`: the full transcript of the current Turn so far, not a delta

  Both live audio and recorded clips produce exactly this input (ADR 0001). System speech (for Barge-in) is tracked by the Call session, not passed to the Endpointer.

- **Endpointer (developer-owned rules).** A pure state machine, one instance per Call. Interface:
  - `reset()` starts a new Turn (the expected Slot is given to the Endpointer when it is built or reset)
  - `step(is_speech, frame_ms, transcript)` feeds one frame and returns a `Decision`: `CONTINUE`, `END` (the Endpoint) or `PROMPT`, with a reason

  It may keep memory across Turns within the Call. It has no wall clock: silence durations are computed only by adding up the `frame_ms` of silent frames. It must Endpoint once continuous silence reaches the 5-second Ceiling, whatever else its rules say. It consults Completeness on the latest `transcript`.

- **Endpointing strategy interface.** The Endpointer and the fixed-timeout Baseline (parameterised by its silence timeout) share one interface, so the Call session, the live server and the evaluation can swap them freely. The Baseline ignores words and simply Endpoints after N ms of continuous silence following speech.

- **Completeness (developer-owned rules).** A pure function `completeness(transcript, expected_slot) → Complete | Incomplete | Unknown`. Slots: account number, date of birth, open reason, and Read-back confirmation (yes/no). The open reason defaults to Unknown and becomes Incomplete if the text ends on a word that can't end an answer ("and", "my", "the", "um", …).

- **Cleanup (developer-owned rules).** A pure function `clean(text) → text` that removes stammered repetitions and fillers without changing meaning. It never collapses repeated digit words, because a repeated digit may be genuine (resolved by Read-back). It targets what Vosk actually outputs: dictionary words only, with sound repetitions appearing as repeated or wrong short words, and Blocks as silence.

- **Slot parsers.** Turn a cleaned transcript into Slot values:
  - account number: exactly 8 digits; handles "oh" as zero and "double"/"triple" multipliers
  - date of birth: day, month, year
  - yes/no
  - Intent by keyword: billing, moving home, meter reading, power cut, otherwise none

- **Dialogue.** A deterministic script, no LLM:
  - account number → Read-back → date of birth → Read-back → open reason → Intent confirmation or summary read-back → closing line
  - At most one Re-prompt per Slot. A "no" to a Read-back counts as that Re-prompt.
  - A second failure triggers Fallback (keypad entry or a simulated human agent).
  - The phrasing is patient and never repeats "didn't catch that".

- **Call session (seam 1).** Composes the chosen strategy, Cleanup, Completeness, Slot parsers and Dialogue. Events go in; system actions come out:
  - `Say(text)` for Prompts, Re-prompts, Read-backs and Fallback offers
  - `StopSpeaking` for Barge-in
  - `Endpoint` markers, for the timeline
  - `CallComplete(slot values, intent)`

  Barge-in: speech during system speech emits `StopSpeaking`, and the speech continues the same Turn. Barge-in is kept only if it stays small; otherwise it moves to "next steps".

- **Audio front end.** Converts 16 kHz mono PCM into frames:
  - **VAD** labels each 32 ms frame speech or silence: an energy VAD first, Silero (ONNX, no PyTorch) once it works.
  - **Vosk** streaming produces the Turn's `transcript`, from partials and finals. Vosk's own "final" segmentation is treated only as transcript chunks, never as Turn ends (ADR 0002).

  The same front end is used by the live server and by the audio evaluations.

- **Live server.** FastAPI with one WebSocket per Call. The browser streams PCM; the server runs the audio front end, calls `step()` once per 32 ms frame, and runs the Call session in the selected mode (Baseline at 700 ms, or Unhurried). It sends actions and timeline events back to the browser.

- **Browser UI.** Plain HTML/JS:
  - mic capture with resampling to 16 kHz PCM
  - `speechSynthesis` for `Say`, cancelled on `StopSpeaking`
  - the Baseline / Unhurried toggle
  - a live timeline (speech, silence, words, Endpoint marker)
  - a "play synthetic caller" button that streams a committed WAV in place of the mic
  - headphones are assumed, so the system's voice doesn't trigger the VAD

- **Timeline generator.** Produces symbolic Calls (three Slot Turns plus confirmation Turns) for a Severity group and seed. Each Turn has speech segments, Blocks, repetitions, fillers and words with a known Turn end. Words are emitted about 250 ms after they are spoken. There are no recognition errors in v1. Parameters:
  - Stammer type frequencies come from the SEP-28k label CSV.
  - Block and prolongation durations come from published literature, cited in the write-up.
  - Severity groups, refined with cited values:
    - fluent: about 0–1% of words, pauses under 500 ms
    - mild: about 3–5% of words, Blocks 0.3–1.5 s
    - severe: about 10–15% of words, Blocks 1–4 s, with some deliberately past the Ceiling

- **Synthetic audio.** An offline generation script uses Piper (local TTS) to produce fluent phrases and inserts Blocks (silence), repetitions (repeated audio) and prolongations (time-stretched audio) at known positions. A small set of WAVs plus their Turn-end labels is committed, for the demo button, the video and an end-to-end check. Piper is needed only to regenerate them.

- **Recorded Turns.** The developer records a handful of fluent answers to the three Prompts. A tool trims each one, finds the word gaps (offline Vosk word timings), and inserts Blocks (and optionally repetitions) with durations drawn from the Severity group parameters. The Turn end follows exactly from the trimmed speech end plus the inserted silence. Small source recordings may be committed; generated variants can be regenerated.

- **Evaluation (seam 2).** Inputs: a strategy (Unhurried, or a Baseline with a given timeout), a dataset, a seed and a Call count. Outputs: Cut-off rate and Wait time (median and p95) per Severity group, plus per-Call records. The reported results include three datasets:
  1. **Timelines**: 1,000 Calls per Severity group, fixed seed. Used for tuning and the headline table.
  2. **Real audio through the VAD and STT**: Recorded Turns with inserted Blocks plus the committed synthetic audio, run through the real audio front end faster than real time.
  3. **SEP-28k real-speech check**: real stammered clips run through the audio front end and each strategy (open-reason Slot). SEP-28k clips are 3-second extracts from the middle of speech, so they have no Turn end. Instead, any Endpoint followed by more speech within the same clip counts as a **mid-clip Cut-off**. This is reported per SEP-28k label (Block, Prolongation, Sound repetition, Word repetition, Interjection, no stammer). Wait time is not measurable on this set and is not reported.

  A fixed-timeout sweep from 300 ms to 4 s across these datasets produces the trade-off chart (Cut-off rate against Wait time), with Unhurried plotted as a point. A results file records metrics, parameters, seed, and pass/fail against the success target.

- **Data handling.** The SEP-28k label CSV is fetched by script. SEP-28k audio is fetched by a download-and-clip script that takes a bounded subset, tolerates dead podcast URLs, and reports how many clips it got. All large downloads (models, SEP-28k audio) are git-ignored. Only small committed WAVs stay in the repo.

### Metrics (precise)

- **Cut-off**: an Endpoint before the Turn end. **Cut-off rate** = Cut-offs ÷ Turns.
- **Wait time**: Endpoint minus Turn end, for Turns that weren't Cut off. Reported as median and p95.
- **Success target**: fluent median Wait time ≤ 900 ms (700 ms Baseline + 200 ms), and stammered Cut-off rate < 5%. Severe Blocks longer than the Ceiling are expected, accepted Cut-offs and are called out separately.
- Cut-offs count even when Barge-in would recover them.

## Testing Decisions

- **What makes a good test**: it checks external behaviour through a seam (what goes in, what comes out) and never internal state or private helpers. Endpointer tests assert *when* an Endpoint happens for a given frame script, not how the rules are stored. All tests are deterministic: no wall clock, no randomness without a fixed seed, no network.
- **Seam 1, Call session**: hand-written event scripts drive whole Calls and assert the action sequence. Examples:
  - a severe caller's account number with a 2 s Block gets no Endpoint during the Block and a Read-back of the correct 8 digits
  - "double four" is parsed correctly
  - a "no" to a Read-back leads to one Re-prompt, then Fallback
  - speech during system speech produces `StopSpeaking`
  - a full fluent Call completes with the right Intent
  - the Baseline strategy in the same script Cuts off at the Block
- **Seam 2, Evaluation run**: tiny hand-made Timelines with known answers check the metric maths (for example, a 700 ms Baseline on a Turn containing a 1 s Block gives exactly 1 Cut-off; Wait time is computed only for Turns that weren't Cut off; p95 is correct). The same seed gives identical results. The mid-clip Cut-off rule is checked on a hand-made clip timeline.
- **Seam 3, Endpointer** (narrow; the developer uses it to write rules test-first with `/tdd`): frame scripts in, Endpoint time or none out. Includes Ceiling behaviour and memory across Turns.
- **Completeness and Cleanup**: direct table-style tests of the pure functions. These are written by the developer alongside the rules.
- **Slot parsers and Dialogue**: covered through seam 1. Parsers may get a few direct table tests where cases are numerous.
- **Not unit-tested (plumbing)**: browser, WebSocket, Silero, Vosk. They're covered by one end-to-end smoke test that runs a committed synthetic WAV through the real audio front end and Call session and checks that sensible events and an Endpoint are produced. This test is skipped if the models haven't been downloaded.
- **Prior art**: none. The codebase is an empty scaffold, so these tests set the pattern (pytest, one test file per module).

## Out of Scope

- Detection of stammering being misclassified as fraud (voice biometrics, risk scoring). It's mentioned only in the problem statement.
- Real telephony (SIP, phone numbers). The browser stands in for the phone line.
- LLM-based dialogue, and cloud STT/TTS or anything needing API keys.
- Custom TTS. Browser `speechSynthesis` speaks the replies; Piper is used only offline to generate test audio.
- Recognition errors in Timelines (v1 assumes perfect words, with a delay). This is named as a limitation.
- A full real-Turn evaluation with hand-labelled Turn ends from real people who stammer. This is future work.
- Splicing SEP-28k clips into Turns with known Turn ends, and measuring real Block durations from clips. Stretch goal: see `issues/sep28k-spliced-turns/spec.md`.
- Echo cancellation. Headphones are assumed.
- Barge-in, if it turns out not to be small: it moves to "next steps".

## Further Notes

- **Schedule**:
  - Sun 8 Nov: Events, Endpointer interface, Baselines, Timeline generator, evaluation harness, sweep chart, and the developer's v1 rules
  - Mon 9 Nov: audio front end, live server, browser UI, Dialogue and Call session, Cleanup rules
  - Tue 10 Nov: synthetic audio, Recorded Turns, SEP-28k check, tuning, video, write-up, README, ai.md
  - Wed 11 Nov: buffer and submit

  If Monday slips, Barge-in is dropped first.
- **Developer-owned work**: the Endpointer, Completeness and Cleanup rules. Agent tickets build interfaces, stubs, harness, audio, server and UI around them, and must not write those rules. ai.md should describe this split honestly.
- **Reviewer framing**: Accessibility track. Voice is not a choice here: phone lines are voice-only and often unavoidable, so this is the key moment where a keyboard can't do the job.
- **Risks**:
  - SEP-28k podcast URLs may be dead. Report the number of clips obtained.
  - Vosk accuracy on stammered speech is limited, so Read-back is the safety net.
  - The SEP-28k mid-clip Cut-off is a proxy metric (no true Turn ends) and should be described as such.
