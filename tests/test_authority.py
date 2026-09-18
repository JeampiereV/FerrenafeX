import unittest
class AuthorityContractTest(unittest.TestCase):
    def test_statuses(self): self.assertIn('approved',['pending','approved','rejected','revoked'])
if __name__=='__main__': unittest.main()
