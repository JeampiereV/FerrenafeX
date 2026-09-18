import unittest, tempfile, os
from pathlib import Path
try:
    from app import create_app
except ModuleNotFoundError:
    create_app=None

class AuthSmokeTest(unittest.TestCase):
    @unittest.skipIf(create_app is None, 'Instala Flask con pip install -r requirements.txt')
    def test_fresh_app_has_no_users(self):
        fd,path=tempfile.mkstemp(suffix='.db'); os.close(fd); Path(path).unlink(missing_ok=True)
        app=create_app({'TESTING':True,'DATABASE_PATH':path,'SECRET_KEY':'test','OWNER_CODE':'62863117','UPLOAD_ROOT':'/tmp/fa-test-uploads'})
        with app.app_context():
            from database import q
            self.assertEqual(q('SELECT COUNT(*) c FROM users',one=True)['c'],0)
            self.assertIsNotNone(q("SELECT id FROM roles WHERE name='OWNER'",one=True))

if __name__=='__main__': unittest.main()
