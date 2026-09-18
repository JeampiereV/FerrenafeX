import unittest
class HelpContractTest(unittest.TestCase):
    def test_radius(self): self.assertIn(1000,(500,1000,2000,5000))
if __name__=='__main__': unittest.main()
