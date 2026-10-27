# Feedback on Nebius Token Factory & NVIDIA tools

_Personalise these notes with your own experience before submitting._

## What worked well
- **OpenAI-compatible API**: we dropped in the official `openai` Python SDK with a different `base_url` and had zero integration friction.
- **Concurrency**: Token Factory handled 64-way concurrent Nano calls steadily, which is what makes a 1,000-agent society feel real-time.
- **Nemotron tiering**: having Nano, Super and Ultra behind one endpoint made "right-size every call" routing trivial. The quality jump to Ultra for the final reasoning is clear.
- **`/v1/models`**: auto-discovering Nemotron IDs meant no hard-coded model names.

## What could be better
- Clearer docs on toggling Nemotron reasoning ("thinking") per request (system-prompt `/no_think` vs `chat_template_kwargs`).
- A batch / bulk-completions endpoint for agent-simulation workloads (thousands of short prompts sharing a long prefix) would cut cost and latency further. Prefix-caching visibility in the usage object would help too.
- Per-model rate-limit headers, so clients can adapt concurrency automatically.
- A Serverless Endpoints example for a plain web app (FastAPI + env vars), not only model servers.
