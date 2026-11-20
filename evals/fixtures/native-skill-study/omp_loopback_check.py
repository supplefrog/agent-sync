"""Exercise a prepared handoff study using deterministic loopback replies and stock OMP.

Run from the Agent Sync checkout with a freshly prepared study path. The
replies replay a checked reference artifact and return no model-quality score.
"""
import json
import sys
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
import tempfile

root = Path.cwd()
sys.path.insert(0, str(root/'tools'))
from evaluation_runtime import runtime_environment
import evaluation_artifact_pilot as pilot
import evaluation_omp_artifact as omp
study = Path(sys.argv[1])
plan = json.loads((study/'results/plan.json').read_bytes())
reference = root/'evals/fixtures/native-skill-study/blind-quality/create-handoff/A'
route = {"provider":"localtest","model":"fixture-test","reasoning":"medium"}

def trial(executable, item, spec):
    fixture = Path(item['fixture'])
    tool_calls = [('read', {'path': 'context/team-notes.md'})]
    if item['catalog']:
        target = Path(item['catalog'][0])
        line_count = len(target.read_text().rstrip('\n').split('\n'))
        if line_count <= 80:
            tool_calls.append(('read', {'path': f'skill://{target.parent.name}'}))
        else:
            for start in range(1, line_count + 1, 80):
                selector = f':raw:{start}-{min(line_count, start + 79)}'
                tool_calls.append(('read', {'path': str(target.relative_to(fixture)) + selector}))
    for file in sorted((reference/'deliverables').rglob('*.md')):
        tool_calls.append(('write', {'path': str(file.relative_to(reference)), 'content': file.read_text()}))

    class MockProvider(BaseHTTPRequestHandler):
        counter = 0
        def log_message(self, *args):
            pass
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert self.path == '/v1/chat/completions'
            assert request['model'] == route['model']
            tools = {tool['function']['name'] for tool in request.get('tools', [])}
            if tools:
                assert tools == omp.TOOLS
                idx = self.__class__.counter
                self.__class__.counter += 1
            else:
                idx = len(tool_calls)
            if idx < len(tool_calls):
                name, args = tool_calls[idx]
                delta = {'tool_calls': [{'index': 0, 'id': f'call_{idx}', 'type': 'function',
                                         'function': {'name': name, 'arguments': json.dumps(args)}}]}
                stop = 'tool_calls'
            else:
                delta = {'content': 'Saved the skill draft and example.'}
                stop = 'stop'
            def chunk(delta, stop=None):
                return {'id': 'fixed-reply', 'object': 'chat.completion.chunk', 'created': 1,
                        'model': route['model'], 'choices': [{'index': 0, 'delta': delta, 'finish_reason': stop}]}
            packets = [chunk({'role': 'assistant', **delta}), chunk({}, stop)]
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.end_headers()
            for packet in packets:
                self.wfile.write(f'data: {json.dumps(packet)}\n\n'.encode())
            self.wfile.write(b'data: [DONE]\n\n')

    with ThreadingHTTPServer(('127.0.0.1', 0), MockProvider) as server, tempfile.TemporaryDirectory() as directory:
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            env = runtime_environment(dict(os.environ), Path(directory))
            settings = Path(directory)/'omp'
            settings.mkdir()
            env.update(PI_CODING_AGENT_DIR=str(settings), NO_PROXY='127.0.0.1,localhost')
            (settings/'models.yml').write_text(f"""providers:
  localtest:
    baseUrl: http://127.0.0.1:{server.server_port}/v1
    apiKey: dummy-local
    api: openai-completions
    models:
      - id: fixture-test
        name: Fixture Test
        reasoning: true
        contextWindow: 128000
        maxTokens: 4000
""")
            output = omp.run_rpc(executable, item['prompt'], fixture, env, route, 35, item['catalog'])
            output['source'] = 'deterministic-loopback-no-model'
            return output
        finally:
            server.shutdown()
            thread.join()

out = study/'results'
with patch.object(omp, 'run_trial', trial):
    report = pilot.run(plan, out)
print(json.dumps({k: report[k] for k in ('completed_trials', 'expected_trials', 'comparison_ready')}, indent=2))
for row in report['results']:
    print(row['arm'], row.get('blocker'), row.get('oracle'), row.get('native', {}).get('tool_events'))
if not report['comparison_ready'] or not all(row['artifact_passed'] for row in report['results']):
    raise SystemExit('Offline OMP control failed')
