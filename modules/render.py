import re, subprocess, json
from pathlib import Path

def parse_lrc(path):
    if not path or not Path(path).exists(): return []
    rx=re.compile(r'\[(\d+):(\d+(?:\.\d+)?)\](.*)'); out=[]
    for line in Path(path).read_text(encoding='utf-8',errors='ignore').splitlines():
        m=rx.match(line.strip())
        if m and m.group(3).strip(): out.append((int(m.group(1))*60+float(m.group(2)),m.group(3).strip()))
    return sorted(out)
def ass_time(x):
    cs=int(round(max(0,x)*100)); h,r=divmod(cs,360000); m,r=divmod(r,6000); s,c=divmod(r,100); return f'{h}:{m:02d}:{s:02d}.{c:02d}'
def esc(t): return t.replace('\\',r'\\').replace('{',r'\{').replace('}',r'\}')
def make_ass(lrc,start,end,ass,cfg):
    rows=parse_lrc(lrc); ev=[]
    for i,(t,txt) in enumerate(rows):
        if not(start<=t<end): continue
        nxt=next((u for u,_ in rows[i+1:] if u>t),end); ev.append((t-start,min(nxt,end)-start,txt))
    header=f'''[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Lyrics,{cfg["subtitle_font"]},{cfg["subtitle_font_size"]},&H00FFFFFF,&H00FFFFFF,&H00151515,&H90000000,1,0,0,0,100,100,0,0,1,{cfg["subtitle_outline"]},2,5,60,60,0,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''
    body='\n'.join(f'Dialogue: 0,{ass_time(s)},{ass_time(e)},Lyrics,,0,0,0,,{esc(t)}' for s,e,t in ev)
    Path(ass).write_text(header+body+'\n',encoding='utf-8'); return ass

def crop_with_effects(source,start,duration,out,ass,cfg):
    ap=str(ass).replace('\\','/').replace(':',r'\:')
    # Slight lift in shadows/brightness, gentle contrast/saturation, vignette.
    eq=f"eq=brightness={cfg['cinematic_brightness']}:contrast={cfg['cinematic_contrast']}:saturation={cfg['cinematic_saturation']},vignette=PI/5:{cfg['cinematic_vignette']},subtitles='{ap}'"
    cmd=[cfg['ffmpeg'],'-y','-ss',f'{start:.3f}','-i',str(source),'-t',f'{duration:.3f}','-vf',eq,'-map','0:v:0','-map','0:a?','-c:v','libx264','-preset',cfg['video_preset'],'-crf',str(cfg['video_crf']),'-c:a','aac','-b:a','320k','-movflags','+faststart',str(out)]
    p=subprocess.run(cmd,capture_output=True,text=True)
    if p.returncode: Path(str(out)+'.log').write_text((p.stdout or '')+'\n'+(p.stderr or ''),encoding='utf-8'); raise RuntimeError('Hook render failed.')

def make_vertical(source,cropped,out,cfg):
    # No crop: 16:9 source is kept intact in the center. A blurred enlarged copy fills the canvas.
    filt="[0:v]scale=-2:1920,crop=1080:1920,boxblur=20:1[bg];[0:v]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p"
    cmd=[cfg['ffmpeg'],'-y','-i',str(cropped),'-filter_complex',filt,'-map','0:a?','-map','0:v:0','-c:v','libx264','-preset',cfg['video_preset'],'-crf',str(cfg['video_crf']),'-c:a','aac','-b:a','320k','-movflags','+faststart',str(out)]
    # Correct mapping for filtered video.
    cmd=[cfg['ffmpeg'],'-y','-i',str(cropped),'-filter_complex',filt,'-map','[vout]','-map','0:a?','-c:v','libx264','-preset',cfg['video_preset'],'-crf',str(cfg['video_crf']),'-c:a','aac','-b:a','320k','-movflags','+faststart',str(out)]
    filt="[0:v]scale=-2:1920,crop=1080:1920,boxblur=20:1[bg];[0:v]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[vout]"
    cmd[cmd.index('-filter_complex')+1]=filt
    p=subprocess.run(cmd,capture_output=True,text=True)
    if p.returncode: Path(str(out)+'.log').write_text((p.stdout or '')+'\n'+(p.stderr or ''),encoding='utf-8'); raise RuntimeError('9:16 render failed.')

def render_three(yt_file,lrc,alignment,hooks,temp_dir,cfg):
    out=[]; start_offset=alignment['offset_seconds']
    for h in hooks:
        idx=h['index']; ass=Path(temp_dir)/f'hook_{idx}.ass'; make_ass(lrc,h['spotify_start'],h['spotify_end'],ass,cfg)
        # h.start/end are YouTube coordinates; subtitles use Spotify coordinates.
        cropped=Path(temp_dir)/f'reel_{idx}_cropped.mp4'; start=h['start']; dur=h['duration']; raw=Path(temp_dir)/f'reel_{idx}_raw.mp4'
        # Raw crop with no lyric/effect; this is the original video audio.
        p=subprocess.run([cfg['ffmpeg'],'-y','-ss',f'{start:.3f}','-i',str(yt_file),'-t',f'{dur:.3f}','-map','0:v:0','-map','0:a?','-c','copy',str(raw)],capture_output=True,text=True)
        if p.returncode:
            p=subprocess.run([cfg['ffmpeg'],'-y','-ss',f'{start:.3f}','-i',str(yt_file),'-t',f'{dur:.3f}','-c:v','libx264','-crf',str(cfg['video_crf']),'-c:a','aac','-b:a','320k',str(raw)],capture_output=True,text=True)
            if p.returncode: raise RuntimeError('Could not crop YouTube video.')
        vertical=Path(temp_dir)/f'reel_{idx}_vertical.mp4'; make_vertical(raw,raw,vertical,cfg)
        out.append({'index':idx,'start':start,'end':start+dur,'duration':dur,'raw':str(raw),'vertical':str(vertical),'ass':str(ass)})
    return out

def finalize_choice(source_vertical,source_crop,ass,final_path,cfg):
    # Apply cinematic effect and lyrics to the vertical output, preserving the centered original.
    ap=str(ass).replace('\\','/').replace(':',r'\:')
    vf=f"eq=brightness={cfg['cinematic_brightness']}:contrast={cfg['cinematic_contrast']}:saturation={cfg['cinematic_saturation']},vignette=PI/5:{cfg['cinematic_vignette']},subtitles='{ap}'"
    p=subprocess.run([cfg['ffmpeg'],'-y','-i',str(source_vertical),'-vf',vf,'-map','0:v:0','-map','0:a?','-c:v','libx264','-preset',cfg['video_preset'],'-crf',str(cfg['video_crf']),'-c:a','aac','-b:a','320k','-movflags','+faststart',str(final_path)],capture_output=True,text=True)
    if p.returncode: Path(str(final_path)+'.log').write_text((p.stdout or '')+'\n'+(p.stderr or ''),encoding='utf-8'); raise RuntimeError('Final reel render failed.')
