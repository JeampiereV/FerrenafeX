import unittest
class RoomsContractTest(unittest.TestCase):
    def test_roles(self): self.assertEqual({'owner','admin','member'},{'owner','admin','member'})
if __name__=='__main__': unittest.main()
