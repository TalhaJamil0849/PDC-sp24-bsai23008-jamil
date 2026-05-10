import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.circuit_breaker import CircuitBreaker, State

app = FastAPI(title="StudySync API")

class StudentIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Student-ID"] = "bsai23008"
        return response

app.add_middleware(StudentIDMiddleware)


llm_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=10)

LLM_API_URL = "https://api.example-llm.com/generate"  # mock endpoint
LLM_TIMEOUT  = 5   


FALLBACK_RESPONSE = {
    "answer": "AI features are temporarily unavailable. Please try again shortly.",
    "source": "fallback",
}
async def call_llm(prompt: str) -> dict:
    """
    Attempt to call the external LLM API.
    Raises httpx.HTTPError on any failure so the caller can record it.
    """
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        resp = await client.post(LLM_API_URL, json={"prompt": prompt})
        resp.raise_for_status()
        return resp.json()

@app.post("/api/ask")
async def ask_llm(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "")

    if not llm_breaker.allow_request():
        return JSONResponse(
            status_code=503,
            content={
                **FALLBACK_RESPONSE,
                "circuit_breaker_state": llm_breaker._state.value,
            },
        )

    try:
        result = await call_llm(prompt)
        llm_breaker.record_success()
        return JSONResponse(content={"answer": result, "source": "llm", "circuit_breaker_state": llm_breaker._state.value})

    except Exception as exc:
        llm_breaker.record_failure()
        return JSONResponse(
            status_code=503,
            content={
                **FALLBACK_RESPONSE,
                "error": str(exc),
                "circuit_breaker_state": llm_breaker._state.value,
            },
        )


@app.get("/api/breaker-status")
async def breaker_status():
    return {
        "state": llm_breaker.state.value,
        "failure_count": llm_breaker._failure_count,
        "failure_threshold": llm_breaker.failure_threshold,
        "cooldown_seconds": llm_breaker.cooldown_seconds,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
