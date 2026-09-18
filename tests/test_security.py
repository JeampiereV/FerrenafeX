import unittest
class SecurityContractTest(unittest.TestCase):
    def test_owner_code_is_not_in_frontend_sources(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        for folder in ('templates','static'):
            for p in (root/folder).rglob('*'):
                if p.is_file() and p.suffix in ('.html','.js','.css'):
                    self.assertNotIn('62863117',p.read_text(encoding='utf-8'))
if __name__=='__main__': unittest.main()
