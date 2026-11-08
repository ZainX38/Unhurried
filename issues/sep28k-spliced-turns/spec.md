# Spliced SEP-28k Turns (stretch goal)

Status: needs-triage

## Why

SEP-28k clips are 3 seconds long and have no Turn end labels, so they cannot measure Cut-off rate directly. In the main demo (`issues/unhurried-demo/spec.md`), SEP-28k calibrates the generator's stammer type frequencies and provides a real-speech check (mid-clip Cut-offs, no Wait time). This stretch goal goes further: real stammered audio inside full Turns, with known Turn ends, so Wait time can be measured too.

## Idea

Splice real stammered SEP-28k clips (especially ones labelled Block, Prolongation or Sound/Word repetition) into synthetic Turns whose Turn end is known. Then run the same Cut-off rate and Wait time evaluation on this semi-real set.

## Notes

- Also a chance to measure real Block and prolongation durations from the clips. For now, durations come from published literature only, since there's no time to time clips by hand.

- The SEP-28k audio is not in the dataset. It ships as podcast episode URLs plus clip timestamps, so episodes must be downloaded and clipped. Start downloads early if this goal is attempted.
- If not done by 11 Nov, list it in the write-up under "what I'd do next", along with a full real-Turn evaluation using hand-labelled Turn ends.
