"""Offline demo backend: deterministic heuristics that mimic model output so the
UI can be developed and demoed without an API key. Clearly flagged in the UI."""
from __future__ import annotations

import asyncio
import hashlib
import random

NEG = ["fee", "charge", "tax", "surge", "increase", "hike", "mandatory", "ban", "penalty", "10 hours", "only", "limited"]
POS = ["free", "discount", "cashback", "no change in salary", "unlimited", "cheaper", "save", "4-day", "reward", "waived", "shows exactly", "capped"]
PRIV = ["data", "track", "facebook", "privacy", "chosen by"]

QUOTES = {
    -2: ["Bilkul nahi. Already sab mehenga hai, ab ye bhi?", "This is pure loot, I'm uninstalling.", "Who asked for this? Total scam.",
         "Hum jaise logon ka koi nahi sochta.", "Enough. Switching to something else today."],
    -1: ["Not happy, but let's see how it goes.", "Thoda zyada ho gaya ye.", "Sounds good on paper, but I don't trust it.",
         "I'll probably use it less now.", "Paisa kahan jaayega, ye koi nahi batayega."],
    0: ["Mujhe kya farak padta hai.", "Don't really understand it, will ask my son.", "Haven't thought about it much.",
        "Depends on what others do.", "Let's wait and watch."],
    1: ["Actually not bad, makes sense.", "If it really helps, theek hai.", "I'd try it once.", "Fair enough, kuch toh change chahiye.",
        "Could be useful for people like me."],
    2: ["Finally! This is exactly what we needed.", "Love it, sharing with everyone.", "Great move, about time.",
        "Ek number idea hai!", "Count me in, signing up today."],
}
EMOTIONS = {-2: "angry", -1: "annoyed", 0: "indifferent", 1: "hopeful", 2: "excited"}


def _h(*parts) -> random.Random:
    return random.Random(int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:8], 16))


def agent_reaction(persona, proposal: str, round_idx: int, prev: dict | None, heard: list[dict]) -> dict:
    p = proposal.lower()
    rng = _h(persona.id, proposal[:80], round_idx)
    score = 0.0
    neg = sum(w in p for w in NEG)
    pos = sum(w in p for w in POS)
    ps = {"very high": 1.6, "high": 1.1, "medium": 0.6, "low": 0.2}[persona.price_sensitivity]
    score -= neg * 0.55 * ps
    score += pos * 0.6
    if any(w in p for w in PRIV) and "privacy-minded" in persona.values:
        score -= 1.2
    if "sceptical of big companies" in persona.values:
        score -= 0.5
    if "early adopter" in persona.values or persona.tech_comfort in ("high", "very high"):
        score += 0.6
    if "delivery partner" in p and persona.occupation in ("food delivery partner", "gig worker (ride-hailing)"):
        score += 1.5
    score += rng.gauss(0, 0.8)
    if prev is not None:
        social = sum(h["stance"] for h in heard) / max(len(heard), 1) if heard else prev["stance"]
        score = 0.65 * prev["stance"] + 0.35 * social + rng.gauss(0, 0.3)
    stance = max(-2, min(2, round(score)))
    adopt = (stance >= 0) or (rng.random() < 0.35 * (1 if persona.price_sensitivity in ("low", "medium") else 0.5))
    share = rng.random() < (0.15 + 0.15 * abs(stance) + (0.1 if persona.tech_comfort in ("high", "very high") else 0))
    quote = rng.choice(QUOTES[stance])
    if prev is not None and stance == prev["stance"]:
        quote = prev["quote"]
    return {"stance": stance, "adopt": bool(adopt), "emotion": EMOTIONS[stance], "quote": quote, "share": share}


async def mock_delay():
    await asyncio.sleep(random.uniform(0.02, 0.12))


def themes(sample: list[dict]) -> dict:
    neg = [s for s in sample if s["stance"] < 0]
    pos = [s for s in sample if s["stance"] > 0]
    out = []
    if neg:
        out.append({"label": "Feels like another hidden charge", "sentiment": "negative", "share_pct": round(100 * len(neg) / len(sample)),
                    "who": "price-sensitive, lower-income households", "quote": neg[0]["quote"]})
        out.append({"label": "Distrust of where the money goes", "sentiment": "negative", "share_pct": round(40 * len(neg) / len(sample)),
                    "who": "people sceptical of big companies", "quote": neg[-1]["quote"]})
    if pos:
        out.append({"label": "Fair if the benefit is visible", "sentiment": "positive", "share_pct": round(100 * len(pos) / len(sample)),
                    "who": "urban, higher-income, tech-comfortable users", "quote": pos[0]["quote"]})
    out.append({"label": "Indifferent / wait-and-watch", "sentiment": "mixed", "share_pct": round(100 * sum(s["stance"] == 0 for s in sample) / len(sample)),
                "who": "older and rural respondents", "quote": QUOTES[0][0]})
    return {"themes": out}


def report(proposal: str, metrics: dict, themes_: dict) -> dict:
    ns = metrics["net_sentiment"]
    pred = "embraced" if ns > 0.35 and metrics["adoption"] > 0.6 else "accepted" if metrics["adoption"] > 0.45 else "rejected"
    return {
        "headline": f"[Demo mode] Net sentiment {ns:+.2f}: likely {pred}.",
        "prediction": pred,
        "confidence": 55,
        "summary": "This report was generated by the offline heuristic engine. Connect a Nebius Token Factory key for "
                   "Nemotron Ultra reasoning over the full simulation.",
        "drivers": [{"factor": "Price sensitivity", "direction": "-", "explanation": "Lower-income segments react to any added cost."},
                    {"factor": "Visible benefit", "direction": "+", "explanation": "Support rises when people can see who benefits."}],
        "segments_at_risk": [{"segment": "Households under ₹15k/month", "why": "Every rupee is noticed."}],
        "surprise": "Opinion spreads mostly within states, so regional clusters harden after round 2.",
        "fix": "Make the benefit concrete and cap the cost for small orders.",
        "rewrite": proposal + " The fee is waived on orders under ₹200, and the app shows exactly how much each rider received.",
        "watch_outs": ["Social-media pile-on in the first 48 hours"],
    }
