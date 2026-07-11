"""CHORA Notion cross-plane cascade repair (MBSCI-9 / D-04b).

Non-destructive, INSERT-only backfill + diagnostic for the Notion Tasks DB
when the write-cascade webhook fails to fire on PR merges into main.

Design contract:
    * Read-side: Linear GraphQL (list MBSCI-* issues) + Supabase prov.entity
      (list merged PRs recorded as prov entities).
    * Write-side: Notion Databases API (POST /pages).
      NEVER PATCH or DELETE. Only additive INSERT of missing rows.
    * Gating: honours 5-plane CHECK constraint
      platform in ('github','supabase','linear','notion','tana').
    * Fail-open: all Notion writes wrapped in try/except; failures logged to
      STDERR only so upstream provenance recording never blocks.

Env:
    CHORA_NOTION_CASCADE_ENABLED=1   feature flag (default 0)
    NOTION_API_TOKEN                 integration token (read from env, never
                                     hard-coded, never logged)
    NOTION_TASKS_DB_ID               target Tasks database id
    LINEAR_API_KEY                   read-only Linear key
    SUPABASE_DB_URL                  optional; for prov.entity cross-check
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set

ALLOWED_PLATFORMS: Set[str] = {"github", "supabase", "linear", "notion", "tana"}


@dataclass(frozen=True)
class MBSCITicket:
    identifier: str            # e.g. "MBSCI-8"
    title: str
    state: str                 # e.g. "OOTKM Ingested"
    linear_url: str
    github_pr_url: Optional[str] = None

    def as_notion_page_properties(self, db_id: str) -> Dict[str, Any]:
        return {
            "parent": {"database_id": db_id},
            "properties": {
                "Name": {
                    "title": [
                        {"text": {"content": f"[{self.identifier}] {self.title}"}}
                    ]
                },
                "Status": {"status": {"name": self.state}},
            },
        }


class NotionCascadeRepair:
    """Idempotent, INSERT-only reconciler between Linear MBSCI and Notion Tasks."""

    def __init__(self, notion_token: str, tasks_db_id: str, *, dry_run: bool = True):
        self._token = notion_token
        self._db_id = tasks_db_id
        self._dry_run = dry_run

    async def diagnose(self, linear_tickets: Iterable[MBSCITicket],
                       existing_notion_names: Iterable[str]) -> List[MBSCITicket]:
        """Return the set-difference: Linear MBSCI rows not present in Notion.

        Pure function: no writes. Matches by identifier prefix in Notion title.
        """
        existing = {n.split("]", 1)[0].lstrip("[").strip()
                    for n in existing_notion_names
                    if n.startswith("[")}
        missing = [t for t in linear_tickets if t.identifier not in existing]
        return missing

    async def backfill(self, missing: List[MBSCITicket]) -> Dict[str, Any]:
        """INSERT-only cascade. Returns per-ticket outcome map."""
        outcomes: Dict[str, Any] = {}
        for ticket in missing:
            if ticket.identifier.split("-", 1)[0].lower() not in ALLOWED_PLATFORMS \
                    and "mbsci" not in ticket.identifier.lower():
                # Sanity: only touch MBSCI-scoped rows.
                outcomes[ticket.identifier] = "skipped:out-of-scope"
                continue
            if self._dry_run:
                outcomes[ticket.identifier] = "dry-run:would-insert"
                continue
            try:
                # Real HTTP POST would go here (httpx/aiohttp). Left as a hook so
                # this scaffold is safe to commit without network dependencies.
                await self._insert_page(ticket)
                outcomes[ticket.identifier] = "inserted"
            except Exception as exc:  # noqa: BLE001 - fail-open by design
                print(f"[chora_notion_cascade] insert failed for "
                      f"{ticket.identifier}: {exc!r}", file=sys.stderr)
                outcomes[ticket.identifier] = f"error:{type(exc).__name__}"
        return outcomes

    async def _insert_page(self, ticket: MBSCITicket) -> None:
        """Placeholder POST hook. Real client wired in follow-up commit."""
        payload = ticket.as_notion_page_properties(self._db_id)
        # Intentional no-op scaffold; MBSCI-9 (2/2) will wire httpx.AsyncClient.
        _ = json.dumps(payload)


async def main() -> int:
    if os.environ.get("CHORA_NOTION_CASCADE_ENABLED", "0") != "1":
        print("[chora_notion_cascade] disabled (set CHORA_NOTION_CASCADE_ENABLED=1)",
              file=sys.stderr)
        return 0
    token = os.environ.get("NOTION_API_TOKEN", "")
    db_id = os.environ.get("NOTION_TASKS_DB_ID", "")
    if not token or not db_id:
        print("[chora_notion_cascade] missing NOTION_API_TOKEN or "
              "NOTION_TASKS_DB_ID", file=sys.stderr)
        return 2
    repair = NotionCascadeRepair(token, db_id, dry_run=True)
    # Deterministic seed set for the known MBSCI-6/7/8 gap; the follow-up
    # commit will replace this with a live Linear query.
    known_gap = [
        MBSCITicket("MBSCI-6",
                    "D-04 Remediation \u2014 PROV-O chain of custody (5-plane)",
                    "OOTKM Ingested",
                    "https://linear.app/chora-labs/issue/MBSCI-6",
                    "https://github.com/BearFoxPrime/CHORA-O-/pull/2"),
        MBSCITicket("MBSCI-7",
                    "D-04 Remediation \u2014 Seed 5-Plane Agents (prov.agent)",
                    "OOTKM Ingested",
                    "https://linear.app/chora-labs/issue/MBSCI-7",
                    "https://github.com/BearFoxPrime/CHORA-O-/pull/3"),
        MBSCITicket("MBSCI-8",
                    "D-04 Remediation \u2014 Proxy instrumentation "
                    "(prov.activity + prov.was_generated_by)",
                    "OOTKM Ingested",
                    "https://linear.app/chora-labs/issue/MBSCI-8",
                    "https://github.com/BearFoxPrime/CHORA-O-/pull/4"),
    ]
    missing = await repair.diagnose(known_gap, existing_notion_names=[])
    outcomes = await repair.backfill(missing)
    print(json.dumps({"missing": [t.identifier for t in missing],
                      "outcomes": outcomes}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
