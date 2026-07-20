## 2024-07-20 - [Compact JSON Serialization for Inter-Process Communication]
**Learning:** Using `indent=2` in `json.dumps()` for payloads sent over machine-to-machine communication channels (like MCP proxies) dramatically inflates payload size and slows down serialization parsing with no benefit to readability, since a human isn't reading the raw IPC stream.
**Action:** When serializing JSON for inter-process communication, prefer compact encoding `separators=(',', ':')` to minimize transmission size and maximize serialization speed.
