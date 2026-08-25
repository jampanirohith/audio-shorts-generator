import json, os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load_config():
    cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
    for k in ('temp_dir','songs_final_dir','reels_finished_dir','state_db'):
        p=ROOT/cfg[k]
        p.parent.mkdir(parents=True,exist_ok=True)
        if k!='state_db': p.mkdir(parents=True,exist_ok=True)
    cfg['root']=str(ROOT)
    cfg['ffmpeg']=os.getenv('FFMPEG_EXE','ffmpeg')
    cfg['fpcalc']=os.getenv('FP_CALC_EXE','fpcalc')
    cfg['youtube_cookie_file']=os.getenv('YOUTUBE_COOKIE_FILE','')
    return cfg
