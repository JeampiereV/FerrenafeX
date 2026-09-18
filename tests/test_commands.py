import unittest
class CommandContractTest(unittest.TestCase):
    def test_sensitive_commands_are_named(self): self.assertEqual('/rango set RANGO ID'.split()[0],'/rango')
if __name__=='__main__': unittest.main()
