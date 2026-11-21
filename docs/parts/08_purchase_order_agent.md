# Thread Futures part 08: Purchase-order agent

**Status:** Built · **Label:** Prototype  

## In one line
Reads a messy production order note, states its assumptions, and calls tested tools for every number.

## Why it matters
Real orders arrive as emails and messages. The agent does the language work; code does the maths, so results are reproducible. Part of the earlier, exploratory technical work, not the product; the same pattern could later turn brands' messy stock lists into batch records for the batch report (part 18).

## Data
Free-text order notes.

## Method
An LLM with tool use calls a deterministic planning tool (forecast, grading, recycler matching). Invalid inputs come back as tool errors so the model can correct them.

## Tools
Python, LLM API with tool use (provider set by environment variables)

## Result
Every figure in the reply comes from tested code; assumptions are flagged explicitly.

## Honest limits
Needs an API key; not evaluated on a large set of real orders yet.

## Where it lives
src/offcut/agent.py, src/offcut/service.py
