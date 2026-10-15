"""Loading diagnostics are signals; valid required procedures remain valid."""
from pathlib import Path
import tempfile
import unittest

import validate


class LoadingDiagnosticsTests(unittest.TestCase):
    def skill(self, body):
        return '---\nname: kept\ndescription: Required protocol.\nlicense: MIT\n---\n' + body

    def test_dense_body_is_signaled_without_size_rejection(self):
        text = self.skill('required procedure ' * 2000)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'kept/SKILL.md'
            target.parent.mkdir()
            target.write_text(text, encoding='utf-8')
            self.assertEqual([], validate.validate_skill(target))
        signals = validate.loading_signals(text)
        self.assertEqual(4000, signals['body_words'])
        self.assertTrue(signals['review_reasons'])

    def test_growth_below_absolute_ceiling_is_signaled(self):
        old = self.skill('common ' * 1000)
        new = self.skill('common ' * 1600)
        self.assertTrue(validate.loading_signals(new, old)['review_reasons'])
        self.assertFalse(validate.loading_signals(self.skill('common ' * 1100), old)['review_reasons'])

    def test_valid_compulsory_workflow_over_500_lines_is_a_review_signal(self):
        text = self.skill('Required step.\n' * 501)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'kept/SKILL.md'
            target.parent.mkdir()
            target.write_text(text, encoding='utf-8')
            self.assertEqual([], validate.validate_skill(target))
        self.assertTrue(validate.loading_signals(text)['review_reasons'])

    def test_frontmatter_and_line_endings_do_not_inflate_body(self):
        text = self.skill('required procedure\n')
        self.assertEqual(validate.loading_signals(text), validate.loading_signals(text.replace('\n', '\r\n')))
        self.assertEqual(2, validate.loading_signals(text)['body_words'])

