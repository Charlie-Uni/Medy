"""In-process MCP protocol client for unit and database integration tests."""

import anyio
from mcp.client.session import ClientSession
from mcp.shared.memory import create_client_server_memory_streams


def call(server, tool: str, arguments: dict):
    async def main():
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            low = server._lowlevel_server
            async with anyio.create_task_group() as tg:
                tg.start_soon(low.run, server_streams[0], server_streams[1], low.create_initialization_options())
                async with ClientSession(*client_streams) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    result = await session.call_tool(tool, arguments)
                tg.cancel_scope.cancel()
            return tools, result

    return anyio.run(main)
