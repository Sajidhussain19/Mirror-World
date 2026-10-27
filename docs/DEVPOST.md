# Devpost submission text

**Project name:** Mirror World
**Tagline:** Rehearse any decision on a simulated India before reality votes.
**Track:** Best Apps and Agents

## Inspiration
Facebook's Free Basics died in a nationwide backlash. Food apps learned how far a ₹2 platform fee could stretch. Every big decision in India is a bet on how 1.4 billion very different people will react, and teams usually find out *after* launch. Focus groups are slow, expensive, urban-biased and come in sample sizes of 12. We wanted a 1,000-person stress test you can run in a minute.

## What it does
Type any proposal: a policy, a price change, a product launch. Mirror World creates a society of up to 1,000 grounded Indian personas, sampled from Census-of-India–style distributions of state, urban/rural setting, age, income, occupation, language and values, and connects them in a social graph.
- **NVIDIA Nemotron Nano** agents react in character, in parallel. Over several rounds they hear what their contacts said and update their views. You watch opinion spread across a live map of India.
- **Nemotron Super** writes a live-news brief from **Tavily** search results for agents to read first, and later mines themes from every voice.
- **Nemotron Ultra** (thinking on) reasons over the full society: the verdict, the drivers backed by segment numbers, who is at risk, a non-obvious insight, and the single change most likely to flip the opposition, written out as a full rewrite.
- One click reruns the **same people** on the rewrite, with an A/B comparison per segment.
- **Backtests** replay real history (Free Basics 2015, Zomato's platform fee 2023, Reels after the TikTok ban 2020) with the outcome hidden from every model.
- **Interviews**: click any person and ask them why.

## How we built it
FastAPI + asyncio backend that streams Server-Sent Events into a zero-build canvas front end. A model router sends each task to the smallest Nemotron tier that can do it well on **Nebius Token Factory** (OpenAI-compatible), with 64-way concurrency, robust JSON repair for reasoning models, and a live usage meter (the Engine room). Completed runs are cached, so examples replay instantly for free.

## Challenges
- Getting *non-diplomatic*, in-character reactions instead of balanced "AI answers".
- Designing word of mouth so only exposed agents are re-queried, which keeps cost linear.
- Parsing JSON reliably from reasoning models.
- Avoiding hindsight leakage in backtests.

## Accomplishments
- A 1,000-agent society with about 2,500 Nemotron calls per run, streamed live.
- A rewrite → rerun → A/B loop that turns insight into action.
- Honest backtests against real Indian history.

## What we learned
Small, fast models at massive scale plus one large reasoning model over the aggregate beats any single model alone. Social structure matters: the same people give different answers once they talk to each other.

## What's next
Calibrating against public survey data (CSDS, NFHS). Voice interviews in Indian languages. Uploading your own customer segments. An API for running a "pre-mortem" in CI before a pricing change ships.

## Built with
nvidia-nemotron, nebius-token-factory, tavily, python, fastapi, asyncio, server-sent-events, javascript, canvas
