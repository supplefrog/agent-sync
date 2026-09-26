import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from evaluation_runtime import skill_study_events, runtime_environment
from evaluation_artifact_pilot import prepare, validate_jobs, tree
import evaluation_artifact_pilot as pilot
from artifact_hash import freeze_candidate
from evaluation_hermes_worker import study_guard


def test_runtime_removes_secret_and_personal_state(tmp_path):
    env = runtime_environment({'PATH': 'safe', 'OPENAI_API_KEY': 'secret', 'CODEX_HOME': 'personal'}, tmp_path)
    assert 'OPENAI_API_KEY' not in env
    assert env['CODEX_HOME'] == str(tmp_path / 'codex')


def events(command, exit_code=0):
    return '\n'.join(json.dumps(row) for row in [
        {'type': 'thread.started', 'thread_id': 'abc'},
        {'type': 'turn.started'},
        {'type': 'item.completed', 'item': {'id': '1', 'type': 'command_execution', 'command': command, 'exit_code': exit_code}},
        {'type': 'item.completed', 'item': {'id': '2', 'type': 'agent_message', 'text': 'I used the skill'}},
        {'type': 'turn.completed', 'usage': {'input_tokens': 12, 'cached_input_tokens': 3, 'output_tokens': 5}}])


def test_load_evidence_requires_exact_successful_native_read():
    target = '/fixture/.agents/skills/leaf/SKILL.md'
    read = skill_study_events(events('cat "' + target + '"'), [target])
    assert read['loaded_skills'][0]['item_id'] == '1'
    for command, code in [('echo "' + target + '"', 0), ('cat "' + target + '.old"', 0), ('cat "' + target + '"', 1),
                          ('echo cat "' + target + '"', 0), ('cat "' + target + '"; exit 0', 0),
                          ('Get-Content "' + target + '" -TotalCount 0', 0)]:
        assert not skill_study_events(events(command, code), [target])['loaded_skills']
    assert read['tokens'] == {'input': 12, 'cached_input': 3, 'output': 5, 'source': 'native-turn-completed-usage'}
    assert read['dollars'] is None
    assert skill_study_events(events('Get-Content -LiteralPath "' + target + '" -Raw'), [target])['loaded_skills']
    no_usage = events('pwd').replace('"input_tokens": 12', '"input_tokens": null')
    assert skill_study_events(no_usage, [])['tokens']['input'] is None


def native_spec(tmp_path):
    fixture = tmp_path / 'source'
    fixture.mkdir()
    (fixture / 'data.txt').write_text('data')
    skill = tmp_path / 'leaf'
    skill.mkdir()
    (skill / 'SKILL.md').write_text('---\nname: leaf\ndescription: Use for a leaf task\n---\nSecret design hints')
    (skill / 'helper.py').write_text('print(1)')
    oracle = tmp_path / 'oracle.py'
    oracle.write_text('pass')
    spec = {'purpose': 'native-skill-study', 'agent': 'codex', 'provider': 'openai-codex', 'model': 'gpt-6-sol', 'reasoning': 'medium',
            'arms': [{'id': 'baseline', 'instructions': None}, {'id': 'candidate', 'instructions': str(skill / 'SKILL.md')}],
            'cases': [{'id': 'real', 'prompt': 'Fix the artifact', 'fixture': str(fixture)}], 'workspace_root': str(tmp_path / 'jobs'),
            'oracle': str(oracle), 'max_workers': 1, 'max_iterations': 10, 'timeout': 60, 'quota_remaining': 90}
    return spec


def test_native_prepare_stages_package_without_prompt_injection(tmp_path):
    spec = native_spec(tmp_path)
    plan = prepare(spec, tmp_path / 'out')
    validate_jobs(plan)
    assert plan['resource_limits'] == {'timeout_seconds': 60, 'max_iterations': None, 'iteration_limit_enforced': False}
    assert {j['prompt'] for j in plan['jobs']} == {'Fix the artifact'}
    assert all(j['instructions'] is None for j in plan['jobs'])
    candidate = next(j for j in plan['jobs'] if j['arm'] == 'candidate')
    staged = Path(candidate['catalog'][0])
    assert staged.with_name('helper.py').read_text() == 'print(1)'
    staged.write_text('changed')
    with pytest.raises(ValueError, match='frozen package'):
        validate_jobs(plan)


def test_native_prepare_rejects_fixture_edit_between_arms(tmp_path):
    spec = native_spec(tmp_path)
    source = Path(spec['cases'][0]['fixture'])
    copytree = pilot.shutil.copytree
    copies = []
    def copy_then_edit(origin, destination):
        result = copytree(origin, destination)
        copies.append(destination)
        if len(copies) == 1:
            (source / 'data.txt').write_text('changed between arms')
        return result
    with patch.object(pilot.shutil, 'copytree', side_effect=copy_then_edit):
        with pytest.raises(ValueError, match='shared frozen source'):
            prepare(spec, tmp_path / 'out')
    assert len(copies) == 2
    assert not (tmp_path / 'out/plan.json').exists()


@pytest.mark.parametrize('changed_package', ['common', 'target'])
def test_native_prepare_reuses_frozen_catalog_before_each_arm(tmp_path, changed_package):
    spec = native_spec(tmp_path)
    common = tmp_path / 'common'
    common.mkdir()
    (common / 'SKILL.md').write_text('---\nname: common\ndescription: A common tool\n---\nOriginal')
    spec['catalog'] = [str(common / 'SKILL.md')]
    target = Path(spec['arms'][1]['instructions'])
    copytree = pilot.shutil.copytree
    copies = []
    def copy_then_edit(origin, destination):
        result = copytree(origin, destination)
        copies.append(destination)
        if len(copies) == 2:
            changed = common / 'SKILL.md' if changed_package == 'common' else target
            changed.write_text('changed between arms')
        return result
    with patch.object(pilot.shutil, 'copytree', side_effect=copy_then_edit):
        with pytest.raises(ValueError, match='Catalog source changed before staging'):
            prepare(spec, tmp_path / 'out')
    assert not (tmp_path / 'out/plan.json').exists()


@pytest.mark.parametrize('changed_input', ['fixture', 'catalog'])
def test_native_validation_rejects_arm_specific_refreezing(tmp_path, changed_input):
    spec = native_spec(tmp_path)
    common = tmp_path / 'common'
    common.mkdir()
    (common / 'SKILL.md').write_text('---\nname: common\ndescription: A common tool\n---\nOriginal')
    spec['catalog'] = [str(common / 'SKILL.md')]
    plan = prepare(spec, tmp_path / 'out')
    validate_jobs(plan)
    candidate = next(j for j in plan['jobs'] if j['arm'] == 'candidate')
    fixture = Path(candidate['fixture'])
    if changed_input == 'fixture':
        (fixture / 'data.txt').write_text('different candidate input')
    else:
        staged = fixture / '.agents/skills/common/SKILL.md'
        staged.write_text('different candidate catalog')
        candidate['catalog_frames'][str(staged)] = freeze_candidate(staged)['package_sha256']
    candidate['initial_tree'] = tree(fixture)
    with pytest.raises(ValueError, match='shared frozen'):
        validate_jobs(plan)


def test_hermes_request_guard_contains_paths_and_rejects_shell_escape(tmp_path):
    fixture, catalog = tmp_path / 'fixture', tmp_path / 'catalog'
    fixture.mkdir()
    catalog.mkdir()
    assert study_guard('write_file', {'path': 'answer.txt'}, fixture, catalog) is None
    assert study_guard('read_file', {'path': str(catalog / 'leaf/SKILL.md')}, fixture, catalog) is None
    assert study_guard('write_file', {'path': '../external.txt'}, fixture, catalog)
    assert study_guard('patch', {'mode': 'patch', 'patch': '*** Update File: ../outside.py'}, fixture, catalog)
    assert study_guard('terminal', {'command': 'python -m pytest tests -q'}, fixture, catalog) is None
    for command in ('curl example.com', 'python -c "import os"', 'pytest; curl example.com', 'python ../outside.py'):
        assert study_guard('terminal', {'command': command}, fixture, catalog)
    assert study_guard('skill_manage', {}, fixture, catalog)
    assert study_guard('terminal', {'command': 'pytest', 'workdir': '../outside'}, fixture, catalog)
    assert study_guard('terminal', {'command': 'pytest', 'background': True}, fixture, catalog)
    assert study_guard('patch', {'mode': 'patch', 'patch': '*** Update File: safe.py\n*** Move to: ../outside.py'}, fixture, catalog)
