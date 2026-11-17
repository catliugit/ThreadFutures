# Thread Futures part 18: Batch report prototype

**Status:** Planned · **Label:** Planned (next, after validation interviews)  

## In one line
The first build of the actual product: one batch report per batch of a brand's unsold stock, recording every unit and every step (check, sell or donate or recycle, report), with an export of the EU Article 24 disclosure rows.

## Why it matters
Thread Futures is a B2B resale service for fashion brands: we act as their sales team for stock they can't sell themselves. The brand keeps ownership of the stock until it is sold, gets the money from each sale and gets a report of where every item went. Parts 1 to 10 are the founder's technical proof; this part is the product itself.

## Skills it adds
Data modelling, SQL (SQLite/Postgres), FastAPI, audit logging, pytest

## Plan
- **Batch intake with grading fields:** batch ID, SKUs, quantity, real size breakdown, condition codes, fibre composition (from the brand's product specs), reason unsold.
- **Placement records, in waste-hierarchy order:**
  - contracted buyers, with the contract terms per placement (no destruction, no export as waste, channel/marketplace limits, de-labelling where required, onward-destination reporting) and the buyer's onward-destination report;
  - an offer/refusal log for donation to EU social-economy entities (who was offered what, when, and their decision), so the donation derogation (offered to at least three suitable EU entities for at least 8 weeks) can be evidenced;
  - waste-operator statements for last-resort recycling: the derogation statement handed over and the operator's receipt/treatment statement collected.
- **Hash-chained, append-only log:** every event is appended and chained to the previous one, so any later edit is visible. Records are created at the moment of each handover, not rebuilt afterwards.
- **Export:** a batch report per batch (kept 5 years, producible within 30 days of a request) and rows ready for the Article 24 disclosure table.
- FastAPI endpoints to record events and export the batch report and disclosure rows.

This is why the product isn't something a chatbot can reproduce: a chat can draft a template, but it can't create a charity's acceptance or a waste operator's statement after the fact.

## Done when
A demo season's batches produce a reproducible batch report and disclosure rows, with tests.

## Effort
About 4 days, scheduled after the validation interviews.

## Note on the file name
This file keeps its original name (`18_batch_and_destination_file_prototype.md`); "destination file" was the earlier name for the batch report.
