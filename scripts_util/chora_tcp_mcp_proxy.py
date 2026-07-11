import asyncio
import json
import sys
import uuid
from typing import Dict, Tuple, Any

HOST = '127.0.0.1'
PORT = 8111
TARGET_MCP_COMMAND = [sys.executable, "scripts_util/tana_mcp_server.py"]

class HardenedMCPMultiplexer:
    def __init__(self):
        self.mcp_process: asyncio.subprocess.Process = None
        self.active_clients: Dict[str, asyncio.Queue] = {}
        self.translation_table: Dict[int, Tuple[str, Any]] = {}
        self.upstream_id_counter = 1

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
                    writer.write((json.dumps(response) + '\n').encode('utf-8'))
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

                    payload = (json.dumps(request) + '\n').encode('utf-8')
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
    server = await asyncio.start_server(mux.handle_client, HOST, PORT)
    print(f"[*] CHORA Hardened TCP Proxy listening securely on {HOST}:{PORT}")
    print(f"[*] Bidirectional ID Mapping and Disconnect Tombstoning ENABLED.")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
