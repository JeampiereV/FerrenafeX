import secrets
from flask import session, request

SESSION_KEY = '_csrf_token'

def get_token():
    token = session.get(SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[SESSION_KEY] = token
    return token

def validate_request():
    expected = session.get(SESSION_KEY)
    supplied = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
    return bool(expected and supplied and secrets.compare_digest(expected, supplied))
