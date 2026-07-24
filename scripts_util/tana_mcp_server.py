import os
import sys
import json
import asyncio
import uuid
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, model_validator, ValidationError

mcp = FastMCP("TANA_ERA_Knowledge_Graph")
dsn = os.getenv("TRI_TRACK_PG_DSN", "postgresql://postgres:postgres@192.168.1.51:5432/postgres")
_pool = None

async def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(conninfo=dsn, min_size=5, max_size=20, open=False, kwargs={"autocommit": False, "row_factory": dict_row})
        await _pool.open(wait=True)
    return _pool

class BBoxRequest(BaseModel):
    min_lon: float = Field(..., ge=-180, le=180)
    min_lat: float = Field(..., ge=-90,  le=90)
    max_lon: float = Field(..., ge=-180, le=180)
    max_lat: float = Field(..., ge=-90,  le=90)
    crs: str = Field("OGC:CRS84")
    expected_row_count: int = Field(...)

    @model_validator(mode="after")
    def _check_bounds(self):
        if self.crs.upper() in {"EPSG:4326", "EPSG/0/4326"}: raise ValueError("Use OGC:CRS84 explicitly")
        if self.min_lat >= self.max_lat or self.min_lon >= self.max_lon: raise ValueError("Degenerate bounds")
        if (self.max_lon - self.min_lon) > 350: raise ValueError("Global span rejected")
        return self

async def execute_with_epistemic_gate(query: str, params: list, expected_row_count: int, base_table: str, include_simulations: bool = False) -> str:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("EXPLAIN (FORMAT JSON) " + query, params)
            explain_result = await cur.fetchone()
            plan_rows = explain_result['QUERY PLAN'][0]['Plan'].get('Plan Rows', 0)
            
            if plan_rows > 130000: raise Exception(f"Cost Gate Rejected: {plan_rows} exceeds 130K budget.")
            if plan_rows > (expected_row_count * 5): raise Exception("Rationale Audit Rejected: Safe-Cover Hacking detected.")
            
            await cur.execute(query, params)
            results = await cur.fetchall()
            
            epistemic_badge = {
                "$schema": "[https://chora.local/schema/epistemic_badge.v1.json](https://chora.local/schema/epistemic_badge.v1.json)",
                "tier": 0 if not include_simulations else 3,
                "fidelity": "full" if not include_simulations else "ground_truth_only",
                "uncertainty_surfaced": include_simulations,
                "prov_activity_uri": f"chora:activity:{uuid.uuid4()}"
            }
            return json.dumps({"epistemic_badge": epistemic_badge, "data": results}, separators=(',', ':'), default=str)

@mcp.tool()
async def fetch_geodetic_markers(min_lon: float, min_lat: float, max_lon: float, max_lat: float, expected_row_count: int, crs: str = "OGC:CRS84", surveyor_name: str = None) -> str:
    """[SPATIAL SCHEMA] Fetches historical geodetic markers. Requires BBox."""
    try:
        BBoxRequest(min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat, crs=crs, expected_row_count=expected_row_count)
        query = "SELECT id, mark_label, surveyor, ST_AsText(geom) as coords FROM spatial.geodetic_marks WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)"
        params = [min_lon, min_lat, max_lon, max_lat]
        if surveyor_name:
            query += " AND surveyor ILIKE %s"
            params.append(f"%{surveyor_name}%")
        return await execute_with_epistemic_gate(query, params, expected_row_count, "spatial.geodetic_marks")
    except Exception as e: return f"Error: {str(e)}"

if __name__ == "__main__":
    if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    mcp.run()
