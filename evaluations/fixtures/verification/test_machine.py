import unittest
from machine import transition

class TestMachine(unittest.TestCase):
    def test_legal(self):
        self.assertEqual(transition('prepare', 'implement'), 'implement')
    def test_illegal(self):
        with self.assertRaises(ValueError):
            transition('prepare', 'verify')
    def test_terminal(self):
        with self.assertRaises(ValueError):
            transition('complete', 'implement')
