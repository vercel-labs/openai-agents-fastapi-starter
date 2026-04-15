# OpenAI Agents SDK FastAPI Starter with Vercel Sandbox

Minimal [FastAPI](https://fastapi.tiangolo.com/) app that runs the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) with [Vercel Sandbox](https://vercel.com/docs/vercel-sandbox) on [Vercel's Python runtime](https://vercel.com/docs/functions/runtimes/python). Each request spins up an isolated microVM, gives the agent shell access to analyze data, and tears it down when done.

## Prerequisites

- Python 3.12+ (Vercel default is 3.12).
- A Vercel account and [Vercel CLI](https://vercel.com/docs/cli) (`npm i -g vercel`).
- An OpenAI API key.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | API key for the OpenAI provider. |
| `VERCEL_OIDC_TOKEN` | Yes | Auto-provisioned by `vercel env pull`. Authenticates Vercel Sandbox. |
| `OPENAI_DEFAULT_MODEL` | No | Default model when the request body omits `model`. Falls back to `gpt-4.1-mini`. |

## Setup

```bash
vercel link
vercel env pull
```

This creates `.env.local` with your `VERCEL_OIDC_TOKEN`. Add your OpenAI key:

```bash
echo 'OPENAI_API_KEY=sk-...' >> .env.local
```

## Local development

```bash
uv sync
uv run uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 to use the interactive demo. The agent has shell access to a sandbox with sample sales data (`sales.csv`).

API endpoints:

- `GET /api/health` returns `{"status": "ok", "openai_configured": true}`
- `POST /api/run` with `{"input": "Which region grew the most?"}` runs the sandbox agent

## Deploy to Vercel

```bash
vercel
```

Vercel detects `app.py` and the `app` ASGI instance. Dependencies come from [pyproject.toml](pyproject.toml). Make sure `OPENAI_API_KEY` is set under **Project > Settings > Environment Variables**. The `VERCEL_OIDC_TOKEN` is auto-provisioned on Vercel deployments.

### Rate limiting

The demo includes in-memory rate limiting (5 requests/minute per IP). This resets on cold starts and does not persist across function instances.

### Timeouts

Sandbox creation and agent runs can take several seconds. Heavy workloads may need [Fluid Compute](https://vercel.com/docs/fluid-compute) or [Vercel Workflow](https://vercel.com/docs/workflow) for durable steps.

## How it works

1. Each `POST /api/run` creates a fresh [Vercel Sandbox](https://vercel.com/docs/vercel-sandbox) microVM with sample data.
2. A `SandboxAgent` with `Shell` capability receives the user's prompt.
3. The agent writes and runs shell commands inside the sandbox to answer the question.
4. The sandbox is torn down after the response is returned.

## License

MIT (match your org's policy when publishing).
