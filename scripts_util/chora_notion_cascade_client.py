"""Live HTTP client for chora_notion_cascade (MBSCI-9 / 2 of 2).

Wires the scaffold in chora_notion_cascade.py to real Linear + Notion APIs
via httpx.AsyncClient. Still INSERT-only; still fail-open; still feature-
flagged. Includes a self-check smoke assertion the CI job will invoke.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

try:
    import httpx  # type: ignore
except ImportError:  # pragma: no cover - httpx is optional at import time
    httpx = None  # type: ignore

from scripts_util.chora_notion_cascade import (
    ALLOWED_PLATFORMS,
    MBSCITicket,
    NotionCascadeRepair,
)

LINEAR_ENDPOINT = "https://api.linear.app/graphql"
NOTION_ENDPOINT = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"


async def fetch_linear_mbsci() -> List[MBSCITicket]:
    """Query Linear GraphQL for all MBSCI-* issues in state OOTKM Ingested."""
    if httpx is None:
        raise RuntimeError("httpx not installed; add to requirements.txt")
    key = os.environ.get("LINEAR_API_KEY", "")
    if not key:
        raise RuntimeError("LINEAR_API_KEY not set")
    query = """
    query MBSCIIngested {
      issues(filter: {
        team: { key: { eq: \"MBSCI\" } },
        state: { name: { eq: \"OOTKM Ingested\" } }
      }) {
        nodes { identifier title state { name } url }
      }
    }
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            LINEAR_ENDPOINT,
            headers={"Authorization": key, "Content-Type": "application/json"},
            json={"query": query},
        )
        resp.raise_for_status()
        nodes = resp.json()["data"]["issues"]["nodes"]
    return [
        MBSCITicket(
            identifier=n["identifier"],
            title=n["title"],
            state=n["state"]["name"],
            linear_url=n["url"],
        )
        for n in nodes
    ]


async def post_notion_page(token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if httpx is None:
        raise RuntimeError("httpx not installed; add to requirements.txt")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            NOTION_ENDPOINT,
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


def smoke_test() -> int:
    """CI smoke: verify 5-plane invariant + INSERT-only contract statically."""
    assert ALLOWED_PLATFORMS == {"github", "supabase", "linear", "notion", "tana"}, \
        "5-plane canonical set mismatch"
    # NotionCascadeRepair must not expose any UPDATE/DELETE surface.
    forbidden = {"update", "patch", "delete", "remove", "drop"}
    exposed = {name for name in dir(NotionCascadeRepair) if not name.startswith("_")}
    leaks = exposed & forbidden
    assert not leaks, f"INSERT-only contract violated: {leaks}"
    print("[chora_notion_cascade_client] smoke OK", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(smoke_test())
