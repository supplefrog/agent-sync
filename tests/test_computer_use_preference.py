"""Computer-use selector acceptance through the existing publication fixture."""
import copy
import unittest
import test_preference_data_classification as fixtures


class ComputerUsePreferenceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PreferenceDataClassificationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.new = copy.deepcopy(self.fixture.old)
        self.fixture.new['roles']['computer_use'] = {'model': 'gpt-6.1-terra', 'reasoning': 'medium'}
        self.fixture.row['preference_roles'] = ['computer_use']
        self.fixture.put(self.fixture.name, self.fixture.core(self.fixture.new))

    def test_explicit_computer_use_selector_is_data_without_behavior_claim(self):
        result = self.fixture.eligible()
        self.assertTrue(result['eligible'])
        self.assertFalse(result['behavioral_proof'])
        self.assertTrue(self.fixture.check())

    def test_computer_use_selector_cannot_carry_instructions(self):
        self.fixture.new['roles']['computer_use']['instructions'] = 'New prose'
        self.fixture.put(self.fixture.name, self.fixture.core(self.fixture.new))
        self.assertIsNone(self.fixture.eligible())


if __name__ == '__main__':
    unittest.main()
