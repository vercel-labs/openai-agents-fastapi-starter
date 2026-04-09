"""OpenAI Agents SDK + Vercel Sandbox on Vercel Python Functions."""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agents import ModelSettings, Runner
from agents.exceptions import AgentsException, UserError
from agents.extensions.sandbox import (
    VercelSandboxClient,
    VercelSandboxClientOptions,
)
from agents.run import RunConfig
from agents.sandbox import Manifest, SandboxAgent, SandboxRunConfig
from agents.sandbox.capabilities import Shell
from agents.sandbox.entries import File

load_dotenv(".env.local")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

SAMPLE_DATA = (
    b"region,q1_revenue,q2_revenue\n"
    b"north,120000,135000\n"
    b"south,95000,102000\n"
    b"east,110000,98000\n"
    b"west,88000,115000\n"
)


def _default_model() -> str:
    return (os.getenv("OPENAI_DEFAULT_MODEL") or "gpt-4.1-mini").strip()


app = FastAPI(title="OpenAI Agents + Vercel Sandbox")


class RunRequest(BaseModel):
    input: str = Field(
        ...,
        min_length=1,
        description="User message for the sandbox agent.",
    )
    model: str | None = Field(
        default=None,
        description="Model override; defaults to OPENAI_DEFAULT_MODEL.",
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
            detail="OPENAI_API_KEY is not set.",
        )

    model = (body.model or _default_model()).strip()

    manifest = Manifest(
        entries={
            "sales.csv": File(content=SAMPLE_DATA),
        },
    )

    agent = SandboxAgent(
        name="analyst",
        model=model,
        instructions=(
            "You have shell access to an isolated sandbox. "
            "Use it to analyze workspace files and answer "
            "questions. Be concise."
        ),
        default_manifest=manifest,
        capabilities=[Shell()],
        model_settings=ModelSettings(tool_choice="required"),
    )

    client = VercelSandboxClient()
    session = await client.create(
        manifest=manifest,
        options=VercelSandboxClientOptions(timeout_ms=120_000),
    )

    try:
        async with session:
            run_config = RunConfig(
                sandbox=SandboxRunConfig(session=session),
                tracing_disabled=True,
            )
            result = await Runner.run(
                agent,
                body.input,
                run_config=run_config,
            )
    except UserError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except AgentsException as exc:
        logger.exception("Agents run failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception:
        logger.exception("Unexpected error during agent run")
        raise HTTPException(status_code=500, detail="Internal server error") from None
    finally:
        await client.delete(session)

    final = result.final_output
    text = "" if final is None else str(final)
    return RunResponse(output=text)
