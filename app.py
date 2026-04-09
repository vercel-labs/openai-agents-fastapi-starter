"""OpenAI Agents SDK on Vercel Python Functions (FastAPI ASGI)."""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agents import Agent, Runner, function_tool
from agents.exceptions import AgentsException, UserError
from agents.run import RunConfig

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


@function_tool
def add_numbers(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    return a + b


def _demo_agent(model: str) -> Agent:
    return Agent(
        name="VercelDemo",
        model=model,
        instructions=(
            "You are a concise assistant. When the user asks for addition of two integers, "
            "use the add_numbers tool."
        ),
        tools=[add_numbers],
    )


def _default_model() -> str:
    return (os.getenv("OPENAI_DEFAULT_MODEL") or "gpt-4.1-mini").strip()


app = FastAPI(title="OpenAI Agents — Vercel template")


class RunRequest(BaseModel):
    input: str = Field(..., min_length=1, description="User message for the agent.")
    model: str | None = Field(
        default=None,
        description="Model override; defaults to OPENAI_DEFAULT_MODEL or gpt-4.1-mini.",
    )


class RunResponse(BaseModel):
    output: str


STATIC_DIR = Path(__file__).parent / "static"

RATE_LIMIT = 5
RATE_WINDOW = 60
_request_log: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> None:
    now = time.time()
    timestamps = _request_log[ip]
    _request_log[ip] = [t for t in timestamps if now - t < RATE_WINDOW]
    if len(_request_log[ip]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {RATE_WINDOW}s.",
        )
    _request_log[ip].append(now)


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str | bool]:
    has_key = bool(os.getenv("OPENAI_API_KEY", "").strip())
    return {
        "status": "ok" if has_key else "degraded",
        "openai_configured": has_key,
    }


@app.post("/api/run", response_model=RunResponse)
async def run_agent(body: RunRequest, request: Request) -> RunResponse:
    _check_rate_limit(request.client.host if request.client else "unknown")

    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not set. Add it in the Vercel project environment.",
        )

    model = (body.model or _default_model()).strip()
    if not model:
        raise HTTPException(status_code=400, detail="model must be a non-empty string when provided.")

    agent = _demo_agent(model)
    run_config = RunConfig(model=model)

    try:
        result = await Runner.run(agent, body.input, run_config=run_config)
    except UserError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except AgentsException as exc:
        logger.exception("Agents run failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception:
        logger.exception("Unexpected error during agent run")
        raise HTTPException(status_code=500, detail="Internal server error") from None

    final = result.final_output
    text = "" if final is None else str(final)
    return RunResponse(output=text)
