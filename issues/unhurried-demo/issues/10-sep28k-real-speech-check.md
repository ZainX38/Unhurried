# 10: SEP-28k real-speech check

**Status:** ready-for-agent (plumbing, Recipe B). **Gate:** you approve the metric definition below before the evaluation runs.
**Blocked by:** 03, 06
**When:** after the Tuesday checkpoint. **First thing cut if behind.**

**What to build:** Every endpointer run against genuine stammered speech from SEP-28k, reporting a false cut-off rate per stammer group against a fluent control, so the results aren't only our own recordings.

## Understand

- SEP-28k clips are 3 s fragments of continuous podcast speech, not finished answers, so they have no true Turn end.
- **Approach (reuse Hiya1's):**
  - Cut **10 s windows centred on a labelled clip**, so the speaker is still talking after the event.
  - Any `END` before the last speech in the window is a **false cut-off**.
- **Groups:** block / repetition / prolongation / **fluent control**.
  - A clip joins a group when at least 2 of 3 annotators chose the label, with priority block > repetition > prolongation.
  - Control windows contain no majority-labelled stammer clip.
- Podcast talk has natural sentence-final pauses, which also cause "cut-offs". So each stammer group is **always read against the control group**, never on its own.
- Report the false cut-off rate per group with **Wilson confidence intervals** (the groups are small).
- **Limitation, to state in the results:** podcasts contain no account numbers, so the answer-format signal ("4/8 digits") can't be tested here. This check measures timing and transcript signals only.
- **Licensing:** SEP-28k labels are CC BY-NC 4.0. The audio stays with the podcast owners and is **never committed**. Only the subset of clip IDs is committed.

## Build

- `eval/sep28k_subset.csv` (the committed clip-ID list; Hiya1's can be reused) and a fetch script that downloads the episodes and cuts the windows into a git-ignored folder. It needs ffmpeg, tolerates dead podcast links, and reports how many windows it obtained.
- A runner that feeds the windows through the same VAD, `--stt vosk` and endpointer path as ticket 03, for the Baseline and the patient endpointer, writing a results table and chart to `eval/results/`.

## Metric definition (for your approval)

_False cut-off: `END` strictly before the last VAD speech frame in the window. Rate = false cut-offs ÷ windows, per group, with 95% Wilson CI. Windows are padded with 8 s of silence as in ticket 03._ Approve or edit before running.

## Check yourself

- [ ] Why 10 s windows instead of the 3 s clips?
- [ ] Why must every group be read against the control?
- [ ] Why Wilson intervals rather than a plain ± error?
- [ ] Which Unhurried signal can this dataset not test, and why?

## Acceptance

- [ ] You have approved the metric definition.
- [ ] The results table shows the false cut-off rate with Wilson CIs per group for Baseline and patient.
- [ ] The results state the number of windows obtained and the account-number limitation.
- [ ] No SEP-28k audio is committed.
