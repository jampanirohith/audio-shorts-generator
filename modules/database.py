from __future__ import annotations
import json, sqlite3, hashlib
from pathlib import Path

class DB:
    def __init__(self,path):
        self.path=Path(path); self.con=sqlite3.connect(self.path); self.con.row_factory=sqlite3.Row
        self.con.execute("""CREATE TABLE IF NOT EXISTS songs(
          serial INTEGER PRIMARY KEY, playlist_id TEXT, playlist_title TEXT, playlist_index INTEGER,
          original_song_json TEXT NOT NULL, final_video_json TEXT, final_video_id TEXT, final_video_url TEXT,
          audio_fingerprint TEXT, hook_start REAL, hook_end REAL, hook_score REAL,
          final_reel TEXT, final_audio TEXT, status TEXT, error TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        self.con.commit()
    def save(self,serial,**kw):
        cur=self.con.execute("SELECT serial FROM songs WHERE serial=?",(serial,))
        exists=cur.fetchone()
        if exists:
            cols=[]; vals=[]
            for k,v in kw.items(): cols.append(f"{k}=?"); vals.append(v)
            cols.append("updated_at=CURRENT_TIMESTAMP")
            self.con.execute(f"UPDATE songs SET {', '.join(cols)} WHERE serial=?",(*vals,serial))
        else:
            data={"serial":serial,**kw}
            keys=list(data); vals=[data[k] for k in keys]
            self.con.execute(f"INSERT INTO songs ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})",vals)
        self.con.commit()
    def get(self,serial):
        return self.con.execute("SELECT * FROM songs WHERE serial=?",(serial,)).fetchone()
    def selected_exists(self,video_id):
        return self.con.execute("SELECT 1 FROM songs WHERE final_video_id=? AND status='DONE' LIMIT 1",(video_id,)).fetchone() is not None
    def redo(self,serial):
        row=self.get(serial)
        if not row: return False
        self.save(serial,status="PENDING",final_reel=None,final_audio=None,hook_start=None,hook_end=None,hook_score=None,error=None)
        return True
    def close(self): self.con.close()
