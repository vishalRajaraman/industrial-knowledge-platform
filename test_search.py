import asyncio, sys; sys.path.append('orchestrator'); from mcp_client import MCPClientManager
async def main():
    mgr = MCPClientManager()
    await mgr.connect_all()
    res = await mgr.call_tool('copilot', 'hybrid_search', {'query': 'test', 'entities': ['pump'], 'top_k': 5})
    print(res)
    await mgr.disconnect_all()
asyncio.run(main())
