from typing import Optional, Dict, Any, Callable, List, cast

from langchain_mcp_adapters.client import MultiServerMCPClient

MCP_SERVERS = {
    "deepwiki": {
        "url": "https://mcp.deepwiki.com/mcp",
        "transport": "streamable_http",
    }
}

async def get_mcp_client(
        server_configs: Optional[Dict[str, Any]] = None,
) -> Optional[MultiServerMCPClient]:
    global _mcp_client

    if server_configs is not None:
        try:
            client = MultiServerMCPClient(server_configs)
            return client
        except Exception as e:
            print(f"Failed to create MCP client: {e}")

    if _mcp_client is None:
        try:
            _mcp_client = MultiServerMCPClient(MCP_SERVERS)
        except Exception as e:
            print(f"Failed to create MCP client: {e}")

    return _mcp_client

async def get_mcp_tools(server_name: str) -> List[Callable[..., Any]]:
    global _mcp_tools_cache

    if server_name in _mcp_tools_cache:
        return _mcp_tools_cache[server_name]

    if server_name not in MCP_SERVERS:
        _mcp_tools_cache[server_name] = []
        return []

    try:
        server_config = {server_name: MCP_SERVERS[server_name]}
        client = await get_mcp_client(server_config)
        if client is None:
            _mcp_tools_cache[server_name] = []
            return []

        all_tools = await client.get_tools()
        tools = cast(List[Callable[..., Any]], all_tools)
        _mcp_tools_cache[server_name] = tools
        return tools
    except Exception as e:
        _mcp_tools_cache[server_name] = []
        return []

async def get_deepwiki_tools() -> List[Callable[..., Any]]:
    return await get_mcp_tools("deepwiki")

