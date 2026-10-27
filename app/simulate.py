"""Mirror World simulation engine.

Pipeline
  1. Sample N grounded personas + social graph                  (local, deterministic)
  2. (optional) Live news brief: Tavily search -> Nemotron Super  (grounding)
  3. Round 0: every agent reacts privately                         (Nemotron Nano x N, parallel)
  4. Rounds 1..R: agents hear what their contacts said & update    (Nemotron Nano x exposed agents)
  5. Theme mining over final quotes                                (Nemotron Super)
  6. Verdict, root causes, segment risks, rewrite                  (Nemotron Ultra, thinking on)
"""
from __future__ import annotations

import asyncio
import random
import statistics
import time
import uuid
from dataclasses import dataclass, field

from . import mock
from .cases import BACKTESTS, classify
from .grounding import tavily_search
from .llm import Router, Usage
from .personas import AUDIENCES, Persona, sample_population

AGENT_SYSTEM = (
    "You are role-playing ONE specific Indian person in a social simulation. Stay fully in character: their income, job, "
    "age, region, values and comfort with technology shape what they notice, what they care about and how they talk. "
    "Do NOT be balanced, polite or diplomatic. Real people are often indifferent, cynical, confused, practical or emotional. "
    "A daily-wage worker and a software engineer react very differently. Many people barely care. "
    "Reply with a single JSON object and nothing else."
)

JSON_SPEC = (
    '{"stance": <integer -2 strongly against, -1 against, 0 neutral/don\'t care, 1 for, 2 strongly for>, '
    '"adopt": <true if you would go along with it in practice (use it, buy it, keep using the service, comply), false if you would avoid, switch, resist or ignore it>, '
    '"emotion": "<one word>", '
    '"quote": "<what you would actually say to a friend about it, max 25 words, in your natural voice; Hinglish or regional phrasing is fine but write in Latin script>", '
    '"share": <true if you would forward/post/talk about this, else false>}'
)

SUPER_THEMES = (
    "You analyse results from a simulated society. Group the reactions into 4-6 distinct THEMES that explain WHY people "
    "feel the way they do. Be specific and concrete (not generic like 'cost concerns'). Return JSON: "
    '{"themes":[{"label":"<short punchy theme name>","sentiment":"positive|negative|mixed","share_pct":<int share of reactions>,'
    '"who":"<which kinds of people hold it>","quote":"<one representative quote copied from the data>"}]}'
)

SUPER_NEWS = (
    "You brief a simulated population on what ordinary Indians would currently be hearing about a topic. "
    "From the search results, write 3-5 short neutral bullets (max 22 words each) of real, recent context "
    "(prices, related events, public mood, competitor moves). No opinions. Return JSON: "
    '{"bullets":["..."],"query_used":"..."}'
)

ULTRA_REPORT = (
    "You are a world-class strategist reading the output of a large agent-based simulation of Indian society reacting to "
    "a proposal. Reason carefully over the numbers by segment, the themes and how opinion moved between rounds. Then give a "
    "decisive, specific verdict a CEO or policymaker could act on. Avoid platitudes. Return JSON only:\n"
    '{"headline":"<one sharp sentence verdict>",'
    '"prediction":"embraced|accepted|rejected",'
    '"confidence":<0-100>,'
    '"summary":"<3 sentences: what happens, who drives it, why>",'
    '"drivers":[{"factor":"...","direction":"+|-","explanation":"<cite segment numbers>"}],'
    '"segments_at_risk":[{"segment":"...","why":"..."}],'
    '"surprise":"<the most non-obvious insight in the data>",'
    '"fix":"<the single change most likely to flip the biggest opposing segment>",'
    '"rewrite":"<the full proposal rewritten with that fix, similar length, same intent>",'
    '"watch_outs":["..."]}'
)


@dataclass
class Run:
    id: str
    proposal: str
    audience: str
    size: int
    rounds: int
    seed: int
    use_news: bool
    date: str | None = None
    backtest_id: str | None = None
    parent_id: str | None = None
    events: list[dict] = field(default_factory=list)
    cond: asyncio.Condition = field(default_factory=asyncio.Condition)
    done: bool = False
    usage: Usage = field(default_factory=Usage)
    result: dict = field(default_factory=dict)

    async def emit(self, ev: dict):
        ev["t"] = round(time.time() - self.usage.started, 2)
        self.events.append(ev)
        async with self.cond:
            self.cond.notify_all()


RUNS: dict[str, Run] = {}


def segment_metrics(people: list[Persona], state: dict[int, dict]) -> dict:
    vals = [state[p.id] for p in people if p.id in state]
    if not vals:
        return {}
    n = len(vals)
    out = {
        "n": n,
        "net_sentiment": round(statistics.mean(v["stance"] for v in vals), 3),
        "support": round(sum(v["stance"] > 0 for v in vals) / n, 3),
        "oppose": round(sum(v["stance"] < 0 for v in vals) / n, 3),
        "neutral": round(sum(v["stance"] == 0 for v in vals) / n, 3),
        "adoption": round(sum(bool(v["adopt"]) for v in vals) / n, 3),
        "virality": round(sum(bool(v["share"]) for v in vals) / n, 3),
        "segments": {},
    }
    dims = {
        "Age": lambda p: p.age_group,
        "Setting": lambda p: "Urban" if p.urban else "Rural",
        "Income": lambda p: p.income,
        "Region": lambda p: p.region,
        "Gender": lambda p: "Men" if p.gender == "M" else "Women",
    }
    order = {"Income": ["< ₹15k", "₹15–35k", "₹35–75k", "₹75k–2L", "> ₹2L"],
             "Age": ["18–24", "25–34", "35–44", "45–59", "60+"]}
    for dim, fn in dims.items():
        groups: dict[str, list[dict]] = {}
        for p in people:
            if p.id in state:
                groups.setdefault(fn(p), []).append(state[p.id])
        keys = [k for k in order.get(dim, sorted(groups)) if k in groups]
        out["segments"][dim] = [
            {"label": k, "n": len(groups[k]),
             "net": round(statistics.mean(v["stance"] for v in groups[k]), 2),
             "adoption": round(sum(bool(v["adopt"]) for v in groups[k]) / len(groups[k]), 2)}
            for k in keys]
    return out


def _clean(r: dict) -> dict:
    try:
        stance = int(round(float(r.get("stance", 0))))
    except (TypeError, ValueError):
        stance = 0
    stance = max(-2, min(2, stance))

    def b(x):
        return x if isinstance(x, bool) else str(x).strip().lower() in ("true", "yes", "1")

    return {"stance": stance, "adopt": b(r.get("adopt", stance >= 0)), "emotion": str(r.get("emotion", ""))[:20],
            "quote": str(r.get("quote", "")).strip().strip('"')[:220], "share": b(r.get("share", False))}


async def run_simulation(run: Run, router: Router):
    usage = run.usage
    people = sample_population(run.size, run.audience, run.seed)
    live = router.live
    await run.emit({"type": "init", "run_id": run.id, "proposal": run.proposal, "audience": run.audience,
                    "audience_label": AUDIENCES.get(run.audience, run.audience), "mode": "live" if live else "demo",
                    "models": router.models if live else {"nano": "mock", "super": "mock", "ultra": "mock"},
                    "rounds": run.rounds, "parent_id": run.parent_id, "backtest_id": run.backtest_id, "date": run.date,
                    "agents": [{k: v for k, v in p.public().items() if k not in ("values", "apps", "neighbors")} | {"nb": p.neighbors}
                               for p in people]})

    ticker_stop = asyncio.Event()

    async def ticker():
        while not ticker_stop.is_set():
            await run.emit({"type": "usage", **usage.to_dict(router.models)})
            try:
                await asyncio.wait_for(ticker_stop.wait(), 1.0)
            except asyncio.TimeoutError:
                pass

    tick = asyncio.create_task(ticker())
    try:
        # ---- 1. grounding --------------------------------------------------
        news: list[str] = []
        if run.use_news and live and not run.backtest_id:
            await run.emit({"type": "phase", "phase": "news", "label": "Reading today's news (Tavily → Nemotron Super)"})
            q = await router.chat("super", "Write one web search query (max 12 words) to find recent Indian news context for this proposal. Return JSON {\"query\":\"...\"}",
                                  run.proposal, usage)
            query = q.get("query") or run.proposal[:120]
            results = await tavily_search(query, usage)
            if results:
                ctx = "\n\n".join(f"[{i+1}] {r['title']}\n{r['content']}" for i, r in enumerate(results))
                brief = await router.chat("super", SUPER_NEWS, f"PROPOSAL: {run.proposal}\n\nSEARCH RESULTS:\n{ctx}", usage)
                news = [str(b) for b in brief.get("bullets", [])][:5]
                await run.emit({"type": "news", "query": query, "bullets": news,
                                "sources": [{"title": r["title"], "url": r["url"]} for r in results]})

        date_line = f"It is {run.date}. You only know what a person would know at that time.\n" if run.date else ""
        news_block = ("Things you've been hearing lately:\n" + "\n".join(f"- {b}" for b in news) + "\n\n") if news else ""

        state: dict[int, dict] = {}
        history: list[dict] = []

        async def react(p: Persona, r_idx: int, heard: list[dict]):
            prev = state.get(p.id)
            if not live:
                await mock.mock_delay()
                return p, mock.agent_reaction(p, run.proposal, r_idx, prev, heard)
            if r_idx == 0:
                user = (f"{date_line}YOU ARE: {p.bio()}\n\n{news_block}"
                        f"YOU JUST HEARD ABOUT THIS:\n\"{run.proposal}\"\n\nHow do you react? JSON: {JSON_SPEC}")
            else:
                said = "\n".join(f"- {h['name']} ({h['occupation']}, {h['place']}): \"{h['quote']}\"" for h in heard)
                user = (f"{date_line}YOU ARE: {p.bio()}\n\nTHE PROPOSAL:\n\"{run.proposal}\"\n\n"
                        f"Earlier you said: \"{prev['quote']}\" (stance {prev['stance']}).\n\n"
                        f"Since then, people you know said:\n{said}\n\n"
                        "Has your view changed? People rarely flip completely; shift only if something genuinely persuades or "
                        f"worries you. JSON: {JSON_SPEC}")
            try:
                return p, _clean(await router.chat("nano", AGENT_SYSTEM, user, usage))
            except Exception as e:  # noqa: BLE001
                print("agent fail", p.id, e)
                return p, None

        rng = random.Random(run.seed)
        for r_idx in range(run.rounds):
            if r_idx == 0:
                cohort = [(p, []) for p in people]
                label = f"Round 1 · {len(people)} agents react privately (Nemotron Nano)"
            else:
                cohort = []
                for p in people:
                    if p.id not in state:
                        continue
                    talkers = [j for j in p.neighbors if j in state and (state[j]["share"] or rng.random() < 0.25)]
                    if not talkers:
                        continue
                    rng.shuffle(talkers)
                    heard = [{"id": j, "name": people[j].name, "occupation": people[j].occupation, "place": people[j].place,
                              "quote": state[j]["quote"], "stance": state[j]["stance"]} for j in talkers[:3]]
                    cohort.append((p, heard))
                label = f"Round {r_idx+1} · {len(cohort)} agents hear from their network and update"
            await run.emit({"type": "phase", "phase": "round", "round": r_idx, "label": label, "cohort": len(cohort)})
            flips = 0
            tasks = [asyncio.create_task(react(p, r_idx, heard)) for p, heard in cohort]
            heard_map = {p.id: heard for p, heard in cohort}
            new_state = dict(state)
            for fut in asyncio.as_completed(tasks):
                p, res = await fut
                if res is None:
                    continue
                prev = state.get(p.id)
                if prev and (prev["stance"] > 0) != (res["stance"] > 0) and (prev["stance"] < 0) != (res["stance"] < 0):
                    flips += 1
                new_state[p.id] = res
                await run.emit({"type": "agent", "round": r_idx, "id": p.id, **res,
                                "from": [h["id"] for h in heard_map.get(p.id, [])]})
            state = new_state
            m = segment_metrics(people, state)
            m["round"] = r_idx
            m["flips"] = flips
            history.append({k: v for k, v in m.items() if k != "segments"})
            await run.emit({"type": "metrics", **m})

        final = segment_metrics(people, state)

        # ---- 5. themes (Super) ------------------------------------------------
        await run.emit({"type": "phase", "phase": "themes", "label": "Mining themes from every voice (Nemotron Super)"})
        sample_ids = list(state)
        random.Random(run.seed).shuffle(sample_ids)
        sample = [{"who": f"{people[i].age}{people[i].gender}, {people[i].occupation}, {people[i].place}, {people[i].income}",
                   "stance": state[i]["stance"], "quote": state[i]["quote"]} for i in sample_ids[:90]]
        if live:
            data = "\n".join(f"[{s['stance']:+d}] ({s['who']}) {s['quote']}" for s in sample)
            th = await router.chat("super", SUPER_THEMES, f"PROPOSAL: {run.proposal}\n\nREACTIONS (stance, who, quote):\n{data}", usage)
        else:
            await asyncio.sleep(0.6)
            th = mock.themes(sample)
        await run.emit({"type": "themes", **th})

        # ---- 6. verdict (Ultra) ------------------------------------------------
        await run.emit({"type": "phase", "phase": "report", "label": "Reasoning over the whole society (Nemotron Ultra)"})
        if live:
            seg_txt = "\n".join(f"{dim}: " + "; ".join(f"{s['label']} n={s['n']} net={s['net']:+.2f} adopt={s['adoption']:.0%}" for s in segs)
                                for dim, segs in final["segments"].items())
            hist_txt = "\n".join(f"round {h['round']+1}: net={h['net_sentiment']:+.2f} support={h['support']:.0%} oppose={h['oppose']:.0%} "
                                 f"adopt={h['adoption']:.0%} share={h['virality']:.0%} flips={h['flips']}" for h in history)
            pos = [s for s in sample if s["stance"] > 0][:8]
            neg = [s for s in sample if s["stance"] < 0][:8]
            user = (f"{date_line}PROPOSAL: {run.proposal}\nAUDIENCE: {AUDIENCES.get(run.audience)} (n={final['n']})\n"
                    + (f"NEWS CONTEXT: {' | '.join(news)}\n" if news else "")
                    + f"\nOPINION DYNAMICS:\n{hist_txt}\n\nFINAL SEGMENTS:\n{seg_txt}\n\nTHEMES: {th}\n\n"
                    f"SAMPLE SUPPORTERS: {pos}\nSAMPLE OPPONENTS: {neg}")
            rep = await router.chat("ultra", ULTRA_REPORT, user, usage)
        else:
            await asyncio.sleep(0.8)
            rep = mock.report(run.proposal, final, th)
        sim_class = classify(final["net_sentiment"], final["adoption"])
        rep["sim_outcome"] = sim_class
        if run.backtest_id:
            bt = next(b for b in BACKTESTS if b["id"] == run.backtest_id)
            rep["backtest"] = {"actual": bt["actual"], "actual_text": bt["actual_text"],
                               "match_sim": sim_class == bt["actual"], "match_ultra": rep.get("prediction") == bt["actual"]}
        await run.emit({"type": "report", **rep})
        run.result = {"final": final, "history": history, "report": rep}
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        await run.emit({"type": "error", "message": str(e)[:400]})
    finally:
        ticker_stop.set()
        await tick
        await run.emit({"type": "usage", **usage.to_dict(router.models)})
        await run.emit({"type": "done"})
        run.done = True


def new_run(**kw) -> Run:
    rid = uuid.uuid4().hex[:10]
    r = Run(id=rid, **kw)
    RUNS[rid] = r
    return r
