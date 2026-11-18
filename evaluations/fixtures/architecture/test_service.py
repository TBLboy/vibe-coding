import unittest
from service import Service

class TestService(unittest.TestCase):
    def test_contract(self):
        s = Service()
        self.assertEqual(s.submit('1', 'timeout'), 'retryable')
        self.assertEqual(s.submit('1', ''), 'terminal')
        self.assertEqual(s.submit('1', 'ok'), 'accepted')
        self.assertEqual(s.submit('1', 'ok'), 'duplicate')
