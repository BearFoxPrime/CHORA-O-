## 2026-07-22 - FastMCP IPC Payload Serialization Optimization
**Learning:** By default, `json.dumps()` in Python includes spaces after commas and colons. When using `indent=2`, it introduces significant whitespace for nested structures. For inter-process communication (IPC) in FastMCP, this formatting bloats the payload size, slowing down transmission and adding parsing overhead.
**Action:** Always prefer compact JSON serialization (`separators=(',', ':')`) for IPC payloads over the wire to minimize size and maximize speed.
