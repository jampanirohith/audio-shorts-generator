from __future__ import annotations
from collections import defaultdict
from difflib import SequenceMatcher
from .utils import json_dump

class PhraseRepetition:
    def __init__(self,work_dir,logger): self.work=work_dir; self.logger=logger
    def analyze(self,words,lines):
        tokens=[w['normalized'] for w in words]
        clusters=[]
        # Exact n-gram recurrence, 2..5 words; keep meaningful repeated sequences.
        exact={}
        for n in range(2,6):
            for i in range(len(tokens)-n+1):
                phrase=tuple(tokens[i:i+n]); key=' '.join(phrase)
                if any(len(x)<=1 for x in phrase): continue
                exact.setdefault((n,key),[]).append(i)
        for (n,key),idxs in exact.items():
            if len(idxs)<2: continue
            occ=[{'word_index':i,'start_ms':words[i]['start_ms'],'end_ms':words[i+n-1]['end_ms']} for i in idxs]
            clusters.append({'cluster_id':f'exact_{n}_{len(clusters)}','canonical_phrase':key,'variants':[key], 'occurrence_count':len(occ),'occurrences':occ,'similarity_score':1.0,'n':n})
        # Full-line repetition.
        line_texts={l['line_index']:l['text'] for l in lines}
        inv=defaultdict(list)
        for idx,t in line_texts.items():
            if t.strip(): inv[' '.join(t.split())].append(idx)
        for t,ids in inv.items():
            if len(ids)>1:
                occ=[]
                for idx in ids:
                    line=next(l for l in lines if l['line_index']==idx); occ.append({'line_index':idx,'start_ms':line['start_ms'],'end_ms':line['end_ms']})
                clusters.append({'cluster_id':f'line_{len(clusters)}','canonical_phrase':t,'variants':[t],'occurrence_count':len(ids),'occurrences':occ,'similarity_score':1.0,'n':'line'})
        # Soft phrase similarity for lines (conservative threshold).
        seen=[]
        line_items=[(l['line_index'],l['text']) for l in lines if l['text'].strip()]
        for i,(ia,a) in enumerate(line_items):
            for ib,b in line_items[i+1:]:
                if a==b: continue
                r=SequenceMatcher(None,a,b).ratio()
                if r>=0.82 and min(len(a),len(b))>=8:
                    # merge with existing similar cluster or create pair
                    seen.append((ia,ib,r,a,b))
        for ia,ib,r,a,b in seen[:100]:
            clusters.append({'cluster_id':f'sim_{len(clusters)}','canonical_phrase':a,'variants':[a,b],'occurrence_count':2,'occurrences':[],'similarity_score':r,'n':'similar_line'})
        json_dump(self.work/'analysis'/'phrase_clusters.json',{'clusters':clusters})
        return clusters
