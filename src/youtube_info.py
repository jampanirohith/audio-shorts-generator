from __future__ import annotations
import json
from pathlib import Path
from .utils import Phase3Error, run_cmd
class YouTubeInfo:
    def __init__(self,cfg,work_dir,logger): self.cfg=cfg; self.work=work_dir; self.logger=logger
    def get(self,video_id:str)->dict:
        url=f'https://www.youtube.com/watch?v={video_id}'
        try:
            p=run_cmd([self.cfg.get('video.yt_dlp_binary','yt-dlp'),'--dump-single-json','--no-warnings','--skip-download',url],timeout=float(self.cfg.get('video.metadata_timeout_seconds',120)))
        except Exception as e: raise Phase3Error('YOUTUBE_VIDEO_UNAVAILABLE',str(e))
        try: data=json.loads(p.stdout)
        except Exception: raise Phase3Error('YOUTUBE_VIDEO_UNAVAILABLE','yt-dlp returned invalid JSON')
        out={'video_id':video_id,'url':url,'title':data.get('title'),'duration_ms':int(round(float(data.get('duration') or 0)*1000)),'channel':data.get('channel'),'uploader':data.get('uploader'),'webpage_url':data.get('webpage_url') or url,'raw':data}
        (self.work/'youtube').mkdir(parents=True,exist_ok=True); (self.work/'youtube'/'metadata.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
        return out
