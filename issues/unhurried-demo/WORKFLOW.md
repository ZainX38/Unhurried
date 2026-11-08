# Per-ticket session workflow

Every ticket in `issues/` is done in its own session:

1. **Fresh session.** Run `claude` in the repo. Paste the last handoff, if there is one.
2. **Plan mode** (Shift+Tab twice): "We're on ticket issues/unhurried-demo/issues/NN-*.md. Explain the plan: files, functions, inputs, outputs, tests. No code." Push back until you could draw it.
3. **/tdd**
   - **Recipe A** (core logic, Status `ready-for-human`): "I'll write the implementation myself. Write one failing test at a time from my cases, then wait."
   - **Recipe B** (plumbing, Status `ready-for-agent`): Claude writes the tests and the implementation. You read every file before accepting it.
4. **Red → green → refactor** (Recipe A): Claude adds a test; you run `uv run pytest` and watch it fail; you write the smallest code that passes (if stuck, ask for a "hint, don't write it"); tidy while green; repeat.
5. **Check yourself.** Answer the ticket's "Check yourself" questions, then ask Claude to "Quiz me with 3 questions, one at a time."
6. **Compare with Hiya1** (`../Hiya1`, the earlier attempt at this project): note one difference in `NOTES.md`.
7. **/code-review.** Fix real problems; note any suggestion you reject and why.
8. **Commit**, move the ticket file to `issues/unhurried-demo/done/`, run `/handoff`, and close the session.

**Cut list if behind:** ticket 10 goes first.
