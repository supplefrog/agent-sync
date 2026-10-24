"""Exact user-authorized transport, not a general mechanical prose waiver."""
from pathlib import Path
from unittest import mock
import copy, shutil, sys, tempfile, unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import instruction_changes as changes
import sync_git
import validate
ENTRY = 'skills/instruction-authoring/SKILL.md'
DOCUMENT = 'docs/system-requirements.md'
RESOURCE = 'skills/instruction-authoring/references/claim-based-testing-and-retirement.md'
OLD = b'../../docs/system-requirements.md#claim-based-testing-and-retirement'
NEW = b'references/claim-based-testing-and-retirement.md#claim-based-testing-and-retirement'

class ReferenceTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        shutil.copytree(ROOT / 'skills/instruction-authoring', self.repo / 'skills/instruction-authoring')
        (self.repo / 'docs').mkdir()
        # Freeze the approved historical source, not mutable current policy.
        published_document = ROOT / 'tests/fixtures/reference-transport/system-requirements-approved.md'
        shutil.copyfile(published_document, self.repo / DOCUMENT)
        self.baseline = {ENTRY: (ROOT / ENTRY).read_bytes().replace(NEW, OLD),
                         DOCUMENT: published_document.read_bytes()}
        self.row = {'change_kind': 'reference-transport', 'basis': 'user-correction',
                    'user_authorized_transport': True}
        self.paths = [ENTRY, RESOURCE]
        patch = mock.patch.object(changes, '_before', side_effect=lambda _source, _base, name: self.baseline.get(name))
        patch.start(); self.addCleanup(patch.stop)

    def eligible(self, name=ENTRY, owner='skills/instruction-authoring'):
        return changes.correction_eligibility(self.repo, self.repo, name, owner, self.row,
                                              'base', self.paths, [])

    def rejected(self):
        with self.assertRaises(sync_git.SyncBlocked): self.eligible()

    def test_exact_approved_transport_both_sources_qualify(self):
        for name in self.paths:
            result = self.eligible(name)
            self.assertTrue(result['eligible'])
            self.assertFalse(result['behavioral_proof'])
            self.assertFalse(result['approval_authenticated'])

    def test_transport_requires_explicit_user_basis_and_scope_declaration(self):
        for key, value in [('basis', 'mechanical-maintenance'), ('user_authorized_transport', False),
                           ('user_authorized_transport', 'true')]:
            with self.subTest(key=key, value=value):
                original = copy.deepcopy(self.row); self.row[key] = value
                self.rejected(); self.row = original

    def test_ordinary_mechanical_label_does_not_waive_reference_gate(self):
        self.row = {'basis': 'mechanical-maintenance'}
        self.assertIsNone(self.eligible())

    def test_other_owner_or_artifact_does_not_gain_transport_waiver(self):
        for name, owner in [(ENTRY, 'skills/other'), ('skills/other/SKILL.md', 'skills/other'),
                             (DOCUMENT, 'skills/instruction-authoring')]:
            with self.assertRaises(sync_git.SyncBlocked): self.eligible(name, owner)

    def test_both_repair_files_must_be_selected(self):
        for name in [ENTRY, RESOURCE]:
            self.paths = [name]; self.rejected()

    def test_unpublished_baseline_is_not_approved_source(self):
        self.baseline[DOCUMENT] += b'\n'; self.rejected()

    def test_canonical_document_must_remain_unchanged(self):
        (self.repo / DOCUMENT).write_bytes(self.baseline[DOCUMENT] + b'\n'); self.rejected()

    def test_baseline_entry_must_be_the_approved_published_entry(self):
        self.baseline[ENTRY] += b'\n'; self.rejected()

    def test_preexisting_resource_cannot_be_rewritten_as_transport(self):
        self.baseline[RESOURCE] = b'existing content'; self.rejected()

    def test_rewritten_resource_is_rejected_even_when_valid_markdown(self):
        path = self.repo / RESOURCE
        path.write_bytes(path.read_bytes() + b'\nAdditional instruction.\n'); self.rejected()

    def test_whitespace_change_is_not_verbatim_transport(self):
        path = self.repo / RESOURCE
        path.write_bytes(path.read_bytes().replace(b'## Claim-based', b'##  Claim-based', 1)); self.rejected()

    def test_extra_entrypoint_prose_is_not_link_repair(self):
        path = self.repo / ENTRY
        path.write_bytes(path.read_bytes() + b'\nAdditional instruction.\n'); self.rejected()

    def test_wrong_anchor_is_not_approved_link(self):
        path = self.repo / ENTRY
        path.write_bytes(path.read_bytes().replace(NEW, NEW + b'-wrong')); self.rejected()

    def test_missing_packaged_reference_is_rejected(self):
        (self.repo / RESOURCE).unlink(); self.rejected()

    def test_unrelated_missing_package_reference_still_fails_loading(self):
        (self.repo / 'skills/instruction-authoring/references/change-review.md').unlink()
        self.rejected()

    def test_validation_failure_cannot_be_skipped(self):
        with mock.patch.object(validate, 'validate_skill', return_value=['invalid']) as check:
            self.rejected(); check.assert_called_once_with(self.repo / ENTRY)

    def test_transport_must_not_claim_behavioral_measurements(self):
        for field in ['behavior_measurements', 'task_contract']:
            self.row[field] = []
            with self.assertRaisesRegex(sync_git.SyncBlocked, 'behavioral-adoption'): self.eligible()
            del self.row[field]

    def test_copied_package_loads_exact_target_without_repository_document(self):
        (self.repo / DOCUMENT).unlink()
        self.assertEqual(validate.validate_skill(self.repo / ENTRY), [])
        entry = (self.repo / ENTRY).read_bytes()
        self.assertIn(b'](' + NEW + b')', entry)
        target = (self.repo / ENTRY).parent / NEW.decode().split('#')[0]
        self.assertEqual(target.read_bytes(), (ROOT / RESOURCE).read_bytes())
        self.assertTrue(target.read_bytes().startswith(b'## Claim-based testing and retirement\n'))

if __name__ == '__main__': unittest.main()
