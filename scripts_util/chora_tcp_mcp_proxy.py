import asyncio
import json
import sys
import uuid
from typing import Dict, Tuple, Any

# MBSCI-8: PROV-O instrumentation (additive; feature-flagged via CHORA_PROV_ENABLED=1)
try:
    from scripts_util import chora_prov_recorder as _prov  # type: ignore
except Exception:
    try:
        import chora_prov_recorder as _prov  # type: ignore
    except Exception:
        _prov = None  # type: ignore

HOST = '127.0.0.1'
PORT = 8111
TARGET_MCP_COMMAND = [sys.executable, "scripts_util/tana_mcp_server.py"]

class HardenedMCPMultiplexer:
    def __init__(self):
        self.mcp_process: asyncio.subprocess.Process = None
        self.active_clients: Dict[str, asyncio.Queue] = {}
        self.translation_table: Dict[int, Tuple[str, Any]] = {}
        self.upstream_id_counter = 1
        # MBSCI-8: map upstream_id -> activity_iri so responses can attach was_generated_by
        self.activity_by_upstream: Dict[int, str] = {}

    async def start_mcp_server(self):
        print(f"[*] Starting hardened target MCP server: {' '.join(TARGET_MCP_COMMAND)}")
        self.mcp_process = await asyncio.create_subprocess_exec(
            *TARGET_MCP_COMMAND,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        asyncio.create_task(self._read_mcp_stdout())
        asyncio.create_task(self._read_mcp_stderr())

    async def _read_mcp_stdout(self):
        while True:
            line = await self.mcp_process.stdout.readline()
            if not line: break
            try:
                payload_str = line.decode('utf-8').strip()
                if not payload_str: continue
                response = json.loads(payload_str)

                if 'id' in response and response['id'] is not None:
                    upstream_id = response['id']
                    # MBSCI-8: attach prov.was_generated_by if the response advertises an entity IRI
                    if _prov is not None:
                        try:
                            activity_iri = self.activity_by_upstream.pop(upstream_id, None)
                            if activity_iri:
                                entity_iri = _prov.extract_entity_iri(response)
                                if entity_iri:
                                    asyncio.create_task(_prov.record_generation(activity_iri, entity_iri))
                        except Exception:
                            pass
                    if upstream_id in self.translation_table:
                        client_id, original_rpc_id = self.translation_table.pop(upstream_id)
                        if client_id in self.active_clients:
                            response['id'] = original_rpc_id
                            await self.active_clients[client_id].put(response)
                        else:
                            print(f"[!] SECURITY GUARD: Dropped orphaned response for tombstoned client {client_id}")
                else:
                    for queue in self.active_clients.values():
                        await queue.put(response)
            except json.JSONDecodeError:
                pass

    async def _read_mcp_stderr(self):
        while True:
            line = await self.mcp_process.stderr.readline()
            if not line: break
            print(f"[MCP STDERR] {line.decode('utf-8').strip()}", file=sys.stderr)

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        client_id = str(uuid.uuid4())
        client_queue = asyncio.Queue()
        self.active_clients[client_id] = client_queue
        print(f"[+] Agent connected: {client_id}")

        async def send_to_client():
            while True:
                try:
                    response = await client_queue.get()
                    # ⚡ Bolt: Use compact JSON serialization for FastMCP IPC performance optimization
                    writer.write((json.dumps(response, separators=(',', ':')) + '\n').encode('utf-8'))
                    await writer.drain()
                except Exception:
                    break

        sender_task = asyncio.create_task(send_to_client())

        try:
            while True:
                data = await reader.readline()
                if not data: break
                try:
                    request = json.loads(data.decode('utf-8').strip())
                    if 'id' in request:
                        original_id = request['id']
                        current_upstream_id = self.upstream_id_counter
                        self.upstream_id_counter += 1
                        self.translation_table[current_upstream_id] = (client_id, original_id)
                        request['id'] = current_upstream_id

                        # MBSCI-8: record prov.activity + was_attributed_to (fire-and-forget)
                        if _prov is not None:
                            try:
                                method = request.get('method', 'unknown')
                                params = request.get('params')
                                async def _record_and_stash(m, p, cid, uid):
                                    activity_iri = await _prov.record_activity(m, p, cid, uid)
                                    if activity_iri:
                                        self.activity_by_upstream[uid] = activity_iri
                                asyncio.create_task(_record_and_stash(method, params, client_id, current_upstream_id))
                            except Exception:
                                pass

                        # ⚡ Bolt: Use compact JSON serialization for FastMCP IPC performance optimization
                        payload = (json.dumps(request, separators=(',', ':')) + '\n').encode('utf-8')
                        self.mcp_process.stdin.write(payload)
                        await self.mcp_process.stdin.drain()
                except json.JSONDecodeError:
                    pass
        finally:
            print(f"[-] Agent disconnected: {client_id}. Tombstoning active requests.")
            sender_task.cancel()
            if client_id in self.active_clients:
                del self.active_clients[client_id]
            writer.close()
            await writer.wait_closed()

async def main():
    mux = HardenedMCPMultiplexer()
    await mux.start_mcp_server()
    # MBSCI-8: initialise the prov recorder pool (no-op if CHORA_PROV_ENABLED != 1)
    if _prov is not None:
        try:
            await _prov.init_pool()
        except Exception:
            pass
    server = await asyncio.start_server(mux.handle_client, HOST, PORT)
    print(f"[*] CHORA Hardened TCP Proxy listening securely on {HOST}:{PORT}")
    print(f"[*] Bidirectional ID Mapping and Disconnect Tombstoning ENABLED.")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
