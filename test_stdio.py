import asyncio
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))


async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(HERE, "server.py")],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("TOOLS:", [t.name for t in tools.tools])
            res = await session.call_tool("ping", {})
            print("PING:", json.dumps(json.loads(res.content[0].text), ensure_ascii=False))
            res = await session.call_tool("create_primitive", {"primitive_type": "uv_sphere", "name": "StdioSphere", "location": [3, 1, 0], "size": 1.5})
            print("CREATE RAW:", [c.text for c in res.content], "isError:", res.isError)
            res = await session.call_tool("delete_object", {"object_name": "StdioSphere"})
            print("DELETE:", res.content[0].text)


asyncio.run(main())
print("STDIO TEST PASSED")
