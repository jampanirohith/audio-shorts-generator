import json,shutil,argparse
from pathlib import Path
from modules.db import DB
from modules.youtube import playlist,search,choose,download,info,metadata_clues,download_original_subtitles
from modules.hooks import detect
from modules.video import make_ass,render

def process(e,db,cfg):
 s=e['serial']; db.upsert(e); row=db.get(s)
 print(f'\n{"="*72}')
 print(f'PLAYLIST ENTRY [{s}]')
 print(f'Original song: {e.get("title","")}')
 print(f'{"="*72}', flush=True)
 if row['status']=='DONE':
  print('Already DONE in database; skipping.', flush=True)
  return 'done'
 temp=Path(cfg['temp_dir']); temp.mkdir(parents=True,exist_ok=True)
 try:
  if not cfg['automation'].get('auto_continue',True):
   x=input('ENTER process, s=skip, q=quit: ').strip().lower()
   if x=='q': return 'quit'
   if x=='s': db.save(s,status='SKIPPED'); return 'skip'
  results=search(e['title'],cfg.get('top_youtube_results',10)); sel=choose(results,e['title'],cfg)
  if sel in ('skip','quit'): return sel
  if db.selected_exists(sel['id']): db.save(s,sel=sel,status='SKIPPED',error='selected video already completed'); return 'skip'
  db.save(s,sel=sel,status='PROCESSING'); yfile=download(sel['url'],temp); inf=info(sel['url']); sub=download_original_subtitles(sel['url'],temp,inf) if cfg.get('subtitles',{}).get('enabled',True) else None
  hook=detect(yfile,temp,cfg); ass=make_ass(sub,hook['start'],hook['end'],temp/'subtitles.ass',cfg) if sub else None
  out=Path(cfg['reels_finished_dir']); out.mkdir(parents=True,exist_ok=True); final=out/f"{s:04d}_{sel['id']}_reel.mp4"
  render(yfile,hook['start'],hook['end'],ass,final,cfg)
  metadata={'serial':s,'original_playlist_song':e,'selected_youtube_video':sel,'youtube_metadata':metadata_clues(inf),'hook':hook,'subtitle_file_found':bool(sub),'final_path':str(final)}
  db.save(s,metadata=metadata,final=final,status='DONE'); db.event(s,'DONE',str(final)); shutil.rmtree(temp,ignore_errors=True); print('DONE:',final); return 'done'
 except Exception as ex:
  db.save(s,status='FAILED',error=str(ex)); raise

def main():
 p=argparse.ArgumentParser(); p.add_argument('--retry',type=int); p.add_argument('--reset',type=int); a=p.parse_args()
 cfg=json.loads(Path('config.json').read_text(encoding='utf-8')); Path(cfg['temp_dir']).mkdir(parents=True,exist_ok=True); Path(cfg['reels_finished_dir']).mkdir(parents=True,exist_ok=True)
 db=DB(cfg['db_path']); entries=playlist(cfg['playlist_url'])
 if a.reset: db.reset(a.reset)
 for e in entries:
  if a.retry and e['serial']!=a.retry: continue
  r=process(e,db,cfg)
  if r=='quit': break
if __name__=='__main__': main()
