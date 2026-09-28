from __future__ import annotations
from pathlib import Path
from .font_manager import ensure_telugu_font
from .ass_generator import ASSGenerator, clean_lrc_text
from .utils import json_dump, sha256_file

class LyricRenderer:
    def __init__(self,cfg,work_dir,logger): self.cfg=cfg; self.work=Path(work_dir); self.logger=logger
    def render(self,words,lrc_lines,reel_start_ms,reel_end_ms)->tuple[Path,dict]:
        font=ensure_telugu_font(self.cfg.fonts_dir,self.cfg.get('lyrics.font_filename','BalooTammudu2-ExtraBold.ttf'),self.cfg.get('lyrics.font_path'))
        ass=ASSGenerator(self.cfg,self.work,self.logger).generate(lrc_lines,words,reel_start_ms,reel_end_ms,font,None)
        selected=[]
        for i,line in enumerate(lrc_lines):
            if int(line.get('end_ms',0))<=reel_start_ms or int(line.get('start_ms',0))>=reel_end_ms: continue
            text=str(line.get('display_text') or clean_lrc_text(line.get('text','')))
            if text: selected.append({'line_index':i,'text':text,'start_ms':int(line['start_ms']),'end_ms':int(line.get('end_ms',line['start_ms']+4000))})
        plan={
            'enabled':True,
            'source_text':'LRC line text',
            'timing_source':'LRC word timestamps when present; Phase 2 JSON word timing fallback',
            'font_path':str(font),
            'font_name':self.cfg.get('lyrics.font_name','Baloo Tammudu 2 ExtraBold'),
            'font_sha256':sha256_file(font) if font.exists() else None,
            'display_mode':'one_lrc_line_at_a_time',
            'current_word_highlighted':True,
            'line_count':len(selected),
            'lines':selected,
            'center_x':int(self.cfg.get('lyrics.center_x',540)),
            'center_y':int(self.cfg.get('lyrics.center_y',960)),
        }
        json_dump(self.work/'lyrics'/'lyric_render_plan.json',plan)
        return ass,plan
