import json, sqlite3
from datetime import datetime, timezone
from pathlib import Path

def now(): return datetime.now(timezone.utc).isoformat()
def jd(v): return json.dumps(v if v is not None else {}, ensure_ascii=False, default=str)

class PlaylistDB:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.cx=sqlite3.connect(self.path,timeout=30);self.cx.row_factory=sqlite3.Row
        self.cx.execute('PRAGMA journal_mode=WAL');self.cx.execute('PRAGMA synchronous=FULL');self._schema()
    def _schema(self):
        self.cx.executescript('''
        CREATE TABLE IF NOT EXISTS playlist_meta(id INTEGER PRIMARY KEY,playlist_id TEXT UNIQUE NOT NULL,playlist_url TEXT,title TEXT,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS playlist_entries(
          id INTEGER PRIMARY KEY AUTOINCREMENT, playlist_id TEXT NOT NULL, spotify_id TEXT NOT NULL,
          url TEXT NOT NULL, title TEXT NOT NULL, artists TEXT, album TEXT, isrc TEXT, duration REAL,
          playlist_order INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'yet_to_start',
          first_seen_at TEXT NOT NULL,last_seen_at TEXT NOT NULL,finished_serial INTEGER,
          stage TEXT NOT NULL DEFAULT 'SPOTIFY_SELECTED',last_error TEXT,
          UNIQUE(playlist_id,spotify_id)
        );
        CREATE INDEX IF NOT EXISTS idx_playlist_next ON playlist_entries(playlist_id,status,playlist_order);
        CREATE INDEX IF NOT EXISTS idx_playlist_isrc ON playlist_entries(isrc);
        ''')
        cols={r['name'] for r in self.cx.execute('PRAGMA table_info(playlist_entries)')}
        if 'duration' not in cols:
            self.cx.execute('ALTER TABLE playlist_entries ADD COLUMN duration REAL')
        # Normalize legacy playlist states to the only three supported states.
        self.cx.execute("UPDATE playlist_entries SET status='yet_to_start' WHERE lower(status) IN ('yet_to_start','yet to start','not_started','processing')")
        self.cx.execute("UPDATE playlist_entries SET status='error' WHERE lower(status) IN ('error','failed')")
        self.cx.execute("UPDATE playlist_entries SET status='finished' WHERE lower(status) IN ('finished','complete','completed')")
        self.cx.commit()
    def sync(self,pid,url,title,entries):
        t=now();existing={r['spotify_id'] for r in self.cx.execute('SELECT spotify_id FROM playlist_entries WHERE playlist_id=?',(pid,))};max_order=int(self.cx.execute('SELECT COALESCE(MAX(playlist_order),0) n FROM playlist_entries WHERE playlist_id=?',(pid,)).fetchone()['n'])
        self.cx.execute('BEGIN IMMEDIATE')
        try:
            self.cx.execute('INSERT INTO playlist_meta(playlist_id,playlist_url,title,updated_at) VALUES(?,?,?,?) ON CONFLICT(playlist_id) DO UPDATE SET playlist_url=excluded.playlist_url,title=excluded.title,updated_at=excluded.updated_at',(pid,url,title,t))
            seen=set()
            for e in entries:
                sid=str(e.get('spotify_id') or e.get('song_id') or '').strip()
                if not sid or sid in seen:continue
                seen.add(sid);artists=', '.join(e.get('artists') or [])
                if sid in existing:
                    self.cx.execute('UPDATE playlist_entries SET last_seen_at=?,url=?,title=?,artists=?,album=?,isrc=?,duration=? WHERE playlist_id=? AND spotify_id=?',(t,e.get('url',''),e.get('name',''),artists,e.get('album_name',''),e.get('isrc'),e.get('duration'),pid,sid))
                else:
                    max_order+=1;self.cx.execute('INSERT INTO playlist_entries(playlist_id,spotify_id,url,title,artists,album,isrc,duration,playlist_order,status,first_seen_at,last_seen_at,stage) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,sid,e.get('url',''),e.get('name',''),artists,e.get('album_name',''),e.get('isrc'),e.get('duration'),max_order,'yet_to_start',t,t,'SPOTIFY_SELECTED'));existing.add(sid)
            self.cx.commit()
        except Exception:self.cx.rollback();raise
    def first_pending(self,pid):return self.cx.execute("SELECT * FROM playlist_entries WHERE playlist_id=? AND status='yet_to_start' ORDER BY playlist_order LIMIT 1",(pid,)).fetchone()
    def by_serial(self,serial):return self.cx.execute('SELECT * FROM playlist_entries WHERE finished_serial=? LIMIT 1',(serial,)).fetchone()
    def mark_stage(self,pid,sid,stage,error=None):self.cx.execute('UPDATE playlist_entries SET stage=?,last_error=? WHERE playlist_id=? AND spotify_id=?',(stage,error,pid,sid));self.cx.commit()
    def set_finished(self,pid,sid,serial):self.cx.execute("UPDATE playlist_entries SET status='finished',finished_serial=?,stage='FINISHED',last_error=NULL WHERE playlist_id=? AND spotify_id=?",(serial,pid,sid));self.cx.commit()
    def reset(self,pid,sid,error=None,stage='ERROR'):self.cx.execute("UPDATE playlist_entries SET status='ERROR',finished_serial=NULL,last_error=?,stage=? WHERE playlist_id=? AND spotify_id=?",(error,stage,pid,sid));self.cx.commit()
    def snapshot(self,pid,sid):
        r=self.cx.execute('SELECT * FROM playlist_entries WHERE playlist_id=? AND spotify_id=?',(pid,sid)).fetchone()
        return dict(r) if r else None
    def restore_snapshot(self,snap):
        if not snap:return
        cols=[k for k in snap.keys() if k!='id']
        vals=[snap[k] for k in cols]
        self.cx.execute('DELETE FROM playlist_entries WHERE id=?',(snap['id'],))
        self.cx.execute('INSERT INTO playlist_entries(id,'+','.join(cols)+') VALUES(?,'+','.join('?' for _ in cols)+')',[snap['id'],*vals])
        self.cx.commit()
    def close(self):self.cx.close()
    def __enter__(self):return self
    def __exit__(self,*a):self.close()

class ReelDB:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.cx=sqlite3.connect(self.path,timeout=30);self.cx.row_factory=sqlite3.Row;self.cx.execute('PRAGMA journal_mode=WAL');self.cx.execute('PRAGMA synchronous=FULL');self._schema()
    def _schema(self):
        self.cx.executescript('''CREATE TABLE IF NOT EXISTS serial_state(id INTEGER PRIMARY KEY CHECK(id=1),next_serial INTEGER NOT NULL);
        INSERT OR IGNORE INTO serial_state(id,next_serial) VALUES(1,1);
        CREATE TABLE IF NOT EXISTS reels(serial INTEGER PRIMARY KEY,spotify_id TEXT,spotify_isrc TEXT,playlist_spotify_id TEXT,selected_youtube_id TEXT,selected_youtube_url TEXT,selected_youtube_title TEXT,status TEXT NOT NULL,stage TEXT NOT NULL,metadata_json TEXT,final_mp4 TEXT,final_json TEXT,created_at TEXT NOT NULL,finished_at TEXT);''');self.cx.commit()
    def allocate_serial(self):
        self.cx.execute('BEGIN IMMEDIATE');s=int(self.cx.execute('SELECT next_serial FROM serial_state WHERE id=1').fetchone()['next_serial']);self.cx.execute('UPDATE serial_state SET next_serial=? WHERE id=1',(s+1,));self.cx.commit();return s
    def create(self,s,spotify,pid):self.cx.execute('INSERT INTO reels(serial,spotify_id,spotify_isrc,playlist_spotify_id,status,stage,created_at) VALUES(?,?,?,?,?,?,?)',(s,spotify.get('spotify_id') or spotify.get('song_id'),spotify.get('isrc'),pid,'PROCESSING','SPOTIFY_SELECTED',now()));self.cx.commit()
    def stage(self,s,stage,meta=None):self.cx.execute('UPDATE reels SET stage=?,metadata_json=COALESCE(?,metadata_json) WHERE serial=?',(stage,jd(meta) if meta is not None else None,s));self.cx.commit()
    def set_youtube(self,s,sel):self.cx.execute('UPDATE reels SET selected_youtube_id=?,selected_youtube_url=?,selected_youtube_title=? WHERE serial=?',(sel.get('id'),sel.get('url'),sel.get('title'),s));self.cx.commit()
    def finish(self,s,meta,mp4,j):self.cx.execute('UPDATE reels SET status=\'FINISHED\',stage=\'FINISHED\',metadata_json=?,final_mp4=?,final_json=?,finished_at=? WHERE serial=?',(jd(meta),str(mp4),str(j),now(),s));self.cx.commit()
    def get(self,s):return self.cx.execute('SELECT * FROM reels WHERE serial=?',(s,)).fetchone()
    def active_for_playlist(self,pid):return self.cx.execute("SELECT * FROM reels WHERE playlist_spotify_id=? AND status='PROCESSING' ORDER BY serial DESC LIMIT 1",(pid,)).fetchone()
    def delete_job(self,s):self.cx.execute('DELETE FROM reels WHERE serial=?',(s,));self.cx.commit()
    def snapshot(self,s):
        r=self.cx.execute('SELECT * FROM reels WHERE serial=?',(s,)).fetchone() if s is not None else None
        state=self.cx.execute('SELECT next_serial FROM serial_state WHERE id=1').fetchone()
        return (dict(r) if r else None, int(state['next_serial']))
    def snapshot_before_new_serial(self):
        state=self.cx.execute('SELECT next_serial FROM serial_state WHERE id=1').fetchone()
        return (None, int(state['next_serial']))
    def restore_snapshot(self,s,snap):
        row,next_serial=snap
        self.cx.execute('DELETE FROM reels WHERE serial=?',(s,))
        if row:
            cols=[k for k in row.keys()]
            self.cx.execute('INSERT INTO reels('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',[row[k] for k in cols])
        self.cx.execute('UPDATE serial_state SET next_serial=? WHERE id=1',(next_serial,))
        self.cx.commit()
    def close(self):self.cx.close()
    def __enter__(self):return self
    def __exit__(self,*a):self.close()

class SongsDB:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True);self.cx=sqlite3.connect(self.path,timeout=30);self.cx.row_factory=sqlite3.Row;self.cx.execute('PRAGMA journal_mode=WAL');self.cx.execute('PRAGMA synchronous=FULL');self._schema()
    def _schema(self):
        self.cx.executescript('''CREATE TABLE IF NOT EXISTS songs(id INTEGER PRIMARY KEY AUTOINCREMENT,serial INTEGER UNIQUE NOT NULL,song_key TEXT UNIQUE NOT NULL,isrc TEXT,title TEXT,artists TEXT,album TEXT,spotify_url TEXT,spotify_track_id TEXT,youtube_video_id TEXT,youtube_url TEXT,spotify_source_file TEXT,spotdl_source_url TEXT,canonical_file TEXT,artwork_file TEXT,lrc_file TEXT,lrc_source TEXT,sync_json TEXT,hook_json TEXT,metadata_json TEXT,created_at TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_songs_isrc ON songs(isrc) WHERE isrc IS NOT NULL AND isrc<>'';''');self.cx.commit()
    def find_duplicate_isrc(self,isrc):
        if not isrc:return None
        return self.cx.execute('SELECT * FROM songs WHERE isrc=? LIMIT 1',(isrc,)).fetchone()
    def insert(self,d):
        cols=['serial','song_key','isrc','title','artists','album','spotify_url','spotify_track_id','youtube_video_id','youtube_url','spotify_source_file','spotdl_source_url','canonical_file','artwork_file','lrc_file','lrc_source','sync_json','hook_json','metadata_json','created_at'];self.cx.execute('INSERT INTO songs('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',tuple(d.get(c) for c in cols));self.cx.commit()
    def close(self):self.cx.close()
    def __enter__(self):return self
    def __exit__(self,*a):self.close()
