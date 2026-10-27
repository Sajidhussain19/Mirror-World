"""Live-news grounding with Tavily: what would people be reading today?"""
from __future__ import annotations

import os
import time

import httpx


async def tavily_search(query: str, usage, max_results: int = 6) -> list[dict]:
    key = os.getenv("TAVILY_API_KEY", "")
    if not key:
        return []
    t0 = time.time()
    st = usage.tiers["search"]
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post("https://api.tavily.com/search", json={
                "api_key": key, "query": query, "max_results": max_results, "search_depth": "advanced",
                "topic": "news", "days": 60, "include_answer": False,
            }, headers={"Authorization": f"Bearer {key}"})
            r.raise_for_status()
            data = r.json()
    except Exception as e:  # noqa: BLE001
        st.errors += 1
        print("tavily error", e)
        return []
    st.calls += 1
    st.latency_total += time.time() - t0
    return [{"title": x.get("title", ""), "url": x.get("url", ""), "content": (x.get("content") or "")[:700]}
            for x in data.get("results", [])]
