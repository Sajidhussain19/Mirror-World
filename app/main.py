from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from .cases import BACKTESTS, EXAMPLES, OUTCOME_LABELS
from .llm import Router
from .personas import AUDIENCES, sample_population
from .simulate import RUNS, Run, new_run, run_simulation

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(os.getenv("RUN_CACHE", ROOT / "runs"))
CACHE.mkdir(exist_ok=True)
MAX_AGENTS = int(os.getenv("MAX_AGENTS", "1000"))
MAX_LIVE_RUNS = int(os.getenv("MAX_LIVE_RUNS", "3"))

app = FastAPI(title="Mirror World")
router = Router()


@app.on_event("startup")
async def _startup():
    await router.discover()
    print("Mirror World mode:", "LIVE" if router.live else "DEMO", router.models)


class RunReq(BaseModel):
    proposal: str = Field(min_length=10, max_length=1500)
    audience: str = "all"
    size: int = 300
    rounds: int = 3
    use_news: bool = True
    backtest_id: str | None = None
    parent_id: str | None = None
    fresh: bool = False


def _key(r: RunReq, live: bool) -> str:
    raw = json.dumps([r.proposal.strip(), r.audience, r.size, r.rounds, r.use_news, r.backtest_id, live, router.models])
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


@app.get("/api/config")
async def config():
    return {"mode": "live" if router.live else "demo", "models": router.models, "audiences": AUDIENCES,
            "examples": EXAMPLES, "backtests": [{k: v for k, v in b.items() if k not in ("actual", "actual_text")} for b in BACKTESTS],
            "outcome_labels": OUTCOME_LABELS, "max_agents": MAX_AGENTS, "tavily": bool(os.getenv("TAVILY_API_KEY"))}


@app.post("/api/run")
async def start(req: RunReq):
    if req.audience not in AUDIENCES:
        raise HTTPException(400, "unknown audience")
    req.size = max(20, min(req.size, MAX_AGENTS))
    req.rounds = max(1, min(req.rounds, 4))
    date = None
    if req.backtest_id:
        bt = next((b for b in BACKTESTS if b["id"] == req.backtest_id), None)
        if not bt:
            raise HTTPException(400, "unknown backtest")
        date = bt["date"]
        req.use_news = False
    key = _key(req, router.live)
    cached = CACHE / f"{key}.json"
    if cached.exists() and not req.fresh:
        events = json.loads(cached.read_text())
        r = new_run(proposal=req.proposal, audience=req.audience, size=req.size, rounds=req.rounds, seed=42,
                    use_news=req.use_news, date=date, backtest_id=req.backtest_id, parent_id=req.parent_id)
        r.events = events
        for e in r.events:
            if e.get("type") == "init":
                e["run_id"] = r.id
                e["parent_id"] = req.parent_id
                e["cached"] = True
        r.done = True
        return {"run_id": r.id, "cached": True}
    active = sum(1 for x in RUNS.values() if not x.done)
    if router.live and active >= MAX_LIVE_RUNS:
        raise HTTPException(429, "Simulations are busy. Try again in a minute, or pick a pre-computed example.")
    r = new_run(proposal=req.proposal, audience=req.audience, size=req.size, rounds=req.rounds, seed=42,
                use_news=req.use_news, date=date, backtest_id=req.backtest_id, parent_id=req.parent_id)

    async def go():
        await run_simulation(r, router)
        if not any(e.get("type") == "error" for e in r.events):
            cached.write_text(json.dumps(r.events))

    asyncio.create_task(go())
    return {"run_id": r.id, "cached": False}


@app.get("/api/run/{rid}/events")
async def events(rid: str, replay_speed: float = 1.0):
    r: Run | None = RUNS.get(rid)
    if not r:
        raise HTTPException(404, "run not found")

    async def gen():
        i = 0
        last_t = 0.0
        while True:
            while i < len(r.events):
                ev = r.events[i]
                if r.done and r.events and any(e.get("cached") for e in r.events[:1]):
                    # replay cached runs with compressed timing so the map still animates
                    dt = max(0.0, (ev.get("t", 0) - last_t)) / max(replay_speed, 0.1)
                    last_t = ev.get("t", 0)
                    if ev["type"] == "agent":
                        dt = min(dt, 0.012)
                    elif ev["type"] == "usage":
                        dt = 0.0
                    await asyncio.sleep(min(dt, 0.6))
                yield {"data": json.dumps(ev)}
                i += 1
            if r.done:
                return
            async with r.cond:
                try:
                    await asyncio.wait_for(r.cond.wait(), 15)
                except asyncio.TimeoutError:
                    yield {"comment": "ping"}

    return EventSourceResponse(gen())


@app.get("/api/run/{rid}")
async def run_result(rid: str):
    r = RUNS.get(rid)
    if not r:
        raise HTTPException(404)
    return JSONResponse({"done": r.done, "events": len(r.events), "result": r.result})


class AskReq(BaseModel):
    agent_id: int
    question: str = Field(min_length=1, max_length=400)
    history: list[dict] = []


@app.post("/api/run/{rid}/ask")
async def ask(rid: str, req: AskReq):
    r = RUNS.get(rid)
    if not r:
        raise HTTPException(404, "run not found")
    people = sample_population(r.size, r.audience, r.seed)
    if not 0 <= req.agent_id < len(people):
        raise HTTPException(400, "unknown agent")
    p = people[req.agent_id]
    said = [e for e in r.events if e.get("type") == "agent" and e.get("id") == p.id]
    if not router.live:
        last = said[-1]["quote"] if said else "I haven't heard much about it."
        return {"answer": f"(demo mode) Like I said: {last} Connect a Nebius key and I'll answer properly."}
    hist = "\n".join(f"Round {e['round']+1}: you said \"{e['quote']}\" (stance {e['stance']})" for e in said)
    convo = "\n".join(f"Interviewer: {h.get('q','')}\nYou: {h.get('a','')}" for h in req.history[-4:])
    date_line = f"It is {r.date}. " if r.date else ""
    system = ("You are being interviewed as a specific person in a social simulation. Stay in character: speak like them, "
              "with their concerns, vocabulary and level of knowledge. Be candid and specific, 2-4 sentences. No lists. "
              "Hinglish/regional phrasing is fine in Latin script.")
    user = (f"{date_line}YOU ARE: {p.bio()}\n\nTOPIC: \"{r.proposal}\"\n\nWHAT YOU SAID EARLIER:\n{hist or 'nothing yet'}\n\n"
            f"{convo}\nInterviewer: {req.question}\nYou:")
    try:
        ans = await router.chat("nano", system, user, r.usage, json_mode=False, max_tokens=260)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"model error: {e}") from e
    return {"answer": ans.strip().strip('"')}


@app.get("/api/runs")
async def list_runs():
    out = []
    for r in RUNS.values():
        last = next((e for e in reversed(r.events) if e.get("type") in ("phase", "error", "done")), {})
        out.append({"id": r.id, "proposal": r.proposal[:60], "done": r.done, "events": len(r.events),
                    "status": last.get("label") or last.get("message") or last.get("type"), "backtest": r.backtest_id})
    return out


@app.get("/healthz")
async def health():
    return {"ok": True, "mode": "live" if router.live else "demo"}


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
async def index():
    return FileResponse(ROOT / "static" / "index.html")
