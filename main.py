import argparse,hashlib,json,platform,shutil
from datetime import datetime,timezone
from pathlib import Path
from modules.db import PlaylistDB,ReelDB,SongsDB
from modules.youtube import playlist,search as ytsearch,info as ytinfo,rank as ytrank,choose as ytchoose,download_video_and_lrc
from modules.spotify import create_client as spcreate,search as spsearch,rank as sprank,choose as spchoose,download as spdownload,song_key
from modules.lyrics import fetch_librelyrics,parse_lrc
from modules.sync import synchronize
from modules.hooks import detect
from modules.songfile import make_canonical
from modules.video import probe,render

def utc():return datetime.now(timezone.utc).isoformat()
def load(path='config.json'):
 return json.loads(Path(path).read_text(encoding='utf-8'))
def ensure(c):
 for k in ['temp_dir','songs_dir','reels_dir','playlist_db_path','reel_db_path','songs_db_path']:
  p=Path(c[k]);(p.parent if p.suffix else p).mkdir(parents=True,exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def clean(p):shutil.rmtree(p,ignore_errors=True) if p and Path(p).exists() else None
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--config',default='config.json');a=ap.parse_args();cfg=load(a.config);ensure(cfg)
 with PlaylistDB(cfg['playlist_db_path']) as pdb,ReelDB(cfg['reel_db_path']) as rdb,SongsDB(cfg['songs_db_path']) as sdb:
  pid,ptitle,rows=playlist(cfg['playlist_url']);pdb.sync(pid,cfg['playlist_url'],ptitle,rows);entry=pdb.first_pending(pid)
  if not entry:print('No YET_TO_START playlist entries.');return
  serial=None;job=None;out=None;jsonpath=None;canonical=None
  try:
   print(f"\n{'='*78}\nPLAYLIST ENTRY [{entry['playlist_order']}]: {entry['title']}\n{'='*78}")
   original={'playlist_id':pid,'video_id':entry['video_id'],'url':entry['url'],'title':entry['title'],'playlist_order':entry['playlist_order']}
   results=ytsearch(entry['title'],cfg.get('top_youtube_results',10));ref=ytinfo(entry['url']);ranked=ytrank(results,entry['title'],ref,cfg);selected,ranked=ytchoose(ranked,cfg.get('youtube_selection_mode','automatic'));dup=rdb.duplicate_youtube(selected['id'])
   if dup:
    pdb.set_finished(pid,entry['video_id'],dup['serial']);print(f'Duplicate YouTube video; existing serial {dup["serial"]:04d}.');return
   serial=rdb.allocate_serial();job=Path(cfg['temp_dir'])/f'{serial:04d}';job.mkdir(parents=True);rdb.create(serial,selected,entry['video_id']);print(f'Assigned permanent serial: {serial:04d}')
   video,ytmeta,ytlrc,ytlrcmeta=download_video_and_lrc(selected['url'],job,selected['title']); source_probe=probe(video); print('YouTube video downloaded; best video/audio streams merged into MP4.')
   title=ytmeta.get('track') or ytmeta.get('title') or selected['title'];artists=ytmeta.get('artist') or ytmeta.get('artists') or ytmeta.get('uploader') or '';album=ytmeta.get('album') or ytmeta.get('album_title') or '';artists=' '.join(artists) if isinstance(artists,list) else str(artists)
   print('\nSearching Spotify from selected YouTube metadata ...');spq=' - '.join(x for x in [title,artists,album] if x);spclient=spcreate(cfg,job);sres=spsearch(spclient,spq);sranked=sprank(sres,title,artists,album,ytmeta.get('duration'),cfg);song,sranked=spchoose(sranked,cfg.get('spotify_selection_mode','automatic'));skey=song_key(song);existing=sdb.find_duplicate(selected['id'],skey)
   if existing:
    rdb.delete_job(serial);clean(job);pdb.set_finished(pid,entry['video_id'],existing['serial']);print(f'Duplicate canonical song; existing serial {existing["serial"]:04d}.');return
   spotify_audio,artwork=spdownload(spclient,song,cfg,job);spotify_lrc=fetch_librelyrics(song.get('url'),job/'spotify_librelyrics.lrc',cfg)
   sync=None
   if ytlrc:print('Usable YouTube LRC found; Spotify↔YouTube synchronization skipped.')
   elif spotify_lrc:print('No YouTube LRC; synchronizing whole-song energy highs/lows ...');sync=synchronize(video,spotify_audio);print(f"Offset={sync['offset_seconds']:.3f}s confidence={sync['confidence']:.3f}")
   else:print('No YouTube or Spotify LRC; hook analysis will use audio only.')
   hook=detect(video,job,cfg,youtube_lrc=ytlrc,spotify_lrc=spotify_lrc,sync=sync);print(f"Hook {hook['start']:.3f}s → {hook['end']:.3f}s ({hook['duration']:.3f}s); lyrics={hook['lyrics_source']}")
   out=Path(cfg['reels_dir'])/f'{serial:04d}.mp4';jsonpath=out.with_suffix('.json')
   render_lrc=None
   if ytlrc:
    render_lrc=ytlrc
   elif spotify_lrc and sync:
    # Convert Spotify timestamps to the YouTube timeline before overlay.
    # synchronize() defines: YouTube time = Spotify time + offset.
    off=float(sync.get('offset_seconds',0)); mapped=[{'time':max(0,x['time']+off),'text':x['text']} for x in parse_lrc(spotify_lrc)]; render_lrc=mapped
   render_result=render(video,hook['start'],hook['end'],out,cfg,lyrics=render_lrc);final_probe=probe(out)
   # Canonical Spotify song is intentionally made only after reel rendering/probing.
   canonical=make_canonical(spotify_audio,artwork,spotify_lrc,cfg['songs_dir'],serial)
   if not (out.is_file() and jsonpath.parent.exists() and canonical.is_file()):raise RuntimeError('Permanent output validation failed.')
   metadata={'schema_version':'5.0','serial':serial,'status':'FINISHED','timestamps':{'started_at':utc(),'finished_at':utc()},'playlist':original,'youtube':{'selected':selected,'search_results':results,'ranking':ranked,'metadata':ytmeta,'ffprobe':source_probe,'lrc':ytlrcmeta},'spotify':{'selected':song,'query':spq,'search_results':sres,'ranking':sranked,'source_audio':str(spotify_audio),'spotdl_source_url':song.get('download_url'),'artwork':str(artwork) if artwork else None,'librelyrics_lrc':str(spotify_lrc) if spotify_lrc else None,'canonical_lrc_source':'librelyrics'},'synchronization':sync,'hook':hook,'render':render_result,'files':{'reel':str(out),'json':str(jsonpath),'song':str(canonical),'reel_sha256':sha(out),'song_sha256':sha(canonical)},'validation':{'reel_probe':final_probe,'reel_exists':out.is_file(),'song_exists':canonical.is_file()},'runtime':{'python':platform.python_version(),'platform':platform.platform()},'config_snapshot':cfg}
   tmp=jsonpath.with_name(jsonpath.name+'.writing');tmp.write_text(json.dumps(metadata,ensure_ascii=False,indent=2,default=str),encoding='utf-8');tmp.replace(jsonpath)
   sdb.insert({'serial':serial,'song_key':skey,'title':song.get('name'),'artists':json.dumps(song.get('artists') or [],ensure_ascii=False),'album':song.get('album_name') or song.get('album'),'spotify_url':song.get('url'),'spotify_track_id':song.get('song_id'),'youtube_video_id':selected['id'],'youtube_url':selected['url'],'spotify_source_file':str(spotify_audio),'spotdl_source_url':song.get('download_url'),'canonical_file':str(canonical),'youtube_title':selected['title'],'artwork_file':str(artwork) if artwork else None,'lrc_file':str(spotify_lrc) if spotify_lrc else None,'lrc_source':'librelyrics' if spotify_lrc else None,'lrc_language':None,'lrc_selection_priority':'spotify_canonical' if spotify_lrc else None,'sync_json':json.dumps(sync or {}),'hook_json':json.dumps(hook),'metadata_json':json.dumps(metadata)})
   rdb.finish(serial,metadata,out,jsonpath);pdb.set_finished(pid,entry['video_id'],serial)
   # Final database/file validation before cleanup.
   reel_ok=bool(rdb.cx.execute("SELECT 1 FROM reels WHERE serial=? AND status='FINISHED'",(serial,)).fetchone())
   song_ok=bool(sdb.cx.execute("SELECT 1 FROM songs WHERE serial=?",(serial,)).fetchone())
   playlist_ok=bool(pdb.cx.execute("SELECT 1 FROM playlist_entries WHERE playlist_id=? AND video_id=? AND status='FINISHED'",(pid,entry['video_id'])).fetchone())
   if not (reel_ok and song_ok and playlist_ok): raise RuntimeError('Final database validation failed.')
   clean(job);print(f'\nFINISHED: {out}\nSONG: {canonical}')
  except KeyboardInterrupt:
   if serial is not None:
    rdb.delete_job(serial); sdb.delete_serial(serial)
   for artifact in (out,jsonpath,canonical):
    if artifact:
     Path(artifact).unlink(missing_ok=True)
   clean(job);pdb.reset(pid,entry['video_id']);print('\nCancelled: current job deleted, playlist reset to YET_TO_START, serial permanently consumed.')
  except Exception as e:
   if serial is not None:
    rdb.delete_job(serial); sdb.delete_serial(serial)
   for artifact in (out,jsonpath,canonical):
    if artifact:
     Path(artifact).unlink(missing_ok=True)
   clean(job);pdb.reset(pid,entry['video_id']);print(f'\nERROR: {e}\nCurrent job deleted and playlist reset to YET_TO_START.')
if __name__=='__main__':main()
