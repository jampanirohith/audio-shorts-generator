import subprocess,re
from pathlib import Path

def _ts(x):
    h,m,s=x.strip().split(':'); return int(h)*3600+int(m)*60+float(s.replace(',','.'))

def make_ass(subtitle,start,end,out,cfg):
    if not subtitle or not Path(subtitle).exists(): return None
    rows=[]; lines=Path(subtitle).read_text(encoding='utf-8-sig',errors='ignore').splitlines(); i=0
    while i<len(lines):
        if '-->' in lines[i]:
            try:
                a,b=[x.strip().split(' ')[0] for x in lines[i].split('-->')]; t0,t1=_ts(a),_ts(b)
            except: i+=1; continue
            i+=1; txt=[]
            while i<len(lines) and lines[i].strip(): txt.append(re.sub(r'<[^>]+>','',lines[i])); i+=1
            text=' '.join(txt).strip()
            if text and t1>=start and t0<=end: rows.append((max(t0,start)-start,min(t1,end)-start,text))
        i+=1
    if not rows:return None
    font=cfg.get('subtitle_font','Veturi')
    head=f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,{font},{cfg.get('subtitle_font_size',62)},&H00FFFFFF,&H00FFFFFF,&H00101010,&H90000000,0,1,0,0,100,100,0,0,1,{cfg.get('subtitle_outline',3)},2,5,70,70,{cfg.get('subtitle_margin_v',170)},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    def at(t): return f"0:{int(t//60):02d}:{t%60:05.2f}"
    Path(out).write_text(head+'\n'.join(f'Dialogue: 0,{at(a)},{at(b)},Default,,0,0,0,,{{\\fad(120,120)}}{t}' for a,b,t in rows),encoding='utf-8')
    return Path(out)

def _nvenc():
    try:return 'h264_nvenc' in subprocess.run(['ffmpeg','-hide_banner','-encoders'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True).stdout
    except:return False

def render(video,start,end,ass,out,cfg):
    w,h=int(cfg['video_width']),int(cfg['video_height'])
    cw=float(cfg.get('source_crop_width',0.70))
    ch=float(cfg.get('source_crop_height',0.55))
    # Crop first. Preserve the crop's aspect ratio. Only scale down if needed
    # to fit the 9:16 canvas; never stretch it into a landscape frame.
    filt=(
        f'[0:v]crop=iw*{cw}:ih*{ch}:(iw-ow)/2:(ih-oh)/2,'
        f'scale=w=min(iw\\,{w}):h=min(ih\\,{h}):force_original_aspect_ratio=decrease:flags=lanczos,'
        f'setsar=1,eq=brightness={cfg.get("cinematic_brightness",.025)}:contrast={cfg.get("cinematic_contrast",1.08)}:saturation={cfg.get("cinematic_saturation",1.04)}[fg];'
        f'color=c=black:s={w}x{h}:r={cfg.get("video_fps",30)}[bg];'
        f'[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1[v]'
    )
    mapv='[v]'
    if ass:
      esc=str(Path(ass).resolve()).replace('\\','/').replace(':','\\:').replace("'","\\'")
      filt+=f";[v]subtitles=filename='{esc}':fontsdir=fonts[vout]"; mapv='[vout]'
    gpu=str(cfg.get('video_encoder','auto')).lower() in ('auto','gpu','nvenc') and _nvenc()
    enc=['-c:v','h264_nvenc','-preset',cfg.get('nvenc_preset','p5'),'-cq',str(cfg.get('nvenc_cq',20)),'-b:v','0'] if gpu else ['-c:v','libx264','-preset',cfg.get('cpu_preset','medium'),'-crf',str(cfg.get('video_crf',18))]
    cmd=['ffmpeg','-y','-hide_banner','-ss',str(start),'-i',str(video),'-t',str(end-start),'-filter_complex',filt,'-map',mapv,'-map','0:a?','-r',str(cfg.get('video_fps',30)),*enc,'-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(out)]
    print('\nFFmpeg rendering (live terminal output):',flush=True)
    print(f'  Crop: {cw:.2f} x {ch:.2f} of source',flush=True)
    print(f'  Canvas: {w}x{h} (9:16)',flush=True)
    print('  Cropped video: centered, aspect ratio preserved',flush=True)
    print('  Encoder:', 'NVENC/GPU' if gpu else 'libx264/CPU',flush=True)
    p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',bufsize=1)
    lines=[]
    if p.stdout:
      for line in p.stdout:
        line=line.rstrip('\r\n'); lines.append(line)
        if line: print(line,flush=True)
    code=p.wait()
    if code: raise RuntimeError('\n'.join(lines[-8000:]))
