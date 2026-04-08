# OpenAI Agents Python on Vercel Functions

Minimal [FastAPI](https://fastapi.tiangolo.com/) app that runs the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) on [Vercel’s Python runtime](https://vercel.com/docs/functions/runtimes/python). Use it to prove `Runner.run` in production before wiring a remote sandbox client.

## Prerequisites

- Python 3.12+ (Vercel default is 3.12; this template sets `requires-python >= 3.12`).
- A Vercel account and [Vercel CLI](https://vercel.com/docs/cli) (`npm i -g vercel`).
- An OpenAI API key.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | API key for the OpenAI provider. Without it, `GET /api/health` reports `degraded` and `POST /api/run` returns **503**. |
| `OPENAI_AGENT_HARNESS_ID` | No | If set, the SDK attaches `agent_harness_id` trace metadata (see SDK `openai_agent_registration`). |
| `OPENAI_DEFAULT_MODEL` | No | Default model when the JSON body does not include `model`. Falls back to `gpt-4.1-mini`. |

Copy [.env.example](.env.example) to `.env` for local use. On Vercel, set variables under **Project → Settings → Environment Variables**.

## Local development

```bash
uv sync
export OPENAI_API_KEY=sk-...
uv run uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

- Health: `GET http://127.0.0.1:8000/api/health`
- Run agent: `POST http://127.0.0.1:8000/api/run` with JSON body:

```json
{
  "input": "What is 19 plus 23? Use the tool.",
  "model": "gpt-4.1-mini"
}
```

Optional: omit `model` to use `OPENAI_DEFAULT_MODEL` / `gpt-4.1-mini`.

## Deploy to Vercel

From this directory:

```bash
vercel
```

Vercel detects `app.py` and the `app` ASGI instance. Dependencies come from [pyproject.toml](pyproject.toml).

### Bundle size

Python functions have an uncompressed bundle size limit (see [Vercel Python docs](https://vercel.com/docs/functions/runtimes/python)). [vercel.json](vercel.json) uses `excludeFiles` to omit common dev-only paths from the function bundle.

### Timeouts and long runs

Agent runs can span multiple model turns. Serverless functions have execution time limits; heavy workloads may need [Fluid Compute](https://vercel.com/docs/fluid-compute), a background worker, or [Vercel Workflow](https://vercel.com/docs/workflow) for durable steps.

## Phases

1. **This template (Phase 1)** — Plain `Agent` + `function_tool` + `Runner.run` on Vercel. No workspace sandbox.
2. **Streaming (optional)** — Add `Runner.run_streamed` and a streaming HTTP response (Vercel supports Python streaming).
3. **Sandbox harness (Phase 3)** — `SandboxAgent` + `SandboxRunConfig(client=...)` needs a **remote** `SandboxClient` (e.g. Vercel Sandbox when exposed in the SDK, or another hosted backend). `UnixLocalSandboxClient` / Docker are not suitable inside a stateless function.

### Using a preview / fork of the SDK

To test unreleased SDK changes, point the dependency in `pyproject.toml` at your Git revision, for example:

```toml
dependencies = [
  "fastapi>=0.117.1",
  "openai-agents @ git+https://github.com/openai/openai-agents-python.git@YOUR_BRANCH",
]
```

Then redeploy so Vercel installs that revision.

## License

MIT (match your org’s policy when publishing).
