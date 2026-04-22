# OpenAI Agents SDK FastAPI Starter with Vercel Sandbox

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fvercel-labs%2Fopenai-agents-fastapi-starter&env=OPENAI_API_KEY&envDescription=Your%20OpenAI%20API%20key%20for%20the%20Agents%20SDK&envLink=https%3A%2F%2Fplatform.openai.com%2Fapi-keys&project-name=openai-agents-starter&repository-name=openai-agents-starter)

Minimal [FastAPI](https://fastapi.tiangolo.com/) app that runs the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) with [Vercel Sandbox](https://vercel.com/docs/vercel-sandbox) on [Vercel's Python runtime](https://vercel.com/docs/functions/runtimes/python). Each request spins up an isolated microVM, gives the agent shell access to analyze data, and tears it down when done.

## Prerequisites

- Python 3.12+ (Vercel default is 3.12).
- A Vercel account and [Vercel CLI](https://vercel.com/docs/cli) (`npm i -g vercel`).
- An [OpenAI](https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key) or [Vercel AI Gateway](https://vercel.com/docs/ai-gateway/getting-started/text#set-up-your-api-key) API key.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI or Vercel AI Gateway API key. |
| `OPENAI_DEFAULT_MODEL` | No | Default model when the request body omits `model`. Falls back to `gpt-4.1-mini`. |
| `OPENAI_BASE_URL` | No | When using AI Gateway, set this to `https://ai-gateway.vercel.sh/v1` |

## Setup

Copy the example env file and fill in your values:

```bash
cp .env.example .env.local
```

Then edit `.env.local` with your keys:

```
OPENAI_API_KEY=sk-...
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

Vercel detects `app.py` and the `app` ASGI instance. Dependencies come from [pyproject.toml](pyproject.toml).

After deploying, set `OPENAI_API_KEY` under **Project Settings > Environment Variables**.

### Timeouts

Sandbox creation and agent runs can take several seconds. Heavy workloads may need [Fluid Compute](https://vercel.com/docs/fluid-compute) or [Vercel Workflow](https://vercel.com/docs/workflow) for durable steps.

## How it works

1. Each `POST /api/run` creates a fresh [Vercel Sandbox](https://vercel.com/docs/vercel-sandbox) microVM with sample data.
2. A `SandboxAgent` with `Shell` capability receives the user's prompt.
3. The agent writes and runs shell commands inside the sandbox to answer the question.
4. The sandbox is torn down after the response is returned.

<img width="3190" height="1106" alt="2026-04-14 at 21 54 06@2x" src="https://github.com/user-attachments/assets/773ec3a0-1369-4d5d-a311-0125958a7ce0" />

## AI Gateway

If you want to use the Vercel AI Gateway with the OpenAI Agents SDK, there are three simple changes that are needed.

1. [Create a new AI Gateway API key](https://vercel.com/docs/ai-gateway/getting-started/text#set-up-your-api-key), and set it as your `OPENAI_API_KEY` environment variable under **Project Settings > Environment Variables**.
2. Set the `OPENAI_BASE_URL` environment variable to `https://ai-gateway.vercel.sh/v1` under **Project Settings > Environment Variables**.
3. Ensure that the provider prefix on your model ID is not being stripped by setting the `model_provider=MultiProvider(openai_prefix_mode="model_id")` in your `RunConfig` as shown in the example.


## License

MIT
