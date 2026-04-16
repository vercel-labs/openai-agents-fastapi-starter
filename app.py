"""OpenAI Agents SDK + Vercel Sandbox on Vercel Python Functions."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from openai.types.responses import ResponseTextDeltaEvent
from pydantic import BaseModel, Field

from agents import ModelSettings, Runner
from agents.exceptions import AgentsException, UserError
from agents.extensions.sandbox import (
    VercelSandboxClient,
    VercelSandboxClientOptions,
)
from agents.run import RunConfig
from agents.models.multi_provider import MultiProvider
from agents.sandbox import Manifest, SandboxAgent, SandboxRunConfig
from agents.sandbox.capabilities import Shell
from agents.sandbox.entries import File
from agents.stream_events import RunItemStreamEvent

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
    return (os.getenv("OPENAI_DEFAULT_MODEL") or "openai/gpt-4.1-mini").strip()


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


STATIC_DIR = Path(__file__).parent / "static"


def _sse(event: str, data: object) -> str:
    payload = json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _extract_tool_call_command(item: object) -> str | None:
    raw = getattr(item, "raw_item", None)
    if raw is None:
        return None
    arguments = getattr(raw, "arguments", None)
    if not arguments:
        return None
    try:
        parsed = json.loads(arguments) if isinstance(arguments, str) else arguments
        return parsed.get("cmd")
    except Exception:
        return None


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


@app.post("/api/run")
async def run_agent(body: RunRequest, request: Request) -> StreamingResponse:
    env_url = "https://vercel.com/d?to=%2F%5Bteam%5D%2F%5Bproject%5D%2Fsettings%2Fenvironment-variables"
    for var in ("OPENAI_API_KEY", "VERCEL_TOKEN", "VERCEL_TEAM_ID", "VERCEL_PROJECT_ID"):
        if not os.getenv(var, "").strip():
            raise HTTPException(
                status_code=503,
                detail=f"{var} is not set. Add it in your project settings: {env_url}",
            )

    token = os.getenv("VERCEL_TOKEN")
    team_id = os.getenv("VERCEL_TEAM_ID")
    project_id = os.getenv("VERCEL_PROJECT_ID")
    base_url = os.getenv("OPENAI_BASE_URL")
    is_ai_gateway = (base_url is not None) and base_url.startswith("https://ai-gateway.vercel.sh")

    async def generate() -> AsyncIterator[str]:
        model = (body.model or _default_model()).strip()

        manifest = Manifest(
            entries={"sales.csv": File(content=SAMPLE_DATA)},
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

        client = VercelSandboxClient(
            token=token,
            team_id=team_id,
            project_id=project_id,
        )
        session = None

        try:
            session = await client.create(
                manifest=manifest,
                options=VercelSandboxClientOptions(timeout_ms=120_000),
            )

            async with session:
                run_config = RunConfig(
                    model_provider=MultiProvider(openai_prefix_mode="model_id" if is_ai_gateway else "alias"),
                    sandbox=SandboxRunConfig(session=session),
                    tracing_disabled=True,
                )
                result = Runner.run_streamed(
                    agent, body.input, run_config=run_config, max_turns=10
                )

                async for event in result.stream_events():
                    if isinstance(event, RunItemStreamEvent):
                        if event.name == "tool_called":
                            cmd = _extract_tool_call_command(event.item)
                            if cmd:
                                yield _sse("tool_call", {"command": cmd})
                        elif event.name == "tool_output":
                            output = getattr(event.item, "output", None)
                            if output is not None:
                                yield _sse("tool_output", {"output": str(output)})

                    elif (
                        event.type == "raw_response_event"
                        and isinstance(event.data, ResponseTextDeltaEvent)
                    ):
                        yield _sse("text_delta", {"delta": event.data.delta})

                yield _sse("done", {})
        except UserError as exc:
            yield _sse("error", {"detail": exc.message})
        except AgentsException as exc:
            logger.exception("Agents run failed")
            yield _sse("error", {"detail": str(exc)})
        except Exception as exc:
            logger.exception("Unexpected error during agent run")
            yield _sse("error", {"detail": str(exc)})
        finally:
            if session is not None:
                await client.delete(session)

    return StreamingResponse(generate(), media_type="text/event-stream")
