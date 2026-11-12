# Thread Futures part 18: Batch and destination file prototype

**Status:** Planned · **Label:** Planned (Mon 16 – Thu 19 Nov 2026)  

## In one line
The first build of the second-life desk's product: one destination file per batch, recording every unit and every step (Grade → Place → Prove), with an export of the EU Article 24 disclosure rows.

## Skills it adds
Data modelling, SQL (SQLite/Postgres), FastAPI, audit logging, pytest

## Plan
- **Batch intake with grading fields:** batch ID, SKUs, quantity, real size breakdown, condition codes, fibre composition (from the brand's tech packs), reason unsold.
- **Placement records, in waste-hierarchy order:**
  - contracted buyers, with the contract terms per placement (no destruction, no export as waste, channel/marketplace limits, de-labelling where required, onward-destination reporting) and the buyer's onward-destination report;
  - an offer/refusal log for donation to EU social-economy entities (who was offered what, when, and their decision), so the donation derogation (offered to at least three suitable EU entities for at least 8 weeks) can be evidenced;
  - waste-operator statements for last-resort recycling: the derogation statement handed over and the operator's receipt/treatment statement collected.
- **Hash-chained, append-only log:** every event is appended and chained to the previous one, so any later edit is visible. Records are created at the moment of each handover, not rebuilt afterwards.
- **Export:** a destination file per batch (kept 5 years, producible within 30 days of a request) and rows ready for the Article 24 disclosure table.
- FastAPI endpoints to record events and export the file and disclosure rows.

This is why the product isn't something a chatbot can reproduce: a chat can draft a template, but it can't create a charity's acceptance or a waste operator's statement after the fact.

## Done when
A demo season's batches produce a reproducible destination file and disclosure rows, with tests.

## Effort
4 days (Mon 16 – Thu 19 Nov 2026)
