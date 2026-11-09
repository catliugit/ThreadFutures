# Thread Futures part 10: CI and Docker build

**Status:** Built · **Label:** Built 9 Nov 2026  

## In one line
On every push, GitHub Actions runs the tests, builds the Docker image and calls the running API.

## Why it matters
Shows the work runs anywhere, not just on one laptop. Docker and CI/CD appear across DS and ML job ads.

## Data
n/a

## Method
Two jobs: test (install pinned dependencies, run pytest) and docker (docker build, docker run, poll /health, POST a real forecast request). Badge on the README.

## Tools
GitHub Actions, Docker, pytest, curl

## Result
First run passed on 9 Nov 2026: tests green, image built, API answered a forecast request.

## Honest limits
Image is built in CI but not yet pushed to a registry.

## Where it lives
.github/workflows/ci.yml, Dockerfile
