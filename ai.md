# AI Usage

I built **Unhurried** with **Agent-Assisted Coding**: 
- **Me**: I designed the system and built the core logic myself (the endpointers, the completeness rules, the evaluation metrics)
- **Claude Code**: it wrote most of the plumbing (audio processing, the evaluation harness, speech to text wiring, the server and the UI) from plans I agreed first. 

I checked everything with tests, regression checks and by reading the code.



## Tools

| Tool | Reason |
| --- | --- |
| **Claude Code** | Planning the code, writing tests, plumbing code and code reviews |
| **Matt Pocock's Skills for Claude Code** | This is a set of instructions that makes Claude a proper engineering process, which looks like this: align --> spec --> tickets --> test driven build --> review |
| **Claude Chat** | To analyse my project plan, explain concepts I didn't know (audio frames, VAD, percentiles) and organising my notes |
| **Perplexity** | For general research such as stammering statistics, and what issues people were facing with current audio systems |
| **Impeccable Skill for Claude Code** | Used it for the UI design of the page |



## My AI Workflow

### 1. Planning

I do this at the start:
1. `/setup-matt-pocock-skills` configures the repo with tickets in `/issues` folder, glossary in `docs/GLOSSARY.md` and decision in `docs/adr`
2. `/grill-with-docs` is probably the most important step as it lets me and Claude Code to align our ideas. It interviews me about my plan one question at a time, and writes teh terms into the glossary and the decisions into ADRs. This made sure Claude and I were aligned about the plan before the code
3. Test seams: I asked for narrow tests for the rules I write myself
4. `to-spec` turned the conversation into a spec and then `/to-ticket` split it into 10 tickets/ issues. These tickets are sized for one fresh Claude session, so Claude Code remains below the 40% context window for better answers.

#### Decisions

From the `grill-with-docs` some decisions were made:

| Decision | Suggested by | Why |
| --- | --- | --- |
| Vosk for speech-to-text (ADR 0002) | Claude | At first, I wanted to use a Python library called `faster-whisper` but this wouldn't stream data to the backend, which Vosk does |
| Endpointer as a pure state machine fed one VAD frame per call (ADR 0001) | Claude | I wanted the Endpointer to analyse the audios and from that figure out some data, but this would be slow. Claude suggested the Endpointer should never see raw audio and turn it into a pure state machine with no clock of its own, which means time arrives only as each frame's 32 ms, so the endpointer has no clock and can replay thousands of Turns faster than real time. |
| Call flow: account number → date of birth → reason, with read-back | Me | This will be the demo flow. It starts from easy (account number), which is predictable to something harder (reason), which is harder to predict, meaning the system must work accurately. This will help me properly test and demo my program |
| At most one re-prompt, then fallback (keypad or simulated agent) | Me | During research, I read that adults who stammer, often fell on audio loops on calls. To prevent this, my system will ask for one reprompt and if it still doesn't understand keypad fallback and if it doesn't understand again then hand over to a person |
| Barge-in: if the caller keeps talking, the system stops and treats it as the same turn | Me + Claude | It can happen the system misunderstand a timing and cuts off the user, so in case this happens, I suggested to Claude to make the system stop talking and start again. Claude also suggested to measure how often this happens and account it for the evaluation and cut-off rate stat. This will be the next step. |
| Real recordings in pieces, Oracle transcripts and Vosk | Me + Claude | This was Claude's test plan to properly evaluate the system |
| Targets: fluent median wait ≤ 900 ms; stammered cut-off rate < 5% | Me | I suggested Claude to use these two values as an evaluation measurement. With these values, I can measure the actual cost of patience. |

The explanation of the results can be seen in [discussion.md](/eval/results/discussion.md)

---

### 2. Building

After the `to-tickets`, now I had an idea of how to work on each ticket step by step. 

I have two approeaches I use when working on them:

|  | Approach A: Core | Approach B: Plumbing |
| --- | --- | --- |
| Used for | The complex and important logic where everything depends on and I will design myself. This includes the endpointer, completeness, metrics and dialogue files | Standard and easy code that isn't the core idea such as audio, harness, STT wiring, server, UI |
| Code Writer | Me | Claude |
| Main Skill | `/tdd` | `/implement` |

- Approach A is where I write the main logiv and I also give Claude test cases in plain English, which it turns into one test at a time. It also reviews my code.

- Approach B is where I make the design decisions, read every line and run it to see it works. And Claude writes the code and explains it file by file, so I have got an idea of how it all works.#

- All tickets start in **plan mode** and ends with a `/code-review` if I added a big change, then a commit and a `/handoff` so the next session starts with the appropriate context. I also use Claude to quiz me if it was the one who wrote the code, so I properly understand the code.



### 3. Writing Code

This is how the workload looks like from all the 10 tickets:

| Part | Me | Claude |
| --- | --- | --- |
| Baseline + endpointer interface | Code and test cases | Tests from my cases |
| Test data | Recorded 30 clips and worked on all design decisions | `make_data.py` and its tests |
| Evaluation | `metrics.py` + tests | Replay harness, sweep, charts |
| Completeness rules | Rule design, about half the code, all test cases | About half the code and later two fixes I specified (rule order, ordinal days), which I reviewed |
| Patient endpointer | Code and test cases | Oracle transcript harness, wiring, chart |
| Speech-to-text | Read Vosk's raw output and made the decisions | Adapter, model download, `--stt` options |
| Dialogue | `dialogue.py` + tests | — |
| Session, server, stream script | Reviewed | All of it |
| Frontend | Requirements, accessibility constraints, review, mic test | React app, sample caller, mic/worklet, UI polish |
| Cleanup | Rules and all test cases | `cleanup.py` |

### 4. Checking AI Output

- **Tests first:** my core logic was built using the skill `/tdd` from test cases I wrote in plain English. This was over 140 tests by the end of Ticket 6. With this method I was able to write code better while meeting the agreed changes with Claude.
- Reading every file Claude wrote, and asking it to explain if anything is unclear (using the skill `/wait-what` or `btw`).
- **Regression Checks**
- **Predicting results before running them**. I did this to predict which clips the patient endpointer would miss (R2 and C1) before the evaluation ran and it matched



### 5. Where I disagreed with AI

I don't like to trust AI in all of their outputs, and it was the same in this project. There were times I disagreed with Claude:
- No LLM endpointer as it adds latency
- Real recordings instead of generated timelines and Piper
- A one off ffmpeg conversion instead of a resampling dependency
- The slot only in `reset()` and never in the constructor

Also, sometimes I made mistakes which Claude caught, but there were also times Claude made mistakes too:

| Claude Caught | I Caught |
| --- | --- |
| I had the rule any word ending in "th" before the month is a day, but this would have matched "birth" making "my date of birth is March" completely wrong. It then narrowed the rule and added a test | Flent clips that never ended were left out of the wait statistics, which hides a real cost. So I asked for a separate column called prompted |
| Using Vosk's partial text would lose words because Vosk restarts its partial when it splits a segment mid blocks | There was a padding mismatch, which was 6s in the clips but 8s for the planned harness. This would have made the prompt impossible to measure. SO, I changed it to 8s, so the 6s prompt could be measured |
