import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import unittest

ROOT = Path(os.environ["PR_REPLAY_ASSETS"]).resolve()
HOST = ROOT.parent / "lcmx-unload" / "hermes-installed-d6d4be3"
RUNNER = Path(os.environ["PR_REPLAY_PYTHON"])
BASE = "9eeb724522bb64bd1663711ac4525196755bff2d"
HEAD = "6cb081cc1018becd25448dddab6dc89b24a11c37"

class TestHermesUnload(unittest.TestCase):
    def verify_archived_source(self, revision):
        export = ROOT / ("runtime-" + revision[:8])
        archive = ROOT / ("source-" + revision[:8] + ".tar")
        with tarfile.open(archive) as source:
            self.assertEqual(source.pax_headers.get("comment"), revision)
            for item in source:
                if not item.isfile() or item.name.split("/")[0] in {".agents", ".github"}:
                    continue
                expected = source.extractfile(item).read()
                actual = (export / item.name).read_bytes()
                self.assertEqual(hashlib.sha256(actual).digest(), hashlib.sha256(expected).digest(), item.name)
        return export

    def test_database_handles_after_unload(self):
        for revision, expected in ((BASE, "bug"), (HEAD, "fixed")):
            with self.subTest(revision=revision):
                export = self.verify_archived_source(revision)
                result = subprocess.run(
                    [str(RUNNER), "-B", str(Path(__file__).with_name("reproduce.py")), "--expect-" + expected],
                    env=os.environ | {"LCMX_PROOF_ROOT": str(ROOT), "LCMX_PROOF_SOURCE": str(export), "LCMX_HERMES_PROOF_SOURCE": str(HOST)},
                    cwd=ROOT, capture_output=True, text=True, check=True, timeout=120,
                )
                evidence = json.loads(result.stdout.splitlines()[-1])
                print(json.dumps({"revision": revision, "expected": expected, "observed": evidence}))
