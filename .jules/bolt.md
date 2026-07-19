## 2024-07-19 - PostgreSQL JSON Aggregation for Large Datasets
**Learning:** Python's memory spikes dramatically and the event loop can block when `json.dumps()` is called on large result sets fetched via `fetchall()`, especially with spatial queries up to 130K rows in the FastMCP tool.
**Action:** Use PostgreSQL's `json_agg()` wrapped in a subquery to offload serialization to the database engine. This prevents fetching raw rows into Python memory, bypassing CPU bottlenecks and maintaining responsiveness of the async thread.
