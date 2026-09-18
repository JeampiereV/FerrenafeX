import unittest
try:
    from services.command_service import run
except ModuleNotFoundError:
    run=None
class PermissionContractTest(unittest.TestCase):
    @unittest.skipIf(run is None,'Instala Flask con pip install -r requirements.txt')
    def test_module_imports(self): self.assertTrue(callable(run))
if __name__=='__main__': unittest.main()
