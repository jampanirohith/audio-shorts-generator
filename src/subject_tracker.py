from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import cv2, numpy as np, json, math

@dataclass
class Detection:
    bbox:tuple[float,float,float,float]
    confidence:float
    kind:str='face'

class FaceDetector:
    def __init__(self,conf=0.5):
        self.conf=conf; self.mp=None; self.detector=None; self.pose=None; self.haar=None
        try:
            import mediapipe as mp
            self.mp=mp
            if hasattr(mp,'solutions'):
                self.detector=mp.solutions.face_detection.FaceDetection(model_selection=0,min_detection_confidence=conf)
                self.pose=mp.solutions.pose.Pose(static_image_mode=False,model_complexity=0,min_detection_confidence=0.4,min_tracking_confidence=0.4)
        except Exception:
            self.haar=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
    def detect(self,frame)->list[Detection]:
        h,w=frame.shape[:2]; out=[]
        if self.detector is not None:
            rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB); r=self.detector.process(rgb)
            for d in (r.detections or []):
                bb=d.location_data.relative_bounding_box
                x=max(0,bb.xmin*w); y=max(0,bb.ymin*h); bw=max(1,bb.width*w); bh=max(1,bb.height*h)
                out.append(Detection((x,y,bw,bh),float(d.score[0]),'face'))
        elif self.haar is not None:
            gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY); boxes=self.haar.detectMultiScale(gray,1.1,5,minSize=(50,50))
            out=[Detection((float(x),float(y),float(bw),float(bh)),0.55,'face') for x,y,bw,bh in boxes]
        if not out and self.pose is not None:
            rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB); p=self.pose.process(rgb)
            if p.pose_landmarks:
                xs=[lm.x*w for lm in p.pose_landmarks.landmark if lm.visibility>0.3]; ys=[lm.y*h for lm in p.pose_landmarks.landmark if lm.visibility>0.3]
                if xs and ys:
                    x0=max(0,min(xs)-0.08*w); y0=max(0,min(ys)-0.08*h); x1=min(w,max(xs)+0.08*w); y1=min(h,max(ys)+0.08*h)
                    out.append(Detection((x0,y0,x1-x0,y1-y0),0.5,'pose'))
        return out
    def close(self):
        for x in (self.detector,self.pose):
            try: x.close()
            except Exception: pass

@dataclass
class Track:
    track_id:int; bbox:tuple[float,float,float,float]; confidence:float; kind:str; last_seen:int; hits:int=1; misses:int=0; vx:float=0; vy:float=0
    def center(self): return (self.bbox[0]+self.bbox[2]/2,self.bbox[1]+self.bbox[3]/2)

class MultiPersonTracker:
    def __init__(self,conf=0.5,max_distance=220,max_misses=15): self.conf=conf; self.max_distance=max_distance; self.max_misses=max_misses; self.tracks={}; self.next_id=1
    @staticmethod
    def iou(a,b):
        ax,ay,aw,ah=a; bx,by,bw,bh=b; x1=max(ax,bx); y1=max(ay,by); x2=min(ax+aw,bx+bw); y2=min(ay+ah,by+bh); inter=max(0,x2-x1)*max(0,y2-y1); ua=aw*ah+bw*bh-inter; return inter/ua if ua>0 else 0
    def update(self,dets,frame_index):
        assigned=set(); result=[]
        for tid,t in list(self.tracks.items()):
            tc=t.center(); best=None; bestscore=-1
            for i,d in enumerate(dets):
                if i in assigned: continue
                dc=(d.bbox[0]+d.bbox[2]/2,d.bbox[1]+d.bbox[3]/2); dist=math.hypot(dc[0]-tc[0],dc[1]-tc[1]); iou=self.iou(t.bbox,d.bbox)
                score=iou+max(0,1-dist/self.max_distance)*0.5+(0.15 if d.kind==t.kind else 0)
                if dist<=self.max_distance and score>bestscore: best=(i,d,dc); bestscore=score
            if best:
                i,d,dc=best; assigned.add(i); old=t.center(); t.vx=0.6*t.vx+0.4*(dc[0]-old[0]); t.vy=0.6*t.vy+0.4*(dc[1]-old[1]); t.bbox=d.bbox; t.confidence=0.7*t.confidence+0.3*d.confidence; t.kind=d.kind; t.last_seen=frame_index; t.hits+=1; t.misses=0
            else: t.misses+=1
            if t.misses>self.max_misses: del self.tracks[tid]
        for i,d in enumerate(dets):
            if i not in assigned:
                self.tracks[self.next_id]=Track(self.next_id,d.bbox,d.confidence,d.kind,frame_index); self.next_id+=1
        result=list(self.tracks.values()); return result

def detect_shots(video_path:Path, sample_every:int=15, threshold:float=0.55)->list[tuple[int,int]]:
    cap=cv2.VideoCapture(str(video_path)); fps=cap.get(cv2.CAP_PROP_FPS) or 25; total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0); prev=None; cuts=[0]
    i=0
    while True:
        ok,frame=cap.read();
        if not ok: break
        if i%sample_every==0:
            small=cv2.resize(frame,(64,36)); hsv=cv2.cvtColor(small,cv2.COLOR_BGR2HSV); hist=cv2.calcHist([hsv],[0,1],None,[16,16],[0,180,0,256]); cv2.normalize(hist,hist)
            if prev is not None:
                d=float(cv2.compareHist(prev,hist,cv2.HISTCMP_BHATTACHARYYA))
                if d>threshold: cuts.append(i)
            prev=hist
        i+=1
    cap.release(); cuts=sorted(set(cuts+[total])); shots=[]
    for a,b in zip(cuts[:-1],cuts[1:]): shots.append((int(a),int(b)))
    return shots
