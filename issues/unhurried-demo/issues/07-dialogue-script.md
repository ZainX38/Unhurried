# Scripted dialogue

Status: ready-for-agent
Blocked by: 06

## What

A Call state machine: account number → Read-back → date of birth → Read-back → open reason → Intent reply. On a failed Slot, give one patient Re-prompt, then Fallback (offer keypad or "connecting you to an agent", simulated). Keyword-based Intents: billing, moving home, meter reading, power cut. Takes cleaned text and returns the next Prompt plus its Slot.

## Acceptance

Unit tests covering the happy path, a Read-back that is rejected, Re-prompt then Fallback, and each Intent.
