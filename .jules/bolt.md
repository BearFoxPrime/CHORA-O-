## 2025-02-23 - FastMCP Inter-process Communication Serialization
**Learning:** For FastMCP inter-process communication (IPC) payloads over UNIX Domain Sockets/TCP, using compact JSON serialization (i.e. `separators=(',', ':')` instead of `indent=2`) significantly reduces transmission payload size and slightly improves parsing speed on the receiving end.
**Action:** Use compact JSON representation `json.dumps(..., separators=(',', ':'))` rather than `indent=2` for all machine-to-machine JSON serialization in backend proxy services.
