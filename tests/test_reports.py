import unittest
class ReportsContractTest(unittest.TestCase):
    def test_statuses(self): self.assertEqual(set(['created','received','in_review','in_attention','referred','resolved','closed','rejected']), set(['created','received','in_review','in_attention','referred','resolved','closed','rejected']))
if __name__=='__main__': unittest.main()
