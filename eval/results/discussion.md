# Explaining Results

`results.md` and `sweep.md` are generated and this shows an interpretation for them.

## 1. A fixed timeout can't solve the problem

The Baseline sweep shows the trade-off. Every stammered clip is cut off up to 1000 ms (30/30). The first threshold that cuts off nobody is 3000 ms, and at that point every fluent caller waits about 3 s (median 3014 ms) after each answer. No fixed threshold meets both targets (stammered cut-off < 5%, fluent median wait ≤ 900 ms). With a single silence threshold, you can only lower cut-offs by making everyone wait longer.

## 2. Reading the words moves off that curve

With real speech totext (Vosk), the Patient endpointer cuts off **7/30** stammered clips (23%) instead of 30/30. Fluent callers wait the same as the 0.7 s Baseline (median **707 ms**, p95 **722 ms**). All 4 thinking-pause takes are no longer cut off. It only waits longer when the words show the answer isn't finished, for example "my account number is…" or 4 of 8 digits. So the patience costs fluent callers almost nothing.

**Target check:** fluent wait met. **Stammered cut-off missed** (23% vs < 5%).

## 3. Why the remaining misses happen

I didn't add rules to fix individual clips. Each miss has a general cause:

| Clips | Transcripts | What happened | Cause |
| --- | --- | --- | --- |
| R2 ×3 | oracle + Vosk | "I want to set up…" ended mid-block | Free-text answers have no clear "unfinished" signal, so the rules fall back to the 0.7 s patience |
| R1_v1 | Vosk | The burst was heard as "what": "I'm calling about what" | It no longer ends on a dangling word, so it's timed like any free text |
| C1 ×3 | Vosk | The burst before "yes" was heard as "yeah" | A one-word answer looks complete, so the turn ended during the block |
| C1 ×3 | oracle | Nothing heard yet during the block | An empty confirmation is UNSURE, so the 0.7 s patience applies |

**Key finding:** Vosk turns the short burst at the start of a stammer into a real word, and which word it becomes is unpredictable. "my my" triggered the repetition bonus and saved R1_v2 and R1_v3. "what" and "yeah" caused cut-offs. Rules based on the words partly depend on how the speech-to-text hears the stammer.

## 4. The cost: turns that end with a prompt instead

Some clips never got an END. These are not cut-offs, and the "no END" column shows them so they aren't hidden from the wait statistics:

- **A3 (1/10 fluent, 3 stammered):** "eight" was heard as "a", which looks like an unfinished word.
- **C2_v1, C2_v3:** "four five two" was heard as "for or five to", and "or" doesn't count as a digit, so only 7/8 digits.

In each case the answer looked incomplete, so after 6 s the caller was gently prompted ("Take your time…") instead of cut off or hung up on. Waiting too long is the safe way to fail. The read-back and keypad fallback catch wrong digits after that.

## 5. Caveats

- My own voice, inserted blocks. I recorded 30 clips of myself and inserted blocks (a short burst, then 1–3 s of silence). There are no real stammers, repetitions or prolongations.
- Small set, no held-out data. 44 clips (10 fluent, 30 stammered, 4 pauses). The rules were designed and tested on the same clips, so the numbers may be optimistic. With 10 fluent clips, the p95 is close to the maximum.
- The oracle pause row is misleading. The thinking-pause takes have no piece transcripts, so the oracle run treats them as timing only (4/4 cut off). The Vosk row (0/4) is the real result.
- Speech-to-text delay. The oracle reveals words 300 ms after each piece. The measured Vosk delay was a median of 181 ms, so the oracle is slightly pessimistic.