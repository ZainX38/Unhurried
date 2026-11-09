# Unhurried

A voice phone line that doesn't cut off people who stammer. It waits until a caller has really finished their turn before replying, without making fluent callers wait noticeably longer.

## Language

### Callers and speech

**Stammer**:
A speech difference where the flow of speech is interrupted by repetitions, prolongations or blocks.
_Avoid_: Stutter (except when quoting sources such as SEP-28k), speech impediment

**Block**:
A silent stoppage inside a Stammer, where the caller is mid-word or mid-phrase but no sound comes out.
_Avoid_: Pause (a Block is not the caller choosing to stop)

### Turn-taking

**Turn**:
Everything a caller says in response to one system prompt, possibly containing many pauses and Blocks.
_Avoid_: Utterance, segment

**Turn end**:
The true moment the caller finished their Turn; the ground truth that Endpoints are judged against.
_Avoid_: End of speech

**Endpointer**:
The part of Unhurried that decides when a caller's Turn has ended.
_Avoid_: Turn detector, silence timeout

**Endpoint**:
The moment the Endpointer decides the Turn has ended and the system may reply.
_Avoid_: Turn end (that is the ground truth, not the decision)

**Barge-in**:
The caller speaking while the system is replying, which makes the system stop and treat the speech as a continuation of the same Turn.
_Avoid_: Interruption

**Completeness**:
Whether the words so far in a Turn form a finished answer to the current Slot: Complete, Incomplete or Unsure.
_Avoid_: Confidence, finished-ness

**Ceiling**:
The longest continuous silence after which the Endpointer always Endpoints, whatever its rules say.
_Avoid_: Timeout, max wait

### Calls

**Call**:
One caller's whole conversation with the line, made of several Prompts and Turns; the Endpointer may remember earlier Turns within a Call.
_Avoid_: Session, conversation

**Prompt**:
One line the system says to ask the caller for something, such as "What's your account number?".
_Avoid_: Question, system turn

**Slot**:
The piece of information a Prompt asks for: account number, date of birth, or reason for calling.
_Avoid_: Field, entity

**Intent**:
The caller's reason for calling, recognised from the open Slot: billing, moving home, meter reading or power cut.
_Avoid_: Category, topic

**Read-back**:
The system repeating a number or date Slot to the caller and asking them to confirm it.
_Avoid_: Verification, echo

**Re-prompt**:
The single patient repeat of a Prompt after a Slot could not be understood.
_Avoid_: Retry, "didn't catch that"

**Fallback**:
What the system offers after a failed Re-prompt instead of asking again: keypad entry or a human agent.
_Avoid_: Escalation, error path

**Cleanup**:
Turning a raw transcript into what the caller meant by removing stammered repetitions and fillers, without changing its meaning.
_Avoid_: Normalisation, disfluency removal

### Evaluation

**Baseline**:
An endpointing strategy that ends a Turn after a fixed amount of silence, used as the comparison for Unhurried.
_Avoid_: Default, control

**Timeline**:
A generated, audio-free description of a Call: speech, Blocks, silences and words with timestamps, plus the true Turn ends.
_Avoid_: Synthetic events, simulation

**Recorded Turn**:
A real recording of a fluent answer with Blocks inserted at known positions, so its Turn end is known exactly.
_Avoid_: Test clip, sample

**Mid-clip Cut-off**:
An Endpoint inside a SEP-28k clip that is followed by more speech in the same clip; a stand-in for Cut-off on speech that has no known Turn end.
_Avoid_: False positive

**Severity group**:
The category a synthetic caller belongs to (fluent, mild or severe), determined by how often and how long they stammer.
_Avoid_: Stammer level, class

**Cut-off**:
An Endpoint that occurs before the Turn end, so the system would have spoken while the caller still had more to say.
_Avoid_: Interruption, false endpoint

**Wait time**:
The time from Turn end to Endpoint, for a Turn that was not Cut off.
_Avoid_: Latency, delay
