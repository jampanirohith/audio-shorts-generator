from __future__ import annotations
from pathlib import Path
import json
from .utils import now_iso, json_dump, stable_json_hash, sha256_file

class OutputJSONBuilder:
    def __init__(self,cfg,work_dir,logger): self.cfg=cfg; self.work=work_dir; self.logger=logger
    def build(self,source,processing,hook,video_source,video_match,video_render,audio_8d,lyrics,validation,errors=None):
        data={
            'schema_version':1,'phase3_pipeline_version':'1.0.13','status':'finished' if validation.get('overall') else 'needs_review',
            'quality_status':'good' if validation.get('overall') else 'needs_review','generated_at':now_iso(),
            'source':source,'processing':processing,'hook_selection':hook,'video_source':video_source,'video_match':video_match,
            'video_render':video_render,'audio_8d':audio_8d,'lyrics':lyrics,'output':{},'validation':validation,'errors':errors or []
        }
        return data
    def write(self,data,path:Path,mp4_path:Path|None=None)->dict:
        if mp4_path and mp4_path.exists():
            data.setdefault('output',{})['reel_mp4']=str(mp4_path)
            data['output']['reel_mp4_sha256']=sha256_file(mp4_path)
            data['output']['file_size_bytes']=mp4_path.stat().st_size
        # Self hash is defined over the canonical JSON with this field null to avoid circularity.
        data.setdefault('output',{})['reel_json_sha256']=None
        canonical=json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
        self_hash=__import__('hashlib').sha256(canonical).hexdigest()
        data['output']['reel_json_sha256']=self_hash
        json_dump(path,data)
        return data
