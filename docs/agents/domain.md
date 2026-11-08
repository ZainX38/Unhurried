# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

**This repo keeps its glossary at `docs/GLOSSARY.md`, not the repo root.** Wherever a skill says "`GLOSSARY.md`", read and write `docs/GLOSSARY.md`. Never create a root-level `GLOSSARY.md`.

## Before exploring, read these

- **`docs/GLOSSARY.md`**: the project's domain vocabulary.
- **`docs/adr/`**: read ADRs that touch the area you're about to work in.

If either is empty or missing, **proceed silently**. Don't flag its absence. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) fills them in as terms and decisions get resolved.

## File structure

Single-context:

```
/
├── docs/
│   ├── GLOSSARY.md
│   └── adr/
│       ├── 0001-some-decision.md
│       └── 0002-another-decision.md
└── src/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `docs/GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because…_
