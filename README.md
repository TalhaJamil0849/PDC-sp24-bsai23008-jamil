Muhammad Talha Jamil | bsai23008

# PDC-Sp24-bsai23008-Jamil

Assignment 2: Building Resilient Distributed Systems — Part 3 implementation.

**Problem solved:** Fault Tolerance via a Circuit Breaker pattern for the external LLM API.

## What is implemented

- `app/circuit_breaker.py` — thread-safe Circuit Breaker with CLOSED / OPEN / HALF_OPEN states
- `app/main.py` — FastAPI app with:
  - `POST /api/ask` — calls LLM through the circuit breaker, returns fallback on failure
  - `GET /api/breaker-status` — exposes the current breaker state for debugging
  - `GET /health` — basic health check
  - `StudentIDMiddleware` — injects `X-Student-ID: bsai23008` on every response
- `tests/test_circuit_breaker.py` — full test suite proving before/after behavior

## How to run

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the server

```bash
uvicorn app.main:app --reload
```

### 3. Run the tests

```bash
pytest tests/test_circuit_breaker.py -v
```

You should see all tests pass. The key tests are:

- `test_without_circuit_breaker_every_request_fails` — proves that without a breaker, all 5 requests hit the broken LLM
- `test_circuit_breaker_opens_after_threshold` — proves that after 3 failures only 3 real calls are made; the rest are short-circuited
- `test_student_id_header_present` — confirms the `X-Student-ID` header is on every response

## Demo notes

For the screen recording, run the tests with `-v` and show the output. The `call_count` assertions make it very clear: 5 calls without the breaker vs 3 calls with the breaker open.
