import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1]))
from mcp import types
from server import ScrapeAdapter, normalize_result
import server


class Remote:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return self.result


def payload(value, **kwargs):
    return types.CallToolResult(content=[types.TextContent(type='text', text=json.dumps(value))], **kwargs)


def test_scrape_requests_html_in_same_call_and_preserves_caller_arguments():
    raw={'ok':True,'markdown':'Original','html':'<html>ordinary</html>'}
    remote=Remote(payload(raw))
    args={'url':'https://example.org/','format':'md'}
    result=asyncio.run(ScrapeAdapter(remote).call('scrape',args))
    assert args == {'url':'https://example.org/','format':'md'}
    assert remote.calls == [('scrape',{'url':'https://example.org/','format':'both'})]
    data=json.loads(result.content[0].text)
    assert data['markdown']=='Original'
    assert 'html' not in data


def test_explicit_both_keeps_html_and_non_scrape_calls_are_unchanged():
    raw={'ok':True,'markdown':'Original','html':'<html>ordinary</html>'}
    remote=Remote(payload(raw))
    result=asyncio.run(ScrapeAdapter(remote).call('scrape',{'url':'https://example.org/','format':'both'}))
    assert json.loads(result.content[0].text)['html']==raw['html']
    other=asyncio.run(ScrapeAdapter(remote).call('search',{'q':'hello'}))
    assert other is remote.result
    assert remote.calls[-1]==('search',{'q':'hello'})


def test_error_and_non_json_results_are_not_reclassified():
    result=payload({'ok':False},isError=True)
    assert normalize_result('https://reddit.com/r/test',result,'md') is result
    plain=types.CallToolResult(content=[types.TextContent(type='text',text='Blocked')])
    assert normalize_result('https://reddit.com/r/test',plain,'md') is plain


def test_structured_only_response_is_normalized_and_metadata_preserved():
    raw = {'ok': True, 'markdown': '', 'html': '<shreddit-comment thingid="t1_abc" author="person"><p slot="comment">Recovered body</p></shreddit-comment>'}
    result = types.CallToolResult(content=[], structuredContent=raw, _meta={'trace': 'test'})
    normalized = normalize_result('https://www.reddit.com/r/test/comments/abc/title/', result, 'md')
    assert normalized.structuredContent['html_recovery']['comments'][0]['body'] == 'Recovered body'
    assert 'html' not in normalized.structuredContent
    assert normalized.meta == result.meta


def test_oversize_forced_html_is_not_returned_to_markdown_callers(monkeypatch):
    monkeypatch.setattr(server, 'MAX_RESULT_CHARS', 100)
    raw = {'ok': True, 'markdown': 'Small', 'html': 'x' * 101}
    for result in (payload(raw), types.CallToolResult(content=[], structuredContent=raw)):
        normalized = normalize_result('https://example.com/', result, 'md')
        assert normalized.isError
        assert normalized.structuredContent is None
        assert 'x' * 101 not in normalized.content[0].text
