# Thread Futures part 09: API service

**Status:** Built · **Label:** Prototype  

## In one line
Puts the offcut forecast, stall risk and regulation search behind one web service.

## Why it matters
Turns notebooks into something other systems can call. Deployment skills were the most common gap in the tracker.

## Data
Models saved by parts 1 and 4; regulation text from part 7.

## Method
FastAPI with Pydantic input validation. Endpoints: /health, /v1/offcuts/forecast, /v1/stock/stall-risk, /v1/regulation/search. Automated tests with pytest and TestClient.

## Tools
FastAPI, Pydantic, uvicorn, pytest, httpx

## Result
23 pytest tests passing across the offcut engine, stock analytics and API (bad inputs return 422).

## Honest limits
Not deployed to a public cloud yet (part 17).

## Where it lives
src/api/main.py, tests/
