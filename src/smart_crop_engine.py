from __future__ import annotations
from pathlib import Path
import json, math
from .subject_tracker import FaceDetector, MultiPersonTracker, detect_shots
from .utils import json_dump, clamp

class SmartCropEngine:
    def __init__(self,cfg,work_dir,logger): self.cfg=cfg; self.work=work_dir; self.logger=logger
    def analyze(self,video_path:Path)->dict:
        import cv2, numpy as np
        cap=cv2.VideoCapture(str(video_path)); fps=cap.get(cv2.CAP_PROP_FPS) or 25; w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920); h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080); total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        det=FaceDetector(float(self.cfg.get('smart_crop.face_confidence_threshold',.5))); tracker=MultiPersonTracker(); tracks=[]; shot_ranges=detect_shots(video_path)
        shot_idx=0; next_cut=shot_ranges[0][1] if shot_ranges else total
        i=0; prev_track_ids=set()
        while i<total:
            ok,frame=cap.read()
            if not ok: break
            if i>next_cut:
                tracker=MultiPersonTracker(); shot_idx=min(shot_idx+1,len(shot_ranges)-1); next_cut=shot_ranges[shot_idx][1] if shot_ranges else total
            # sample at ~10fps for tracking, then interpolate during render.
            if i % max(1,int(round(fps/10)))==0:
                ds=det.detect(frame); ts=tracker.update(ds,i)
                visible=[]
                for t in ts:
                    cx,cy=t.center(); visible.append({'track_id':t.track_id,'x':cx,'y':cy,'w':t.bbox[2],'h':t.bbox[3],'confidence':t.confidence,'kind':t.kind,'frame':i,'time_ms':int(i/fps*1000),'misses':t.misses,'shot_index':shot_idx})
                tracks.extend(visible)
            i+=1
        cap.release(); det.close()
        # Build frame/sample path: choose most prominent persistent subject and avoid large jumps.
        byframe={}
        for rec in tracks: byframe[rec['frame']]=rec
        sample_frames=sorted(byframe)
        if sample_frames:
            # choose track with best weighted prominence/confidence; bias persistent tracks.
            scores={}
            for rec in tracks:
                scores[rec['track_id']]=scores.get(rec['track_id'],0)+rec['confidence']*(1+0.01*rec['w']*rec['h'])
            primary=max(scores,key=scores.get)
        else: primary=None
        path=[]
        for f in sample_frames:
            rec=next((r for r in tracks if r['frame']==f and (r['track_id']==primary)),None) or byframe[f]
            path.append(rec)
        # Interpolate to 10fps path; render module interpolates per frame.
        data={'fps':fps,'width':w,'height':h,'frame_count':total,'shots':shot_ranges,'primary_track_id':primary,'samples':path,'tracking_confidence_mean':(sum(x['confidence'] for x in tracks)/len(tracks) if tracks else 0),'subject_switches':len({x['track_id'] for x in path})-1 if path else 0}
        json_dump(self.work/'video'/'tracking.json',data); return data
