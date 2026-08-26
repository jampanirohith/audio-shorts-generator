import sqlite3,json
from pathlib import Path
class DB:
 def __init__(self,path):
  self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.cx=sqlite3.connect(self.path); self.cx.row_factory=sqlite3.Row
  self.cx.execute("""CREATE TABLE IF NOT EXISTS queue(serial INTEGER PRIMARY KEY,playlist_id TEXT UNIQUE,original_title TEXT,original_url TEXT,selected_video_id TEXT,selected_video_title TEXT,selected_video_url TEXT,status TEXT NOT NULL DEFAULT 'PENDING',error TEXT,metadata_json TEXT,final_path TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
  self.cx.execute("CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,serial INTEGER,stage TEXT,message TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
  self.cx.commit()
 def upsert(self,e):
  self.cx.execute("""INSERT INTO queue(serial,playlist_id,original_title,original_url) VALUES(?,?,?,?) ON CONFLICT(serial) DO UPDATE SET playlist_id=excluded.playlist_id,original_title=excluded.original_title,original_url=excluded.original_url""",(e['serial'],e['id'],e['title'],e['url'])); self.cx.commit()
 def get(self,s): return self.cx.execute("SELECT * FROM queue WHERE serial=?",(s,)).fetchone()
 def selected_exists(self,yid): return self.cx.execute("SELECT 1 FROM queue WHERE selected_video_id=? AND status='DONE'",(yid,)).fetchone() is not None
 def save(self,s,sel=None,metadata=None,final=None,status=None,error=None):
  sets=[]; vals=[]
  if sel: sets+=['selected_video_id=?','selected_video_title=?','selected_video_url=?']; vals += [sel['id'],sel['title'],sel['url']]
  if metadata is not None: sets.append('metadata_json=?'); vals.append(json.dumps(metadata,ensure_ascii=False))
  if final is not None: sets.append('final_path=?'); vals.append(str(final))
  if status is not None: sets.append('status=?'); vals.append(status)
  sets += ['error=?','updated_at=CURRENT_TIMESTAMP']; vals += [error,s]; self.cx.execute('UPDATE queue SET '+','.join(sets)+' WHERE serial=?',vals); self.cx.commit()
 def reset(self,s): self.cx.execute("UPDATE queue SET status='PENDING',error=NULL WHERE serial=?",(s,)); self.cx.commit()
 def event(self,s,stage,msg): self.cx.execute("INSERT INTO events(serial,stage,message) VALUES(?,?,?)",(s,stage,msg)); self.cx.commit()
