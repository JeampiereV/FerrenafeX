import os
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import unittest

import services.ocr_service as ocr

ROOT = Path(__file__).resolve().parents[1]


class RealtimeAndOcrContractTest(unittest.TestCase):
    def test_chat_server_emits_after_persisting(self):
        source = (ROOT / 'routes/community.py').read_text(encoding='utf-8')
        self.assertIn("mid=x('INSERT INTO private_messages", source)
        self.assertIn("socketio.emit('private_message'", source)
        self.assertIn("socketio.emit('room_message'", source)

    def test_frontends_have_id_dedup_and_recovery_polling(self):
        chat = (ROOT / 'static/js/chat.js').read_text(encoding='utf-8')
        rooms = (ROOT / 'static/js/rooms.js').read_text(encoding='utf-8')
        self.assertIn('seen', chat)
        self.assertIn('setInterval(()=>Chat.load(),10000)', chat)
        self.assertIn('roomSeen', rooms)
        self.assertIn('setInterval(loadRoomMessages,10000)', rooms)

    def test_ocr_request_contract(self):
        calls = {}

        class Response:
            status_code = 200
            text = ''
            def raise_for_status(self):
                pass
            def json(self):
                return {'ErrorMessage': '', 'ProcessedPages': 2, 'OCRText': [['uno', 'dos']]}

        def fake_post(url, **kwargs):
            calls.update(url=url, kwargs=kwargs)
            return Response()

        old_post = ocr.requests.post
        old_user = os.environ.get('ONLINEOCR_USERNAME')
        old_code = os.environ.get('ONLINEOCR_LICENSE_CODE')
        try:
            os.environ['ONLINEOCR_USERNAME'] = 'test-user'
            os.environ['ONLINEOCR_LICENSE_CODE'] = 'test-license'
            ocr.requests.post = fake_post
            upload = SimpleNamespace(filename='scan.pdf', stream=BytesIO(b'%PDF-1.7'), mimetype='application/pdf')
            result = ocr.process_document(upload, 'spanish')
        finally:
            ocr.requests.post = old_post
            if old_user is None: os.environ.pop('ONLINEOCR_USERNAME', None)
            else: os.environ['ONLINEOCR_USERNAME'] = old_user
            if old_code is None: os.environ.pop('ONLINEOCR_LICENSE_CODE', None)
            else: os.environ['ONLINEOCR_LICENSE_CODE'] = old_code

        self.assertEqual(result['text'], 'uno\n\ndos')
        self.assertEqual(calls['kwargs']['params']['pagerange'], 'allpages')
        self.assertEqual(calls['kwargs']['params']['gettext'], 'true')
        self.assertEqual(calls['kwargs']['headers']['UserName'], 'test-user')
        self.assertEqual(calls['kwargs']['headers']['LicenseCode'], 'test-license')


if __name__ == '__main__':
    unittest.main()
