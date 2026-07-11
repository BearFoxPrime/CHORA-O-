# CHORA LABS: Quad-Platform Agentic OS

**Status:** ACTIVE DEPLOYMENT (Horizon 3)
**Governance:** V14.2 "Zero-Hallucination Epistemic Parity"

## 🌐 Quad-Platform Topology

This repository serves as the execution layer for the CHORA Agentic Workflow, unifying four discrete platforms into a single Sovereign Substrate:

1. **Linear (`MBSCI`)**: Autonomous Task Dispatch & Webhook Generation
2. **Notion**: Executive Dashboard & Knowledge Base Syncer
3. **Tana**: Graph/OOTKM Formatting & Wetware Gateway
4. **Supabase (Tri-Track PostGIS)**: Bare-metal PostgreSQL 17 deterministic storage

## 🏗️ Architecture Matrix

- **`scripts_util/chora_tcp_mcp_proxy.py`**: Hardened asynchronous UNIX Domain Socket (UDS)/TCP multiplexer. Provides bidirectional ID mapping, strict socket tombstoning, and protects the DB from unconstrained agent concurrency.
- **`scripts_util/tana_mcp_server.py`**: The FastMCP target server. Enforces the "Constitutional BBox" contract (Pydantic CRS84 validation, PostgreSQL EXPLAIN cost-gating) and outputs strict W3C PROV-O JSON `EpistemicBadges`.

*Engineered for zero-trust spatial reasoning.*
