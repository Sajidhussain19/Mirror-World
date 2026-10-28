"""Model router for Nebius Token Factory (OpenAI-compatible).

Three tiers, picked per task:
  nano  -> thousands of cheap, fast persona reactions
  super -> synthesis: news briefs, theme clustering
  ultra -> deep reasoning: final verdict, root causes, rewrite
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field

from openai import AsyncOpenAI

BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")

# Sensible defaults; override with env vars. Auto-discovery fills gaps at startup.
DEFAULT_MODELS = {
    "nano": os.getenv("MODEL_NANO", ""),
    "super": os.getenv("MODEL_SUPER", ""),
    "ultra": os.getenv("MODEL_ULTRA", ""),
}

TIER_PARAMS = {
    "nano": dict(max_tokens=220, temperature=0.9),
    "super": dict(max_tokens=1600, temperature=0.4),
    "ultra": dict(max_tokens=6000, temperature=0.4),
}


@dataclass
class TierStats:
    calls: int = 0
    errors: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_total: float = 0.0

    def to_dict(self):
        return dict(calls=self.calls, errors=self.errors, prompt_tokens=self.prompt_tokens,
                    completion_tokens=self.completion_tokens,
                    avg_latency=round(self.latency_total / self.calls, 2) if self.calls else 0)


@dataclass
class Usage:
    tiers: dict[str, TierStats] = field(default_factory=lambda: {t: TierStats() for t in ("nano", "super", "ultra", "search")})
    started: float = field(default_factory=time.time)

    def to_dict(self, models: dict[str, str]):
        tot = sum(t.prompt_tokens + t.completion_tokens for t in self.tiers.values())
        el = max(time.time() - self.started, 0.001)
        return dict(tiers={k: {**v.to_dict(), "model": models.get(k, "tavily" if k == "search" else "")}
                           for k, v in self.tiers.items()},
                    total_tokens=tot, elapsed=round(el, 1), tokens_per_sec=round(tot / el))


THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def extract_json(text: str):
    text = THINK_RE.sub("", text or "")
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
    if start < 0:
        raise ValueError("no json found")
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    # truncated: best-effort repair
    return json.loads(text[start:] + closer)


class Router:
    def __init__(self, api_key: str | None = None, models: dict[str, str] | None = None, concurrency: int = 64):
        self.api_key = api_key or os.getenv("NEBIUS_API_KEY", "")
        self.models = dict(DEFAULT_MODELS)
        if models:
            self.models.update({k: v for k, v in models.items() if v})
        self.client = AsyncOpenAI(base_url=BASE_URL, api_key=self.api_key, timeout=180, max_retries=2) if self.api_key else None
        self.sem = asyncio.Semaphore(int(os.getenv("CONCURRENCY", concurrency)))
        self.available: list[str] = []
        self.discovery_error = ""

    @property
    def live(self) -> bool:
        return self.client is not None

    async def discover(self) -> dict[str, str]:
        """Find NVIDIA Nemotron models on the account and fill missing tiers."""
        if not self.client:
            return self.models
        try:
            res = await self.client.models.list()
            ids = [m.id for m in res.data]
        except Exception as e:  # noqa: BLE001
            print("model discovery failed:", e)
            self.discovery_error = str(e)[:300]
            if not all(self.models.values()):
                print("!! Could not reach Nebius Token Factory and no MODEL_* env vars set -> falling back to DEMO mode")
                self.client = None
            return self.models
        self.available = ids
        nem = [i for i in ids if "nemotron" in i.lower()]

        def pick(*keys, avoid=("embed", "reward", "vl", "parse", "safety", "guard", "rerank")):
            for k in keys:
                for i in nem:
                    low = i.lower()
                    if k in low and not any(a in low for a in avoid):
                        return i
            return ""

        if not self.models["nano"]:
            self.models["nano"] = pick("nano")
        if not self.models["super"]:
            self.models["super"] = pick("super", "70b", "49b")
        if not self.models["ultra"]:
            self.models["ultra"] = pick("ultra", "253b", "super")
        fallback = self.models["super"] or self.models["nano"] or self.models["ultra"]
        for t in ("nano", "super", "ultra"):
            self.models[t] = self.models[t] or fallback
        return self.models

    async def chat(self, tier: str, system: str, user: str, usage: Usage, *, json_mode: bool = True,
                   thinking: bool | None = None, max_tokens: int | None = None):
        assert self.client
        params = dict(TIER_PARAMS[tier])
        if max_tokens:
            params["max_tokens"] = max_tokens
        think = (tier == "ultra") if thinking is None else thinking
        sys = system if think else "/no_think\n" + system
        extra = {"chat_template_kwargs": {"enable_thinking": think}}
        st = usage.tiers[tier]
        last_err = None
        for attempt in range(3):
            async with self.sem:
                t0 = time.time()
                try:
                    r = await self.client.chat.completions.create(
                        model=self.models[tier], messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
                        extra_body=extra, **params)
                except Exception as e:  # noqa: BLE001
                    st.errors += 1
                    last_err = e
                    if "chat_template_kwargs" in str(e) or "extra" in str(e).lower():
                        extra = {}
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                st.calls += 1
                st.latency_total += time.time() - t0
                if r.usage:
                    st.prompt_tokens += r.usage.prompt_tokens or 0
                    st.completion_tokens += r.usage.completion_tokens or 0
            msg = r.choices[0].message
            text = msg.content or ""
            if not json_mode:
                return THINK_RE.sub("", text).split("</think>")[-1].strip()
            try:
                return extract_json(text)
            except Exception as e:  # noqa: BLE001
                last_err = e
                rc = getattr(msg, "reasoning_content", None)
                if rc:
                    try:
                        return extract_json(rc)
                    except Exception:  # noqa: BLE001
                        pass
                st.errors += 1
                user = user + "\n\nReturn ONLY valid JSON. No prose."
        raise RuntimeError(f"{tier} call failed: {last_err}")
