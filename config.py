import os
from pathlib import Path
BASE_DIR=Path(__file__).resolve().parent
p=BASE_DIR/'.env'
if p.exists():
    for line in p.read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            k,v=line.split('=',1); os.environ.setdefault(k.strip(),v.strip().strip('"').strip("'"))
class Config:
    SECRET_KEY=os.getenv('FLASK_SECRET_KEY') or 'change-this-secret-before-production'
    OWNER_CODE=os.getenv('FERRENAFE_OWNER_CODE','62863117')
    DATABASE_PATH=str(BASE_DIR/os.getenv('DATABASE_PATH','database/ferre_alerta.db'))
    MAX_CONTENT_LENGTH=5*1024*1024
    SESSION_COOKIE_HTTPONLY=True
    SESSION_COOKIE_SAMESITE='Lax'
    SESSION_COOKIE_SECURE=os.getenv('SESSION_COOKIE_SECURE','0') == '1'
    UPLOAD_ROOT=str(BASE_DIR/'uploads')
