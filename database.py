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
    # FerreñafeX feature migrations for existing SQLite databases.
    table_cols = {r['name'] for r in db.execute('PRAGMA table_info(rooms)').fetchall()}
    if 'visibility' not in table_cols: db.execute("ALTER TABLE rooms ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'")
    lm_cols = {r['name'] for r in db.execute('PRAGMA table_info(learning_modules)').fetchall()}
    badge_cols={r['name'] for r in db.execute('PRAGMA table_info(badges)').fetchall()}
    if 'color' not in badge_cols: db.execute("ALTER TABLE badges ADD COLUMN color TEXT NOT NULL DEFAULT '#22c55e'")
    if 'details' not in lm_cols: db.execute("ALTER TABLE learning_modules ADD COLUMN details TEXT DEFAULT ''")
    help_cols={r['name'] for r in db.execute('PRAGMA table_info(help_requests)').fetchall()}
    if 'location_expires_at' not in help_cols: db.execute("ALTER TABLE help_requests ADD COLUMN location_expires_at TEXT")
    user_cols={r['name'] for r in db.execute('PRAGMA table_info(users)').fetchall()}
    if 'owner_expires_at' not in user_cols: db.execute("ALTER TABLE users ADD COLUMN owner_expires_at TEXT")
    if 'vip_expires_at' not in user_cols: db.execute("ALTER TABLE users ADD COLUMN vip_expires_at TEXT")
    ann_cols={r['name'] for r in db.execute('PRAGMA table_info(announcements)').fetchall()} if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='announcements'").fetchone() else set()
    if ann_cols and 'kind' not in ann_cols: db.execute("ALTER TABLE announcements ADD COLUMN kind TEXT NOT NULL DEFAULT 'OWNER'")
    room_cols={r['name'] for r in db.execute('PRAGMA table_info(rooms)').fetchall()} if db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rooms'").fetchone() else set()
    if room_cols and 'expires_at' not in room_cols: db.execute("ALTER TABLE rooms ADD COLUMN expires_at TEXT")
    code_cols={r['name'] for r in db.execute('PRAGMA table_info(owner_codes)').fetchall()}
    if 'expires_at' not in code_cols: db.execute("ALTER TABLE owner_codes ADD COLUMN expires_at TEXT")
    ann_cols={r['name'] for r in db.execute('PRAGMA table_info(announcements)').fetchall()}
    if 'animation' not in ann_cols: db.execute("ALTER TABLE announcements ADD COLUMN animation TEXT NOT NULL DEFAULT 'fade'")
    if 'animation_duration_ms' not in ann_cols: db.execute("ALTER TABLE announcements ADD COLUMN animation_duration_ms INTEGER NOT NULL DEFAULT 300")
    if 'font' not in ann_cols: db.execute("ALTER TABLE announcements ADD COLUMN font TEXT NOT NULL DEFAULT 'DM Sans'")
    if 'expires_at' not in ann_cols: db.execute("ALTER TABLE announcements ADD COLUMN expires_at TEXT")
    db.execute("CREATE TABLE IF NOT EXISTS room_messages(id INTEGER PRIMARY KEY AUTOINCREMENT,room_id INTEGER NOT NULL,sender_id INTEGER NOT NULL,message TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(room_id) REFERENCES rooms(id) ON DELETE CASCADE,FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE)")
    db.execute("CREATE TABLE IF NOT EXISTS live_locations(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL UNIQUE,latitude REAL NOT NULL,longitude REAL NOT NULL,accuracy REAL,context TEXT NOT NULL DEFAULT 'self',sharing INTEGER NOT NULL DEFAULT 1,expires_at TEXT NOT NULL,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_live_locations_expiry ON live_locations(expires_at,sharing)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_room_messages ON room_messages(room_id,created_at)")

    # One-time cleanup requested for the current release: start with no badges.
    db.execute("CREATE TABLE IF NOT EXISTS fx_migrations(name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    if not db.execute("SELECT 1 FROM fx_migrations WHERE name='clear_default_badges_v1'").fetchone():
        db.execute("DELETE FROM user_badges")
        db.execute("DELETE FROM badges")
        db.execute("INSERT INTO fx_migrations(name) VALUES('clear_default_badges_v1')")

    # FerreñafeX now exposes exactly two system roles: OWNER and MEMBER.
    # Create both before resolving their IDs. Existing accounts are preserved.
    db.execute("INSERT OR IGNORE INTO roles(name) VALUES('MEMBER')")
    db.execute("INSERT OR IGNORE INTO roles(name) VALUES('OWNER')")
    member_id=db.execute("SELECT id FROM roles WHERE name='MEMBER'").fetchone()[0]
    owner_id=db.execute("SELECT id FROM roles WHERE name='OWNER'").fetchone()[0]
    db.execute("UPDATE users SET role_id=? WHERE role_id<>?", (member_id, owner_id))
    db.execute("DELETE FROM role_permissions WHERE role_id IN (SELECT id FROM roles WHERE name IN ('CITIZEN','COLLABORATOR','STAFF','AUTHORITY'))")
    db.execute("DELETE FROM roles WHERE name IN ('CITIZEN','COLLABORATOR','STAFF','AUTHORITY')")
    # Expire temporary Owner/VIP access without needing a background worker.
    db.execute("UPDATE users SET role_id=?, owner_expires_at=NULL, updated_at=CURRENT_TIMESTAMP WHERE owner_expires_at IS NOT NULL AND owner_expires_at <= CURRENT_TIMESTAMP AND role_id=?", (member_id, owner_id))
    db.execute("UPDATE announcements SET active=0 WHERE expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP")
    db.commit()
def q(sql,params=(),one=False):
    c=get_db().execute(sql,params); r=c.fetchone() if one else c.fetchall(); c.close(); return r
def x(sql,params=()):
    c=get_db().execute(sql,params); get_db().commit(); return c.lastrowid
