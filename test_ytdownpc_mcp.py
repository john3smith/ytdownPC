"""Smoke tests that do not access media sites or start downloads."""

import asyncio
import sys
import unittest
from unittest.mock import patch

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import ytdownpc_mcp


class BridgeTests(unittest.TestCase):
    def test_rejects_unapproved_host(self):
        with self.assertRaises(ValueError):
            ytdownpc_mcp.start_download("https://example.com/video")

    def test_rejects_unknown_quality(self):
        with self.assertRaises(ValueError):
            ytdownpc_mcp.start_download("https://youtu.be/abcdefghijk", "ultra")

    def test_probe_uses_existing_ytdownpc_function(self):
        with patch.object(ytdownpc_mcp, "probe_video", return_value={"id": "abcdefghijk"}) as probe:
            self.assertEqual(ytdownpc_mcp.video_info("https://youtu.be/abcdefghijk"), {"id": "abcdefghijk"})
            probe.assert_called_once()

    def test_stdio_exposes_tools(self):
        async def check():
            params = StdioServerParameters(
                command=sys.executable,
                args=[ytdownpc_mcp.__file__],
            )
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    names = {tool.name for tool in tools.tools}
                    self.assertEqual(names, {"video_info", "start_download", "download_status"})

        asyncio.run(check())


if __name__ == "__main__":
    unittest.main()
