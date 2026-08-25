import sqlite3, json, hashlib, time
from pathlib import Path

class DB:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cx = sqlite3.connect(self.path)
        self.cx.row_factory = sqlite3.Row
        self._init_schema()

    def _cols(self, table):
        try:
            return [r[1] for r in self.cx.execute(f'PRAGMA table_info({table})').fetchall()]
        except sqlite3.OperationalError:
            return []

    def _create_queue(self):
        self.cx.execute('''CREATE TABLE IF NOT EXISTS queue(
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            playlist_index INTEGER,
            playlist_added TEXT,
            youtube_id TEXT,
            isrc TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            selected_spotify INTEGER,
            selected_hook INTEGER,
            error TEXT,
            data_json TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

    def _migrate_queue(self):
        cols = self._cols('queue')
        if not cols:
            self._create_queue(); return
        if 'id' not in cols:
            # Older versions had incompatible primary-key layouts. Preserve every
            # row in a legacy table, then create the stable v2 queue schema.
            legacy = f"queue_legacy_{int(time.time())}"
            self.cx.execute(f'ALTER TABLE queue RENAME TO {legacy}')
            self._create_queue()
            oldcols = self._cols(legacy)
            rows = self.cx.execute(f'SELECT * FROM {legacy}').fetchall()
            for r in rows:
                d = dict(r)
                url = d.get('url') or d.get('youtube_url') or ''
                title = d.get('title') or ''
                qid = d.get('queue_id') or d.get('id') or hashlib.sha1(url.encode('utf-8')).hexdigest()[:16]
                self.cx.execute('''INSERT OR IGNORE INTO queue(id,title,url,playlist_index,youtube_id,isrc,status,selected_hook,error,data_json,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''',
                    (qid,title,url,d.get('playlist_index'),d.get('youtube_id'),d.get('isrc'),
                     d.get('status') or 'PENDING',d.get('selected_hook'),d.get('error'),d.get('data_json')))
            return
        required = {
            'playlist_added':'TEXT','youtube_id':'TEXT','isrc':'TEXT',
            'status':"TEXT NOT NULL DEFAULT 'PENDING'",'selected_spotify':'INTEGER',
            'selected_hook':'INTEGER','error':'TEXT','data_json':'TEXT','updated_at':'TEXT'
        }
        for name, definition in required.items():
            if name not in cols:
                try: self.cx.execute(f'ALTER TABLE queue ADD COLUMN {name} {definition}')
                except sqlite3.OperationalError: pass
        self.cx.execute("UPDATE queue SET status='PENDING' WHERE status IS NULL OR status=''")

    def _init_schema(self):
        self._migrate_queue()
        self.cx.execute('''CREATE TABLE IF NOT EXISTS youtube_done(
            youtube_id TEXT PRIMARY KEY, isrc TEXT, title TEXT, final_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        self.cx.execute('''CREATE TABLE IF NOT EXISTS songs(
            isrc TEXT PRIMARY KEY, title TEXT, artist TEXT, album TEXT,
            spotify_url TEXT, youtube_id TEXT, data_json TEXT,
            final_audio_path TEXT, final_reel_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        self.cx.execute('''CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT, queue_id TEXT, stage TEXT,
            message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        self.cx.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_queue_id ON queue(id)')
        self.cx.commit()

    def upsert(self, qid, title, playlist_index, url, playlist_added=None):
        self.cx.execute('''INSERT OR IGNORE INTO queue(id,title,url,playlist_index,playlist_added)
                           VALUES(?,?,?,?,?)''', (qid,title,url,playlist_index,playlist_added))
        self.cx.execute('''UPDATE queue SET title=?,url=?,playlist_index=?,playlist_added=?,updated_at=CURRENT_TIMESTAMP WHERE id=?''',
                        (title,url,playlist_index,playlist_added,qid))
        self.cx.commit()

    def get(self,qid):
        return self.cx.execute('SELECT * FROM queue WHERE id=?',(qid,)).fetchone()

    def set_status(self,qid,status,error=None,**kwargs):
        sets=['status=?','error=?','updated_at=CURRENT_TIMESTAMP']; vals=[status,error]
        for k,v in kwargs.items(): sets.append(k+'=?'); vals.append(v)
        vals.append(qid)
        self.cx.execute('UPDATE queue SET '+','.join(sets)+' WHERE id=?',vals); self.cx.commit()

    def save_json(self,qid,key,obj):
        row=self.get(qid); data=json.loads(row['data_json'] or '{}') if row else {}
        data[key]=obj
        self.cx.execute('UPDATE queue SET data_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                        (json.dumps(data,ensure_ascii=False),qid)); self.cx.commit()

    def event(self,qid,stage,message):
        self.cx.execute('INSERT INTO events(queue_id,stage,message) VALUES(?,?,?)',(qid,stage,message)); self.cx.commit()

    def youtube_exists(self,yid):
        return self.cx.execute('SELECT 1 FROM youtube_done WHERE youtube_id=?',(yid,)).fetchone() is not None

    def mark_youtube_done(self,yid,isrc,title,path):
        self.cx.execute('INSERT OR REPLACE INTO youtube_done(youtube_id,isrc,title,final_path) VALUES(?,?,?,?)',(yid,isrc,title,path)); self.cx.commit()

    def song_exists(self,isrc):
        return self.cx.execute('SELECT 1 FROM songs WHERE isrc=?',(isrc,)).fetchone() is not None

    def song_final_paths(self,isrc):
        r=self.cx.execute('SELECT final_audio_path,final_reel_path FROM songs WHERE isrc=?',(isrc,)).fetchone()
        return (r['final_audio_path'],r['final_reel_path']) if r else (None,None)

    def save_song(self,sp,yid,data,final_audio=None,final_reel=None):
        self.cx.execute('''INSERT INTO songs(isrc,title,artist,album,spotify_url,youtube_id,data_json,final_audio_path,final_reel_path)
                           VALUES(?,?,?,?,?,?,?,?,?)
                           ON CONFLICT(isrc) DO UPDATE SET title=excluded.title,artist=excluded.artist,album=excluded.album,
                           spotify_url=excluded.spotify_url,youtube_id=excluded.youtube_id,data_json=excluded.data_json,
                           final_audio_path=COALESCE(excluded.final_audio_path,songs.final_audio_path),
                           final_reel_path=COALESCE(excluded.final_reel_path,songs.final_reel_path),updated_at=CURRENT_TIMESTAMP''',
                        (sp.get('isrc'),sp.get('title'),sp.get('artist'),sp.get('album'),sp.get('url'),yid,
                         json.dumps(data,ensure_ascii=False),final_audio,final_reel)); self.cx.commit()

    def list_pending_ordered(self):
        return self.cx.execute('''SELECT * FROM queue ORDER BY
            CASE WHEN playlist_added IS NULL OR playlist_added='' THEN 1 ELSE 0 END,
            playlist_added ASC, playlist_index ASC''').fetchall()
