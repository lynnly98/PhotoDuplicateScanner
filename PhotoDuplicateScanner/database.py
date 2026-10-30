import sqlite3
import sys
from contextlib import closing
from pathlib import Path

BASE = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
DATA = BASE / 'data'
DATA.mkdir(exist_ok=True)
DB = DATA / 'scanner.db'


def connect():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA busy_timeout=30000')
    return c


def init():
    with closing(connect()) as c, c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS photos (
          path TEXT PRIMARY KEY COLLATE NOCASE, root TEXT NOT NULL,
          size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL,
          sha256 TEXT, last_seen TEXT, active INTEGER DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_size ON photos(active,size);
        CREATE INDEX IF NOT EXISTS idx_hash ON photos(active,sha256);
        CREATE INDEX IF NOT EXISTS idx_root ON photos(root,last_seen);
        CREATE TABLE IF NOT EXISTS scan_status (
          id INTEGER PRIMARY KEY CHECK(id=1), run_id TEXT, phase TEXT,
          scanned INTEGER DEFAULT 0, hashed INTEGER DEFAULT 0,
          errors INTEGER DEFAULT 0, current_path TEXT, started TEXT,
          finished TEXT, message TEXT
        );
        INSERT OR IGNORE INTO scan_status(id,phase,message) VALUES(1,'idle','No scans yet');
        CREATE TABLE IF NOT EXISTS scan_errors (
          id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT,
          path TEXT, error TEXT
        );
        CREATE TABLE IF NOT EXISTS recycle_log (
          id TEXT PRIMARY KEY, created TEXT, path TEXT, sha256 TEXT,
          state TEXT, message TEXT
        );
        CREATE TABLE IF NOT EXISTS folder_jobs (
          id TEXT PRIMARY KEY, root TEXT NOT NULL, created TEXT NOT NULL,
          scan_run_id TEXT, state TEXT NOT NULL, total INTEGER DEFAULT 0,
          bytes INTEGER DEFAULT 0, done INTEGER DEFAULT 0,
          recycled INTEGER DEFAULT 0, failed INTEGER DEFAULT 0,
          mode TEXT NOT NULL DEFAULT 'within'
        );
        CREATE TABLE IF NOT EXISTS folder_items (
          job_id TEXT NOT NULL, seq INTEGER NOT NULL, path TEXT NOT NULL,
          size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL, sha256 TEXT NOT NULL,
          keeper TEXT NOT NULL, state TEXT DEFAULT 'pending', message TEXT DEFAULT '',
          PRIMARY KEY(job_id,seq), UNIQUE(job_id,path)
        );
        ''')

    # Non-destructive migration for projects created before V1.1.
    with closing(connect()) as c, c:
        photo_columns = {r['name'] for r in c.execute('PRAGMA table_info(photos)')}
        if 'media_type' not in photo_columns:
            c.execute("ALTER TABLE photos ADD COLUMN media_type TEXT NOT NULL DEFAULT 'photo'")
        c.execute('CREATE INDEX IF NOT EXISTS idx_media_hash ON photos(active,media_type,sha256)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_media_size ON photos(active,media_type,size)')
        job_columns = {r['name'] for r in c.execute('PRAGMA table_info(folder_jobs)')}
        if 'mode' not in job_columns:
            c.execute("ALTER TABLE folder_jobs ADD COLUMN mode TEXT NOT NULL DEFAULT 'within'")
        if 'media_type' not in job_columns:
            c.execute("ALTER TABLE folder_jobs ADD COLUMN media_type TEXT NOT NULL DEFAULT 'photo'")
        columns = {r['name'] for r in c.execute('PRAGMA table_info(scan_status)')}
        for name, typ in {'scan_mode':"TEXT DEFAULT 'photos'", 'hash_total':'INTEGER DEFAULT 0', 'hash_done':'INTEGER DEFAULT 0', 'index_estimate':'INTEGER DEFAULT 0', 'phase_started':'TEXT', 'index_bytes':'INTEGER DEFAULT 0', 'hash_bytes':'INTEGER DEFAULT 0', 'current_folder':'TEXT'}.items():
            if name not in columns: c.execute(f'ALTER TABLE scan_status ADD COLUMN {name} {typ}')

    # V1.9 pixel matching is additive; whole-file SHA-256 remains unchanged.
    with closing(connect()) as c, c:
        for table, fields in {
            'photos': {'image_sha256':'TEXT','image_checked':'INTEGER DEFAULT 0','image_error':'TEXT'},
            'folder_jobs': {'match_kind':"TEXT NOT NULL DEFAULT 'exact'"},
            'folder_items': {'match_digest':'TEXT'},
            'recycle_log': {'match_kind':"TEXT NOT NULL DEFAULT 'exact'"},
        }.items():
            present={r['name'] for r in c.execute('PRAGMA table_info('+table+')')}
            for name,definition in fields.items():
                if name not in present:c.execute('ALTER TABLE '+table+' ADD COLUMN '+name+' '+definition)
        c.execute('CREATE INDEX IF NOT EXISTS idx_image_hash ON photos(active,media_type,image_sha256)')

    with closing(connect()) as c,c:
        present={r['name'] for r in c.execute('PRAGMA table_info(photos)')}
        new_match_keys='match_key' not in present
        for name,definition in {'video_sha256':'TEXT','video_checked':'INTEGER DEFAULT 0','video_error':'TEXT','match_key':'TEXT'}.items():
            if name not in present:c.execute('ALTER TABLE photos ADD COLUMN '+name+' '+definition)
        c.execute('CREATE INDEX IF NOT EXISTS idx_match_key ON photos(active,match_key)')
        c.execute("UPDATE photos SET match_key=media_type||':raw:'||sha256 WHERE match_key IS NULL AND sha256 IS NOT NULL")
        if new_match_keys:
            from photo_match import refresh_match_keys
            refresh_match_keys(c)

    with closing(connect()) as c,c:
        if 'content_skipped' not in {r['name'] for r in c.execute('PRAGMA table_info(scan_status)')}:
            c.execute('ALTER TABLE scan_status ADD COLUMN content_skipped INTEGER DEFAULT 0')

    # V2.1 additive similarity cache. Confirmed match_key is never replaced.
    with closing(connect()) as c,c:
        present={r['name'] for r in c.execute('PRAGMA table_info(photos)')}
        for name,definition in {'sim_phash':'TEXT','sim_dhash':'TEXT','sim_thumb':'BLOB','sim_aspect':'REAL','sim_checked':'INTEGER DEFAULT 0'}.items():
            if name not in present:c.execute('ALTER TABLE photos ADD COLUMN '+name+' '+definition)
        c.execute('CREATE TABLE IF NOT EXISTS similarity_members(path TEXT PRIMARY KEY COLLATE NOCASE,group_id TEXT NOT NULL,score REAL NOT NULL)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_similarity_group ON similarity_members(group_id)')
        c.execute('CREATE VIEW IF NOT EXISTS review_photos AS SELECT p.*,coalesce(s.group_id,p.match_key) review_key,CASE WHEN s.group_id IS NULL THEN 0 ELSE 1 END is_similar,s.score similarity_score FROM photos p LEFT JOIN similarity_members s ON s.path=p.path')
