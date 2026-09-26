"""Validate a draft through its intended target layout without applying it."""
from pathlib import Path
import sys,json,tempfile,shutil
import oracle
root=Path(sys.argv[1]).resolve()
failures=[]
source=Path(__file__).parent/'fixtures/revise-project'
for original in source.rglob('*'):
 if original.is_file():
  target=root/original.relative_to(source)
  if not target.is_file() or target.read_bytes()!=original.read_bytes():failures.append('Original source changed: '+original.relative_to(source).as_posix())
proposal=root/'deliverables/project-instructions.md'
if not proposal.is_file() or not proposal.read_text(encoding='utf-8').strip():failures.append('Readable instruction proposal missing')
if not failures:
 with tempfile.TemporaryDirectory() as temp:
  staged=Path(temp)/'validation';shutil.copytree(root,staged)
  shutil.copy2(proposal,staged/'project/AGENTS.md')
  result=oracle.evaluate(staged,'revise-project')
  failures+=result['failures'];passed=result['passed']+1
else:passed=0
print(json.dumps({'passed':passed,'failed':len(failures),'failures':failures}))
sys.exit(bool(failures))
