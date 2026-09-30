"""Build explicit source-behavior questions; never infer semantic loss from keywords."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import Sequence
import artifact_hash
import fleet
import validate

def compare_sources(candidate: Path, references: Sequence[str | Path]) -> dict:
    candidate_snapshot = artifact_hash.freeze_candidate(candidate)
    proposed = candidate_snapshot['prompt_text'].lower().replace('\\', '/')
    inventories = []
    for supplied in references:
        path = Path(supplied).absolute()
        if path.is_dir():
            path = path/'SKILL.md'
        if not path.is_file() or fleet.is_linklike_path(path):
            raise ValueError('reference skill must be an existing regular source')
        snapshot = artifact_hash.freeze_candidate(path)
        metadata, _ = validate.frontmatter(path.read_text(encoding='utf-8'))
        name = metadata.get('name', path.parent.name)
        package_reference = name.lower()+'/skill.md' in proposed
        named = name.lower() in proposed
        relationship = 'concrete-package-reference' if package_reference else 'named-source-only' if named else 'no-source-reference-observed'
        clues = []
        for relative, expected in snapshot['files'].items():
            if Path(relative).suffix.lower() != '.md':
                continue
            raw = (path.parent/relative).read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError('reference source changed during review; retry')
            text = raw.decode('utf-8')
            section = 'entrypoint'
            for number, line in enumerate(text.splitlines(),1):
                if line.startswith('#'):
                    section = line.lstrip('# ').strip()
                elif re.search(r'\b(read|fetch|search|preserve|resolve|validate|verify|only|before|when|must|do not)\b',line,re.I) and len(line.strip()) >= 35:
                    # This is an addressable excerpt, not an asserted behavior contract.
                    excerpt = line.strip()[:240]
                    words = set(re.findall(r'[a-z]{4,}',excerpt.lower())) - {'when','that','with','from','this','only','before','read'}
                    signal = len([w for w in words if w in proposed]) >= 3
                    clues.append({'source_file':relative,'line':number,'section':section,'excerpt':excerpt,
                                  'candidate_text_signal':signal,
                                  'question':'Is this applicable behavior reused, adapted, preserved natively, deliberately deferred, or missing?',
                                  'status':'verify-inheritance-and-host-fit' if package_reference else 'needs-behavior-review'})
                if len(clues) >= 24:
                    break
            if len(clues) >= 24:
                break
        suggestion = ('Verify read-through, selected supporting files, host boundaries and update lifecycle; avoid duplicating the source.'
                      if package_reference else 'Make source reuse concrete or port the needed procedure into the existing owner; website links or a source name alone do not preserve its workflow.')
        inventories.append({'source_name':name,'source_sha256':snapshot['package_sha256'],
                            'source_files':snapshot['files'],'candidate_relationship_hint':relationship,
                            'behavior_clues':clues,'clues_are_partial':True,
                            'recommendation':{'suggestion':suggestion,
                                              'reason':'An existing procedure may contain decision rules, helpers or host strengths absent from the proposal; textual signals do not prove preservation.'},
                            'alternatives':[
                                {'approach':'reuse or reference the existing source','benefit':'preserves its procedures and avoids a mirror','cost':'depends on source availability, host fit and its actual update lifecycle'},
                                {'approach':'extend the existing native owner','benefit':'retains native capabilities and narrow discovery','cost':'needs explicit shared/source ownership and recovery checks'},
                                {'approach':'port selected portable behavior','benefit':'works without the native source dependency','cost':'creates provenance, licensing and update/merge obligations'},
                                {'approach':'leave or defer','benefit':'avoids unsupported duplication or behavior loss','cost':'the useful capability can remain unavailable'}],
                            'unresolved':['Applicability and semantic omissions require source inspection, not keyword scoring.',
                                          'A reference can preserve behavior without copying its text.',
                                          'Update propagation and runtime behavior must be exercised before claiming them.']})
    return {'mode':'explicit-source-behavior-review','sources':inventories,
            'automatic_semantic_verdict':False,
            'judgment_output':['State applicable useful behaviors and what the proposal omits or changes.',
                               'Recommend reuse, reference, native adaptation, selected port, or defer; give reasons.',
                               'Name the strongest meaningful alternative and its tradeoff.',
                               'Separate observed preservation, inferred fit, deliberate exclusions and unresolved limits.']}
