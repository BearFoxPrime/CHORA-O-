## 2024-05-18 - [FastMCP IPC Payload Optimization]
**Learning:** For FastMCP inter-process communication (IPC) payloads, pretty-printed JSON (like `indent=2`) adds unnecessary transmission size overhead and parsing time, which slows down the Quad-Platform Agentic OS pipeline.
**Action:** Always prefer compact JSON serialization (`separators=(',', ':')` instead of `indent=2`) when passing data across IPC boundaries to minimize transmission size and maximize parsing speed.
