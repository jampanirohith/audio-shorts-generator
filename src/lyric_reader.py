from __future__ import annotations
import re, json
from pathlib import Path
from .utils import Phase3Error
from .package_validator import extract_word_records

_ANGLE_WORD_TS=re.compile(r'<(?P<t>\d{1,2}:\d{2}(?:\.\d{1,3})?)>')
_INLINE_BRACKET_TS=re.compile(r'\[(?P<t>\d{1,2}:\d{2}(?:[.:]\d{1,3})?)\]')
_LINE_TS=re.compile(r'\[(?P<t>\d{1,2}:\d{2}(?:[.:]\d{1,3})?)\]\s*(?P<text>.*)$')

def _t_ms(t):
    t=t.replace(':','.'); parts=t.split('.')
    if len(parts)==3: m,s,cs=parts
    else:
        # mm:ss.xx originally after replace => mm.ss.xx
        m,s,cs=(parts+[0,0])[:3]
    return int(m)*60000+int(s)*1000+int(str(cs).ljust(3,'0')[:3])

def parse_lrc(path:Path)->list[dict]:
    lines=[]; raw=path.read_text(encoding='utf-8-sig',errors='replace').splitlines()
    for line in raw:
        m=_LINE_TS.search(line)
        if not m: continue
        ts=_t_ms(m.group('t')); text=m.group('text').strip(); words=[]

        # Enhanced LRC in the supplied Phase 2 corpus uses inline [mm:ss.xx]
        # timestamps. The first line timestamp belongs to the first word; the
        # inline timestamps begin subsequent words.
        bracket=list(_INLINE_BRACKET_TS.finditer(text))
        if bracket:
            first_start=ts
            boundaries=[(b.start(),b.end(),_t_ms(b.group('t'))) for b in bracket]
            cursor=0; starts=[first_start]+[b[2] for b in boundaries]
            slices=[]
            for i,b in enumerate(boundaries):
                segment=text[cursor:b[0]].strip()
                slices.append(segment); cursor=b[1]
            slices.append(text[cursor:].strip())
            for i,segment in enumerate(slices):
                if not segment: continue
                start_ms=int(starts[i]); end_ms=int(starts[i+1]) if i+1<len(starts) else start_ms+400
                words.append({'text':segment,'start_ms':start_ms,'end_ms':max(start_ms+10,end_ms)})
        else:
            # Also accept <mm:ss.xx> enhanced-LRC syntax.
            angle=list(_ANGLE_WORD_TS.finditer(text))
            if angle:
                starts=[ts]+[_t_ms(a.group('t')) for a in angle]
                slices=[]; cursor=0
                for a in angle:
                    segment=text[cursor:a.start()].strip(); slices.append(segment); cursor=a.end()
                slices.append(text[cursor:].strip())
                for i,segment in enumerate(slices):
                    if not segment: continue
                    start_ms=int(starts[i]); end_ms=int(starts[i+1]) if i+1<len(starts) else start_ms+400
                    words.append({'text':segment,'start_ms':start_ms,'end_ms':max(start_ms+10,end_ms)})
            elif text:
                # Plain LRC line; canonical JSON word timing can fill this later.
                pass
        clean=' '.join(_INLINE_BRACKET_TS.sub('',text).split())
        clean=' '.join(_ANGLE_WORD_TS.sub('',clean).split())
        lines.append({'start_ms':ts,'text':text,'display_text':clean,'words':words})
    for i,l in enumerate(lines): l['end_ms']=lines[i+1]['start_ms'] if i+1<len(lines) else l['start_ms']+4000
    return lines


def load_canonical_words(json_data:dict,lrc_lines:list[dict])->list[dict]:
    words=extract_word_records(json_data)
    if not words: raise Phase3Error('WORD_TIMELINE_MISSING','No word-level JSON timing')
    out=[]
    for w in words:
        text=str(w.get('original') or w.get('text') or '').strip()
        if not text: continue
        out.append({'text':text,'normalized':str(w.get('normalized') or text),'start_ms':int(w['start_ms']),'end_ms':int(w['end_ms']),
                    'score':w.get('score'),'source':w.get('source'),'line_index':int(w.get('line_index',0)),'word_index':int(w.get('word_index',0))})
    return out
