import sqlite3
from pathlib import Path
from flask import current_app,g
SCHEMA=Path(__file__).resolve().parent/'database'/'schema.sql'
def get_db():
    if 'db' not in g:
        path=current_app.config['DATABASE_PATH']; Path(path).parent.mkdir(parents=True,exist_ok=True)
        g.db=sqlite3.connect(path); g.db.row_factory=sqlite3.Row; g.db.execute('PRAGMA foreign_keys=ON')
    return g.db
def close_db(_=None):
    db=g.pop('db',None)
    if db: db.close()
def init_db():
    db=get_db(); db.executescript(SCHEMA.read_text(encoding='utf-8'))
    cols={r['name'] for r in db.execute('PRAGMA table_info(users)').fetchall()}
    if 'authority_type' not in cols: db.execute('ALTER TABLE users ADD COLUMN authority_type TEXT')
    if 'birth_date' not in cols: db.execute('ALTER TABLE users ADD COLUMN birth_date TEXT')
    db.commit()
def q(sql,params=(),one=False):
    c=get_db().execute(sql,params); r=c.fetchone() if one else c.fetchall(); c.close(); return r
def x(sql,params=()):
    c=get_db().execute(sql,params); get_db().commit(); return c.lastrowid
