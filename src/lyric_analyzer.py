from __future__ import annotations
from collections import Counter,defaultdict
import re
from .utils import json_dump

def norm_tokens(words):
    out=[]
    for w in words:
        t=w.get('normalized') or w.get('text') or ''
        t=' '.join(str(t).strip().split())
        if t: out.append(t)
    return out

class LyricAnalyzer:
    def __init__(self,cfg,work_dir,logger): self.cfg=cfg; self.work=work_dir; self.logger=logger
    def analyze(self,words,lrc_lines):
        lines=defaultdict(list)
        for w in words: lines[w['line_index']].append(w)
        line_records=[]
        for idx,ws in sorted(lines.items()):
            text=' '.join(w['text'] for w in ws).strip();
            line_records.append({'line_index':idx,'start_ms':min(w['start_ms'] for w in ws),'end_ms':max(w['end_ms'] for w in ws),'text':text,'words':ws})
        gaps=[]
        if line_records:
            last=0
            for l in line_records:
                if l['start_ms']-last>800: gaps.append({'start_ms':last,'end_ms':l['start_ms'],'duration_ms':l['start_ms']-last})
                last=l['end_ms']
        durations=[max(1,w['end_ms']-w['start_ms']) for w in words]
        data={'word_count':len(words),'line_count':len(line_records),'lines':line_records,'lyric_free_gaps':gaps,
              'mean_word_duration_ms':sum(durations)/len(durations) if durations else 0,
              'mean_words_per_line':len(words)/max(1,len(line_records))}
        json_dump(self.work/'analysis'/'lyric_analysis.json',data)
        return data
