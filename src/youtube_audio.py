from __future__ import annotations
import json
from pathlib import Path
from .utils import Phase3Error, run_cmd, sha256_file
class YouTubeAudioDownloader:
    def __init__(self,cfg,work_dir,logger): self.cfg=cfg; self.work=work_dir; self.logger=logger
    def download(self,video_id:str)->Path:
        outdir=self.work/'youtube'; outdir.mkdir(parents=True,exist_ok=True); out=outdir/'full_video_audio.m4a'
        if out.exists() and out.stat().st_size>10000: return out
        url=f'https://www.youtube.com/watch?v={video_id}'; yt=self.cfg.get('video.yt_dlp_binary','yt-dlp'); tmpl=str(outdir/'full_video_audio.%(ext)s')
        try:
            run_cmd([yt,'--no-playlist','-f',self.cfg.get('video.audio_format','bestaudio/best'),'-o',tmpl,url],timeout=float(self.cfg.get('video.download_timeout_seconds',600)))
        except Exception as e: raise Phase3Error('YOUTUBE_AUDIO_DOWNLOAD_FAILED',str(e))
        candidates=list(outdir.glob('full_video_audio.*'))
        candidates=[p for p in candidates if p.name!='full_video_audio.m4a']
        if not candidates: raise Phase3Error('YOUTUBE_AUDIO_DOWNLOAD_FAILED','No audio file produced')
        src=candidates[0]
        if src.suffix.lower()!='.m4a':
            run_cmd(['ffmpeg','-y','-v','error','-i',str(src),'-c:a','aac','-b:a','192k',str(out)])
            src.unlink(missing_ok=True)
        else: src.replace(out)
        return out
