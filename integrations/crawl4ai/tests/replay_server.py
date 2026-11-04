"""Offline upstream fixture for an actual stdio MCP server/client smoke test."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).parents[1]))
import server
from mcp import types

saved=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
os.environ['CRAWL4AI_KEY']='sk_live_offline_fixture'

@asynccontextmanager
async def transport(*args,**kwargs):
    yield None,None,None

class Remote:
    def __init__(self,*args,**kwargs): pass
    async def __aenter__(self): return self
    async def __aexit__(self,*args): pass
    async def initialize(self): return SimpleNamespace(instructions='Offline fixture')
    async def list_tools(self,**kwargs):
        return types.ListToolsResult(tools=[types.Tool(name='scrape',description='Fixture scraper',inputSchema={
            'type':'object','properties':{'url':{'type':'string'},'format':{'type':'string'}},'required':['url']})])
    async def call_tool(self,name,arguments):
        assert name=='scrape' and arguments['url']==saved['url']
        assert arguments['format']=='both', 'HTML must be requested in the same cloud call'
        return types.CallToolResult(content=[types.TextContent(type='text',text=json.dumps(saved['body']))])

server.streamablehttp_client=transport
server.ClientSession=Remote
asyncio.run(server.serve())
