# Thread Futures part 10: CI and Docker build

**Status:** Built · **Label:** Built 9 Nov 2026  

## In one line
On every push, GitHub Actions runs the tests, builds the Docker image and calls the running API.

## Why it matters
Shows the work runs anywhere, not just on one laptop. Part of the earlier, exploratory technical work, not the product; if the batch report prototype (part 18) is ever built, it would be tested and built the same way.

## Data
n/a

## Method
Two jobs: test (install pinned dependencies, run pytest) and docker (docker build, docker run, poll /health, POST a real forecast request). Badge on the README.

## Tools
GitHub Actions, Docker, pytest, curl

## Result
First run passed on 9 Nov 2026: tests green, image built, API answered a forecast request. Latest check, 17 Nov 2026: the five most recent runs are green; the log shows 23 tests passed and the container answered the forecast request.

## Honest limits
Image is built in CI but not yet pushed to a registry.

## Where it lives
.github/workflows/ci.yml, Dockerfile
