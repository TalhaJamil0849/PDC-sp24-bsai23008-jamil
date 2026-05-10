"""
test_circuit_breaker.py

Simulates the LLM API going down and proves the circuit breaker
handles it gracefully.

Run with:
    pytest tests/test_circuit_breaker.py -v
"""

import respx
import httpx
from fastapi.testclient import TestClient

from app.main import app, llm_breaker, LLM_API_URL
from app.circuit_breaker import State



def reset_breaker():
    """Reset the circuit breaker to a clean CLOSED state before each test."""
    llm_breaker._state = State.CLOSED
    llm_breaker._failure_count = 0
    llm_breaker._opened_at = None



def test_student_id_header_present():
    """Every response must carry the X-Student-ID header."""
    reset_breaker()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Student-ID" in response.headers
    assert response.headers["X-Student-ID"] == "bsai23008"


def test_student_id_header_present():
    reset_breaker()
    client = TestClient(app)
    response = client.get("/health")

    print("\n")
    print("=" * 60)
    print("  HEADER CHECK: X-Student-ID on every response")
    print("=" * 60)
    print(f"  Endpoint: GET /health")
    print(f"  Status:   HTTP {response.status_code}")
    print(f"  Header:   X-Student-ID = {response.headers.get('X-Student-ID')}")
    print("=" * 60)

    assert response.status_code == 200
    assert "X-Student-ID" in response.headers
    assert response.headers["X-Student-ID"] == "bsai23008"



def test_without_circuit_breaker_every_request_fails():
    reset_breaker()
    original_threshold = llm_breaker.failure_threshold
    llm_breaker.failure_threshold = 999

    call_count = 0

    print("\n")
    print("=" * 60)
    print("  BEFORE: No circuit breaker. LLM is DOWN. Sending 5 requests...")
    print("=" * 60)

    try:
        with respx.mock:
            def broken_llm(request):
                nonlocal call_count
                call_count += 1
                print(f"  --> Request #{call_count} hit the LLM... FAILED")
                raise httpx.ConnectError("LLM is down")

            respx.post(LLM_API_URL).mock(side_effect=broken_llm)
            client = TestClient(app)
            for i in range(5):
                resp = client.post("/api/ask", json={"prompt": "test"})
                print(f"  <-- Response #{i+1}: HTTP {resp.status_code}")

        print(f"\n  RESULT: {call_count}/5 requests hit the broken LLM. No protection.")
        print("=" * 60)
        assert call_count == 5
    finally:
        llm_breaker.failure_threshold = original_threshold



def test_circuit_breaker_opens_after_threshold():
    reset_breaker()
    call_count = 0

    print("\n")
    print("=" * 60)
    print("  AFTER: Circuit breaker ON. Threshold = 3. LLM is DOWN...")
    print("=" * 60)

    with respx.mock:
        def broken_llm(request):
            nonlocal call_count
            call_count += 1
            print(f"  --> Request #{call_count} reached LLM... FAILED")
            raise httpx.ConnectError("LLM is down")

        respx.post(LLM_API_URL).mock(side_effect=broken_llm)
        client = TestClient(app)

        for i in range(3):
            resp = client.post("/api/ask", json={"prompt": f"q{i}"})
            print(f"  <-- Response #{i+1}: HTTP {resp.status_code} | breaker: {llm_breaker._state.value}")

        print(f"\n  Breaker is now: {llm_breaker._state.value}")
        print("  Sending 5 more requests... these should be BLOCKED:")

        for i in range(5):
            resp = client.post("/api/ask", json={"prompt": f"q_after_{i}"})
            data = resp.json()
            print(f"  <-- Request blocked! HTTP {resp.status_code} | source: {data['source']} | '{data['answer'][:45]}...'")

    print(f"\n  RESULT: Only {call_count}/8 requests hit the LLM. 5 were short-circuited.")
    print("  Users got instant fallback instead of a 60s hang.")
    print("=" * 60)

    assert call_count == 3


def test_fallback_response_is_user_friendly():
    """The fallback response should be a readable message, not a raw exception."""
    reset_breaker()
    llm_breaker._state = State.OPEN
    import time
    llm_breaker._opened_at = time.time()  # make sure it's fresh OPEN

    client = TestClient(app)
    resp = client.post("/api/ask", json={"prompt": "hello"})
    assert resp.status_code == 503
    data = resp.json()
    assert "temporarily unavailable" in data["answer"].lower()
    assert data["source"] == "fallback"


def test_circuit_breaker_transitions_to_half_open():
    """After cooldown the breaker should enter HALF_OPEN and allow one probe."""
    reset_breaker()
    import time

    llm_breaker._state = State.OPEN
    # Set opened_at far in the past so cooldown has expired
    llm_breaker._opened_at = time.time() - 9999

    # Checking state should flip it to HALF_OPEN
    state = llm_breaker.state
    assert state == State.HALF_OPEN


def test_success_resets_breaker():
    """A successful LLM call should reset the breaker back to CLOSED."""
    reset_breaker()
    llm_breaker._failure_count = 2  # one away from threshold

    with respx.mock:
        respx.post(LLM_API_URL).mock(return_value=httpx.Response(200, json={"text": "Hello!"}))

        client = TestClient(app)
        resp = client.post("/api/ask", json={"prompt": "hi"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "llm"

    assert llm_breaker._state == State.CLOSED
    assert llm_breaker._failure_count == 0


def test_breaker_status_endpoint():
    """The /api/breaker-status endpoint should expose current breaker state."""
    reset_breaker()
    client = TestClient(app)
    resp = client.get("/api/breaker-status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "CLOSED"
    assert data["failure_count"] == 0
