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
    SESSION_COOKIE_SECURE=os.getenv('SESSION_COOKIE_SECURE','1' if os.getenv('RENDER') else '0') == '1'
    SESSION_COOKIE_NAME='ferrenafex_session'
    SESSION_COOKIE_SAMESITE='Lax'
    MAIL_SERVER=os.getenv('MAIL_SERVER','')
    MAIL_PORT=int(os.getenv('MAIL_PORT','587') or 587)
    MAIL_USERNAME=os.getenv('MAIL_USERNAME','')
    MAIL_PASSWORD=os.getenv('MAIL_PASSWORD','')
    MAIL_DEFAULT_SENDER=os.getenv('MAIL_DEFAULT_SENDER') or os.getenv('MAIL_USERNAME','')
    APP_BASE_URL=os.getenv('APP_BASE_URL','').rstrip('/')
    UPLOAD_ROOT=str(BASE_DIR/'uploads')
