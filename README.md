# 🪞 Mirror World

**Rehearse any decision on a simulated India before reality votes.**

Type a policy, a price change, a product launch or an ad. Mirror World creates a society of up to **1,000 grounded Indian personas**: farmers in Bihar, delivery partners in Hyderabad, homemakers in Kochi and software engineers in Bengaluru. Each persona reacts in character, talks to its contacts over several rounds of word of mouth, and changes its mind (or doesn't). Then **NVIDIA Nemotron Ultra** reasons over the whole society. It tells you who breaks and why, and gives the single change most likely to flip the opposition. Click **Rerun** and the same 1,000 people react to the rewritten version, so you can watch the map turn from red to green.

> Built for the **Nebius × NVIDIA Global AI Hackathon** · Track: **Best Apps and Agents**
> Runs on **Nebius Token Factory** with **NVIDIA Nemotron Nano, Super & Ultra**, plus **Tavily** for live grounding.

🔗 **Live demo:** _<your deployed URL>_ · 🎬 **Video:** _<YouTube link>_

---

## Why this exists

Every big decision in India is a bet on how 1.4 billion very different people will react. Examples include Facebook's Free Basics, the platform fees on food apps, UPI charges and work-week rules. Companies and governments usually find out *after* launch, from a social-media pile-on. Focus groups are slow, expensive, urban-biased and come in sample sizes of 12.

Mirror World gives a product manager, a policy analyst or a founder a **1,000-person stress test in about a minute for a few rupees of tokens**. It isn't meant to replace research. It shows you the blind spots before you commit.

## What makes it different

| | |
|---|---|
| **Grounded population** | Personas are sampled from Census-of-India-style marginals: state population shares, urban/rural split by state, age bands, household income bands, occupations conditional on setting, age and income, languages, values and app usage. They're reproducible from a seed. |
| **Social contagion** | Agents sit in a small-world, homophilous social graph (local ties in the same state, peer ties in the same age group and random long-range ties). In each round, agents hear what their contacts actually said and update. On the map you can watch backlash travel along the network. |
| **Model routing** | Each task goes to the smallest Nemotron model that can do it well (see below). Thousands of Nano calls run in parallel on Token Factory. Ultra runs only once per simulation, with thinking turned on. |
| **Rewrite → rerun → A/B** | Ultra writes the fix, and the *same* people (same seed, same graph) react again. Deltas are shown per segment. |
| **Backtests** | Replays of real decisions (Free Basics 2015, Zomato's platform fee 2023, Reels after the TikTok ban 2020). Agents are told the date. The real outcome is hidden from every model and revealed only after the run. |
| **Interviews** | Click any dot to interview that person: *"What would change your mind?"* They answer in character, with memory of what they said in each round. |
| **Live news** | Before reacting, agents read a neutral brief of today's news on the topic. Tavily searches and Nemotron Super condenses the results. |

## How it works

```
                ┌──────────────────────────────────────────────────────────┐
 proposal ───►  │ 1. Population sampler + social graph   (local, seeded)   │
                │ 2. Tavily search ─► Nemotron SUPER news brief            │
                │ 3. Round 1: N × Nemotron NANO private reactions          │──► SSE stream ─► live map
                │ 4. Rounds 2..R: exposed agents × NANO (word of mouth)    │
                │ 5. Nemotron SUPER: theme mining over every voice         │
                │ 6. Nemotron ULTRA (thinking on): verdict, drivers,       │
                │    segments at risk, surprise, fix, full rewrite         │
                └──────────────────────────────────────────────────────────┘
```

### NVIDIA Nemotron on Nebius Token Factory: model routing

| Tier | Model (auto-discovered, overridable) | Used for | Volume per 1,000-agent run |
|---|---|---|---|
| **Nano** | `MODEL_NANO` | Persona reactions, word-of-mouth updates, interviews | ~2,000–3,000 calls, run in parallel |
| **Super** | `MODEL_SUPER` | Search-query writing, news brief, theme clustering | 3 calls |
| **Ultra** | `MODEL_ULTRA` | Final reasoning, root causes, rewrite | 1 call (thinking on) |

The **Engine room** panel in the UI shows live call counts, tokens, latency and throughput for each tier.

**Where Token Factory sped things up:** the whole product depends on cheap, highly concurrent inference. A 1,000-agent, 3-round simulation is about 2,500 LLM calls. Token Factory's OpenAI-compatible API let us fire them with 64-way concurrency from one async Python process and route each tier to a different Nemotron model with no extra infrastructure. Nano's speed is what makes the map animate in real time.

## Run it locally

```bash
git clone https://github.com/<you>/mirror-world && cd mirror-world
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # add NEBIUS_API_KEY (and optionally TAVILY_API_KEY)
set -a && source .env && set +a
uvicorn app.main:app --reload --port 8000
# open http://localhost:8000
```

If you don't set a key, the app runs in **demo mode**. A deterministic offline engine lets you explore the UI, and the mode is clearly labelled.

Tests: `pip install pytest && pytest -q`

## Deploy

**Docker (anywhere):**
```bash
docker build -t mirror-world .
docker run -p 8080:8080 -e NEBIUS_API_KEY=... -e TAVILY_API_KEY=... mirror-world
```

**Nebius Serverless Endpoint (CPU container):**
```bash
# push the image to a registry Nebius can pull from, then:
nebius ai endpoint create \
  --name mirror-world --image <registry>/mirror-world:latest \
  --platform cpu-d3 --preset 4vcpu-16gb --container-port 8080 \
  --public --subnet-id <subnet_ID>
# set NEBIUS_API_KEY / TAVILY_API_KEY as env vars (see `nebius ai endpoint create --help`)
```

Simulations you've already run are cached in `runs/`, so example scenarios replay instantly and cost nothing for repeat viewers. Ship the image with a warm cache for judging.

## Honest limitations

- **This is a simulation, not a poll.** LLM personas can reflect model biases and stereotypes. We ground them with demographic marginals and ask for in-character, non-diplomatic answers, but the outputs are hypotheses to test, not facts.
- **Backtests can leak.** The models may have seen the historical outcomes in pre-training. We reduce this by framing the date, hiding the outcome from every prompt and scoring the aggregate behaviour rather than asking "what happened?". Treat backtests as a sanity check, not proof.
- Marginals are approximations of Census 2011 / survey data, not a calibrated sample frame.

## Project structure

```
app/
  personas.py   population sampler + small-world social graph
  llm.py        Token Factory router (Nano/Super/Ultra), JSON repair, usage meter
  simulate.py   the simulation pipeline + SSE event bus
  grounding.py  Tavily live-news search
  cases.py      example scenarios + historical backtests
  mock.py       offline demo engine
  main.py       FastAPI app (REST + Server-Sent Events + interviews)
static/         zero-build front-end (canvas map, live KPIs, report, A/B)
tests/          pytest suite
```

## Feedback on Nebius & NVIDIA tools

See [`docs/FEEDBACK.md`](docs/FEEDBACK.md).

## Credits & license

- Code: **MIT** (see `LICENSE`).
- India boundary: [DataMeet India community](https://github.com/datameet/maps), CC BY 4.0, simplified.
- Models: NVIDIA Nemotron family (open models) served by Nebius Token Factory.
