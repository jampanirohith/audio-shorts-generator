import json, shutil, subprocess, tempfile
from pathlib import Path


def req(name):
    if shutil.which(name) is None: raise RuntimeError(f'{name} was not found on PATH.')


def probe(path):
    req('ffprobe'); p=subprocess.run(['ffprobe','-v','error','-print_format','json','-show_format','-show_streams',str(path)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
    if p.returncode: raise RuntimeError(p.stdout[-8000:] or 'ffprobe failed')
    return json.loads(p.stdout)


def nvenc_available():
    try:return 'h264_nvenc' in subprocess.run(['ffmpeg','-hide_banner','-encoders'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace').stdout
    except Exception:return False


def _ffpath(p):
    return str(Path(p).resolve()).replace('\\','/').replace(':','\\:').replace("'","\\'")


def _font(cfg):
    p=Path(cfg.get('lyrics_fontfile','fonts/NotoSerifTelugu.ttf'))
    if not p.is_file(): raise RuntimeError(f"Configured lyric font was not found: {p.resolve()}")
    return p


def _escape(v):
    return str(v).replace('\\','\\\\').replace(':','\\:').replace("'","\\'").replace('%','\\%').replace('[','\\[').replace(']','\\]')


def _wrap(text,max_chars):
    max_chars=int(max_chars)
    raw_lines=str(text).replace('\x00','').replace('\r','').split('\n')
    wrapped=[]
    for raw in raw_lines:
        line=' '.join(raw.split())
        if not line: continue
        if max_chars<=0 or len(line)<=max_chars:
            wrapped.append(line); continue
        words=line.split()
        if len(words)==1:
            mid=max(1,len(line)//2); wrapped.extend([line[:mid],line[mid:]])
            continue
        current=[]; current_len=0
        for word in words:
            proposed=len(word) if not current else current_len+1+len(word)
            if current and proposed>max_chars:
                wrapped.append(' '.join(current)); current=[word]; current_len=len(word)
            else:
                current.append(word); current_len=proposed
        if current: wrapped.append(' '.join(current))
    return '\n'.join(wrapped)

def _lyric_filters(lines,duration,cfg,tmpdir):
    if not lines:return None,0
    font=_font(cfg); max_chars=int(cfg.get('lyrics_max_chars_per_line',34)); size=int(cfg.get('lyrics_font_size',52)); border=int(cfg.get('lyrics_border_width',3)); opacity=max(0,min(1,float(cfg.get('lyrics_opacity',1))))
    merge_tol=max(0.0,float(cfg.get('lyrics_merge_timestamp_tolerance_seconds',0.15)))
    max_display=max(0.5,float(cfg.get('lyrics_max_display_seconds',6.0)))

    # Group LRC entries that start at essentially the same time. This is common
    # with two vocal lines encoded at one timestamp. Rendering them as separate
    # drawtext filters would place both strings on top of each other. A group is
    # rendered as one multiline text block instead.
    groups=[]
    for raw in lines:
        start=float(raw['time']); text=' '.join(str(raw.get('text','')).replace('\x00','').split())
        if not text or start>=duration: continue
        if groups and abs(start-groups[-1]['time']) <= merge_tol:
            groups[-1]['texts'].append(text)
        else:
            groups.append({'time':start,'texts':[text]})

    filters=[]; count=0
    for i,g in enumerate(groups):
        start=max(0,min(duration,g['time']))
        next_start=groups[i+1]['time'] if i+1<len(groups) else duration
        # Do not leave an old lyric displayed for an excessively long silent gap.
        # It remains visible long enough to be readable, then disappears until
        # the next timestamp.
        end=min(duration,next_start,start+max_display)
        if end <= start: continue
        text=_wrap('\n'.join(g['texts']),max_chars)
        f=tmpdir/f'lyric_{i:04d}.txt';f.write_text(text,encoding='utf-8-sig')

        # drawtext's line_spacing is measured in pixels added between lines.
        # Noto/TrueType font metrics already contain a substantial line box, so
        # a small positive value can still look very loose. Allow negative
        # spacing and make the configured value explicit in the generated
        # filter. This makes the config control the *actual* extra spacing.
        line_spacing=int(cfg.get('lyrics_line_spacing',-12))

        # Fade each lyric block in/out. If a lyric interval is shorter than the
        # requested combined fade duration, split the interval so the two fades
        # never overlap. A zero duration disables that side's fade.
        interval=max(0.0,end-start)
        requested_fade_in=max(0.0,float(cfg.get('lyrics_fade_in_seconds',0.20)))
        requested_fade_out=max(0.0,float(cfg.get('lyrics_fade_out_seconds',0.20)))
        fade_in=min(requested_fade_in,interval/2.0)
        fade_out=min(requested_fade_out,interval/2.0)

        alpha_expr='1'
        if fade_in>0 or fade_out>0:
            if fade_in>0 and fade_out>0:
                alpha_expr=(
                    f"if(lt(t\\,{start+fade_in:.3f})\\,(t-{start:.3f})/{fade_in:.3f}\\,"
                    f"if(gt(t\\,{end-fade_out:.3f})\\,({end:.3f}-t)/{fade_out:.3f}\\,1))"
                )
            elif fade_in>0:
                alpha_expr=f"if(lt(t\\,{start+fade_in:.3f})\\,(t-{start:.3f})/{fade_in:.3f}\\,1)"
            else:
                alpha_expr=f"if(gt(t\\,{end-fade_out:.3f})\\,({end:.3f}-t)/{fade_out:.3f}\\,1)"

        filters.append("drawtext="+":".join([
            f"fontfile='{_ffpath(font)}'",f"textfile='{_ffpath(f)}'",
            f"fontcolor={_escape(str(cfg.get('lyrics_font_color','white')))}@{opacity:.3f}",
            f"bordercolor={_escape(str(cfg.get('lyrics_border_color','black')))}",f"borderw={border}",f"fontsize={size}",
            f"line_spacing={line_spacing}","text_align=center",
            "x=(w-text_w)/2","y=(h-text_h)/2",f"alpha='{alpha_expr}'",
            f"enable='between(t,{start:.3f},{end:.3f})'"
        ]));count+=1
    return ','.join(filters),count

def render(video, youtube_start, duration, spotify_audio, spotify_start, out, cfg, lyrics=None):
    req('ffmpeg');out=Path(out);out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix('.rendering.mp4')
    w=int(cfg.get('video_width',1920));h=int(cfg.get('video_height',1080));fps=int(cfg.get('video_fps',30))
    lyric_tmp=Path(tempfile.mkdtemp(prefix=f'.{out.stem}_lyrics_',dir=str(out.parent)))
    try:
        base='crop=min(iw\\,ih*16/9):min(ih\\,iw*9/16):(iw-ow)/2:(ih-oh)/2,scale=%d:%d:flags=lanczos,setsar=1'%(w,h)
        if cfg.get('cinematic_enabled',True):
            base+=',eq=brightness=%s:contrast=%s:saturation=%s:gamma=%s'%(cfg.get('cinematic_brightness',0),cfg.get('cinematic_contrast',1.1),cfg.get('cinematic_saturation',1.03),cfg.get('cinematic_gamma',1.02))
            sharp=float(cfg.get('cinematic_sharpen',.3));base+=f',unsharp=5:5:{sharp}:5:5:0'
            base+=f',vignette=PI/{cfg.get("cinematic_vignette_divisor",7)}:eval=frame'
        lf,count=_lyric_filters(lyrics,float(duration),cfg,lyric_tmp) if lyrics else (None,0)
        if lf:base+=','+lf
        enc=['-c:v','h264_nvenc','-preset',cfg.get('nvenc_preset','p5'),'-cq',str(cfg.get('nvenc_cq',20)),'-b:v','0'] if cfg.get('video_encoder','auto').lower() in {'auto','gpu','nvenc'} and nvenc_available() else ['-c:v','libx264','-preset',cfg.get('cpu_preset','medium'),'-crf',str(cfg.get('video_crf',18))]
        cmd=['ffmpeg','-y','-hide_banner','-loglevel','error','-ss',f'{float(youtube_start):.3f}','-i',str(video),'-ss',f'{float(spotify_start):.3f}','-i',str(spotify_audio),'-t',f'{float(duration):.3f}','-filter:v',base,'-map','0:v:0','-map','1:a:0','-r',str(fps),*enc,'-pix_fmt','yuv420p','-c:a','aac','-b:a',cfg.get('audio_bitrate','192k'),'-shortest','-movflags','+faststart',str(tmp)]
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
        if p.returncode:raise RuntimeError(p.stdout[-12000:] or 'FFmpeg render failed')
        tmp.replace(out)
        return {'encoder':'h264_nvenc' if any(x=='h264_nvenc' for x in enc) else 'libx264','canvas':{'width':w,'height':h,'fps':fps,'aspect_ratio':'16:9'},'youtube_start':round(float(youtube_start),3),'spotify_start':round(float(spotify_start),3),'duration':round(float(duration),3),'lyrics_rendered':bool(lyrics),'lyrics_line_count':count,'lyrics_position':'center','audio_source':'spotify','video_source':'youtube','command':cmd,'probe':probe(out)}
    finally:
        shutil.rmtree(lyric_tmp,ignore_errors=True)
