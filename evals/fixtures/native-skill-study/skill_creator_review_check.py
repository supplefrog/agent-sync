"""Verify the bundled grading tools using a missing deliverable and its correction."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

repo = Path.cwd()
fixture = repo / 'evals/fixtures/native-skill-study'
fresh = Path(sys.argv[1]).resolve()
fresh.mkdir()
skill = repo / 'skills/skill-authoring'
case = json.loads((fixture/'cases.json').read_bytes())['cases'][0]
for iteration in (1, 2):
    workspace = fresh / f'iteration-{iteration}'
    for label, ref in (('without_skill', 'A'), ('with_skill', 'B')):
        trial = workspace / 'eval-0' / label / 'run-1'
        restored = not (iteration == 1 and label == 'with_skill')
        shutil.copytree(fixture/'fixtures/create-handoff', trial/'fixture')
        shutil.copytree(fixture/f'blind-quality/create-handoff/{ref}/deliverables', trial/'fixture/deliverables')
        if not restored:
            (trial/'fixture/deliverables/sample-handoff.md').unlink()
        shutil.copytree(trial/'fixture/deliverables', trial/'outputs')
        result = subprocess.run([sys.executable, str(fixture/'oracle.py'), str(trial/'fixture'), case['id']],
                                text=True, capture_output=True)
        actual = json.loads(result.stdout)
        assert (result.returncode == 0) is restored
        expectations = [
            {'text':'Reusable skill package is present', 'passed':True, 'evidence':'Inspected outputs/trial-handoff/SKILL.md'},
            {'text':'Sample handoff is present and passes the oracle', 'passed':restored,
             'evidence': 'Independent oracle accepted unchanged-input file set' if restored else actual['failures'][0]},
        ]
        grade = {'expectations': expectations, 'summary':{'passed':sum(e['passed'] for e in expectations),
                 'failed': 0 if restored else 1, 'total':2, 'pass_rate':1 if restored else 0.5},
                 'timing':{'total_duration_seconds':2}, 'execution_metrics':{'output_chars':9999}}
        (trial/'grading.json').write_text(json.dumps(grade))
        (trial/'eval_metadata.json').write_text(json.dumps({'eval_id':0,'prompt': case['prompt']}))
        (trial/'timing.json').write_text(json.dumps({'total_tokens':123,'total_duration_seconds':1}))
    subprocess.run([sys.executable,'-B','-m','scripts.aggregate_benchmark',str(workspace),'--skill-name','offline-review-control'],
                   cwd=skill, check=True)
    benchmark = workspace/'benchmark.json'
    summary = json.loads(benchmark.read_bytes())['run_summary']
    assert summary['with_skill']['pass_rate']['mean'] == (0.5 if iteration == 1 else 1)
    assert summary['without_skill']['pass_rate']['mean'] == 1
    assert summary['with_skill']['tokens']['mean'] == 123
    viewer = [sys.executable,'-B',str(skill/'scripts/generate_review.py'),str(workspace),
              '--skill-name','<offline-review-control>','--benchmark',str(benchmark),'--static',str(workspace/'review.html')]
    if iteration == 2:
        viewer.extend(['--previous-workspace',str(fresh/'iteration-1')])
    subprocess.run(viewer,check=True)
    rendered = (workspace/'review.html').read_text(encoding='utf-8')
    assert all(name in rendered for name in ('trial-handoff/SKILL.md','sample-handoff.md',case['prompt']))
    embedded = rendered.split('const EMBEDDED_DATA = ', 1)[1].split(';\n', 1)[0]
    assert '<' not in embedded and json.loads(embedded)['skill_name'] == '<offline-review-control>'
    print(f'Iteration {iteration} grade, timing and nested review artifacts verified')
