import json, subprocess

def validate_video(path,cfg):
    ffprobe=cfg['ffmpeg'].replace('ffmpeg','ffprobe')
    p=subprocess.run([ffprobe,'-v','error','-show_entries','format=duration:stream=codec_type,width,height','-of','json',str(path)],capture_output=True,text=True)
    if p.returncode: return {'valid':False,'reason':'ffprobe failed'}
    try:
        d=json.loads(p.stdout); dur=float(d['format']['duration']); streams=d.get('streams',[]); hv=any(s.get('codec_type')=='video' for s in streams); ha=any(s.get('codec_type')=='audio' for s in streams)
        if not hv or not ha or dur<1:return {'valid':False,'reason':'missing stream or duration'}
        return {'valid':True,'duration':dur,'streams':streams}
    except Exception as e:return {'valid':False,'reason':str(e)}
