import unittest
from engine import evaluate
from strategies import legacy

class TestEngine(unittest.TestCase):
    def test_default_and_public_import(self):
        self.assertEqual(evaluate(-3), 0)
        self.assertEqual(evaluate(3), 3)
        self.assertEqual(legacy(3), 3)
    def test_errors(self):
        with self.assertRaises(ValueError):
            evaluate('bad')
        with self.assertRaises(ValueError):
            evaluate(1, 'unknown')
