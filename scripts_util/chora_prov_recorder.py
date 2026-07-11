"""CHORA LABS: PROV-O Async Recorder (MBSCI-8)

Records JSON-RPC tool calls flowing through chora_tcp_mcp_proxy.py into the
Supabase `prov` schema (deployed by MBSCI-6) using the 5-plane agent seed
(MBSCI-7) as canonical prov:Agent identities.

Design constraints:
- Non-destructive: failures NEVER propagate to the proxy hot path.
- Feature-flagged via CHORA_PROV_ENABLED=1 (defaults to disabled).
- Async / non-blocking: uses asyncpg with a small connection pool.
- Preserves V14.2 Zero-Hallucination Epistemic Parity.
"""
from __future__ import annotations

import os
import sys
import uuid
from typing import Any, Dict, Optional

try:
    import asyncpg  # type: ignore
except ImportError:
    asyncpg = None  # type: ignore

_POOL: Optional[Any] = None
_ENABLED: bool = os.environ.get("CHORA_PROV_ENABLED", "0") == "1"
_DB_URL: Optional[str] = os.environ.get("SUPABASE_DB_URL")

PLATFORM_AGENT_IRI = {
    "github":   "urn:chora:agent:platform:github",
    "supabase": "urn:chora:agent:platform:supabase",
    "linear":   "urn:chora:agent:platform:linear",
    "notion":   "urn:chora:agent:platform:notion",
    "tana":     "urn:chora:agent:platform:tana",
}


def _log(msg: str) -> None:
    print(f"[PROV] {msg}", file=sys.stderr)


async def init_pool() -> None:
    global _POOL
    if not _ENABLED:
        _log("disabled (CHORA_PROV_ENABLED != 1); recorder is a no-op")
        return
    if asyncpg is None:
        _log("asyncpg not installed; recorder disabled")
        return
    if not _DB_URL:
        _log("SUPABASE_DB_URL not set; recorder disabled")
        return
    if _POOL is not None:
        return
    try:
        _POOL = await asyncpg.create_pool(_DB_URL, min_size=1, max_size=4)
        _log("asyncpg pool initialised")
    except Exception as exc:
        _log(f"pool init failed: {exc!r}")
        _POOL = None


async def close_pool() -> None:
    global _POOL
    if _POOL is not None:
        try:
            await _POOL.close()
        except Exception:
            pass
        _POOL = None


def _infer_platform(method: str) -> str:
    if not isinstance(method, str):
        return "supabase"
    lower = method.lower()
    for plane in ("github", "supabase", "linear", "notion", "tana"):
        if plane in lower:
            return plane
    return "supabase"


async def record_activity(method, params, client_id, upstream_id, platform=None):
    if not _ENABLED or _POOL is None:
        return None
    plane = platform or _infer_platform(method)
    agent_iri = PLATFORM_AGENT_IRI.get(plane, PLATFORM_AGENT_IRI["supabase"])
    activity_iri = f"urn:chora:activity:{uuid.uuid4()}"
    try:
        async with _POOL.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO prov.activity (iri, label, activity_type, started_at, platform) VALUES ($1, $2, $3, now(), $4)",
                    activity_iri,
                    f"rpc:{method}[client={client_id[:8]},up={upstream_id}]",
                    method,
                    plane,
                )
                await conn.execute(
                    "INSERT INTO prov.was_attributed_to (entity_id, agent_id) SELECT a.id, g.id FROM prov.activity a, prov.agent g WHERE a.iri = $1 AND g.iri = $2 ON CONFLICT DO NOTHING",
                    activity_iri,
                    agent_iri,
                )
        return activity_iri
    except Exception as exc:
        _log(f"record_activity failed for {method!r}: {exc!r}")
        return None


async def record_generation(activity_iri, entity_iri):
    if not _ENABLED or _POOL is None or not activity_iri or not entity_iri:
        return
    try:
        async with _POOL.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO prov.entity (iri, label) VALUES ($1, $2) ON CONFLICT (iri) DO NOTHING",
                    entity_iri,
                    entity_iri.rsplit(":", 1)[-1],
                )
                await conn.execute(
                    "INSERT INTO prov.was_generated_by (entity_id, activity_id) SELECT e.id, a.id FROM prov.entity e, prov.activity a WHERE e.iri = $1 AND a.iri = $2 ON CONFLICT DO NOTHING",
                    entity_iri,
                    activity_iri,
                )
    except Exception as exc:
        _log(f"record_generation failed ({entity_iri} <- {activity_iri}): {exc!r}")


def extract_entity_iri(response):
    if not isinstance(response, dict):
        return None
    result = response.get("result")
    if isinstance(result, dict):
        for key in ("entity_iri", "iri"):
            val = result.get(key)
            if isinstance(val, str) and val.startswith("urn:"):
                return val
    return None
