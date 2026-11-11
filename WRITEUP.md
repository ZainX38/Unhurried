# Unhurried

**Zain Mohammad Tahira**. Hiya Voice AI Challenge, Accessibility track

Unhurried is a phone line that doesn't cut off people who stammer.

## The problem

Automated phone lines decide when you have finished speaking when it detects silence for a fixed time, which is often around 0.7s. But, people who stammer often have **blocks** (silent moments mid-sentence where the word won't come out). So for a fixed timeout, a block is the same as the end of an answer.

In Apple's study of people who stutter, the most common complaint about voice assistants (61%) was being cut off, and 77% blamed pauses for it. STAMMA's 2025 survey found that 65% of calls made by people who stammer were mishandled. For example, callers were interrupted, talked over, stuck in recognition loops or hung on. 

Making the timout longer doesn't fix the problem because then every caller, even if fluent, has to wait for longer periods of time.

## Who it's for

People who stammer who need to use automated phone lines for everyday services like energy, banks and the GP, where an account number or date of birth has to be given by voice. It also helps the businesses running those lines as fewer failed calls and fewer callers handed over to an agent.

## Why voice?

Phone menus, call screeners and helplines are often voice-only and unavoidable. Unhurried's goal is to stop these callers from being excluded and misunderstood.

## What I built

A working demo energy company line ("Northwind Energy") that asks for an account number, date of birth and reason for calling, with a switch between a standard **Baseline** (fixed 0.7 s timeout) and **Unhurried**.

- **Patient endpointer:** a pure, frame by frame state machine. It waits 0.7s like the Baseline, but also reads the live transcript against the question asked. If the answer is clearly unfinished ("my account number is…", 4 of 8 digits, a date with no year), silence never ends the turn. After 6s it gently says "Take your time" and keeps listening
- I added **Completeness rules** instead of an LLM as they run in microseconds, so there's no added delay
- **Read-back, one re-prompt, then a keypad fallback** and a hand-over to a person, so no caller gets stuck in a loop.
- **Offline speech-to-text (Vosk)**, a FastAPI WebSocket backend and a React frontend, with either your microphone or a recorded sample caller.
- **An evaluation** on 44 clips of my own voice with blocks inserted at known points, plus a sweep of fixed timeouts from 0.3 to 4s for comparison.

**Results (with real speech recognition):** stammered callers cut off fell from **100% to 23%**. Fluent callers still wait a median of **707 ms**, the same as the 0.7s Baseline, and no thinking pause was cut off. A fixed timeout only stops cutting stammered callers off at 3 s, where every fluent caller waits 3s too. The remaining misses are free text answers, where the words give no "unfinished" signal, and stammers that the speech recogniser turned into a real word ("yeah"). When Unhurried does fail, it usually fails safely, with a gentle prompt rather than a cut-off.

## What I'd do next with more time

1. **Test with people who stammer.** My data is my own voice with added blocks, so this is the most important step
2. **Detect blocks from the audio itself**, with a detector trained on real stammered speech (e.g. Apple's SEP-28k), since speech recognition turns the start of a stammer into unpredictable words
3. **Barge-in:** if the bot speaks too early and the caller keeps talking, stop and treat it as the same turn
4. **Run it on a real phone line** (8 kHz telephone audio) and measure call completion rates with real users