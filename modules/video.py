import json,shutil,subprocess
from pathlib import Path

def req(n):
 if shutil.which(n) is None: raise RuntimeError(f'{n} was not found on PATH.')
def probe(p):
 req('ffprobe');q=subprocess.run(['ffprobe','-v','error','-print_format','json','-show_format','-show_streams',str(p)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
 if q.returncode: raise RuntimeError(q.stdout[-6000:] or 'ffprobe failed')
 return json.loads(q.stdout)
def nvenc():
 try:return 'h264_nvenc' in subprocess.run(['ffmpeg','-hide_banner','-encoders'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace').stdout
 except:return False

def _ffmpeg_path(path):
 return str(Path(path).resolve()).replace('\\','/').replace(':','\\:').replace("'","\\'")

def _default_font_path():
 candidates=[Path('C:/Windows/Fonts/Nirmala.ttf'),Path('C:/Windows/Fonts/NirmalaUI.ttf'),Path('C:/Windows/Fonts/arial.ttf'),Path('C:/Windows/Fonts/segoeui.ttf')]
 for p in candidates:
  if p.is_file(): return str(p)
 return None

def _escape_filter_value(text):
 return str(text).replace('\\','\\\\').replace(':','\\:').replace("'","\\'").replace('%','\\%').replace('[','\\[').replace(']','\\]')

def _subtitle_filter(lines,hook_start,hook_end,width,height,font_path=None,font_size=52,temp_dir=None,cfg=None):
 """Render lyrics on the actual foreground video, not on the surrounding black canvas.

    Each lyric is a two-line-capable drawtext event. textfile= avoids punctuation escaping.
    All typography and placement is controlled by config.json.
    """
 cfg=cfg or {}
 font_path=font_path or _default_font_path()
 if not font_path or not Path(font_path).is_file():
  raise RuntimeError('No usable lyric font file found. Set lyrics_fontfile in config.json.')
 import tempfile
 root=Path(temp_dir) if temp_dir else Path(tempfile.mkdtemp(prefix='audio_shorts_lrc_'))
 root.mkdir(parents=True,exist_ok=True);created=[];parts=[]
 font_size=int(cfg.get('lyrics_font_size',font_size));font_color=str(cfg.get('lyrics_font_color','white'));border_color=str(cfg.get('lyrics_border_color','black'))
 border_w=int(cfg.get('lyrics_border_width',3));bold=bool(cfg.get('lyrics_bold',False));opacity=float(cfg.get('lyrics_opacity',1.0))
 # The lyric y position is relative to the foreground video. Default is lower-middle,
 # safely inside the video rather than in the black area around it.
 x_expr=str(cfg.get('lyrics_x','(w-text_w)/2'))
 y_expr=str(cfg.get('lyrics_y','h*0.68-text_h/2'))
 align=str(cfg.get('lyrics_alignment','center'))
 line_spacing=int(cfg.get('lyrics_line_spacing',4));max_chars=int(cfg.get('lyrics_max_chars_per_line',0))
 try:
  for i,line in enumerate(lines):
   t=float(line['time']); next_t=float(lines[i+1]['time']) if i+1<len(lines) else hook_end
   a=max(hook_start,t); b=min(hook_end,max(t+0.08,next_t))
   if b<=hook_start or a>=hook_end: continue
   text=str(line['text']).replace('\x00','').strip()
   if max_chars>0 and len(text)>max_chars:
    # Always preserve the complete lyric.  Split into at most two visual
    # lines; never truncate at two lines.  Prefer a balanced word boundary,
    # and fall back to a character split for scripts without spaces.
    words=text.split()
    if len(words) >= 2:
     best_i=1; best_score=None
     for cut in range(1,len(words)):
      left=' '.join(words[:cut]); right=' '.join(words[cut:])
      score=abs(len(left)-len(right)) + (max(0,len(left)-max_chars)*2) + (max(0,len(right)-max_chars)*2)
      if best_score is None or score<best_score:
       best_score=score; best_i=cut
     text=' '.join(words[:best_i])+'\n'+' '.join(words[best_i:])
    else:
     mid=max(1,len(text)//2)
     text=text[:mid]+'\n'+text[mid:]
   text_file=root/f'.lyric_{i:04d}.txt';text_file.write_text(text,encoding='utf-8-sig');created.append(text_file)
   # drawtext has no separate bold switch. Bold is achieved by selecting the configured bold font file.
   # This is deliberately config-driven via lyrics_fontfile rather than relying on fontconfig.
   fontcolor=f"{font_color}@{max(0,min(1,opacity)):.3f}"
   parts.append('drawtext='+':'.join([
    f"fontfile='{_ffmpeg_path(font_path)}'",f"textfile='{_ffmpeg_path(text_file)}'",f"fontcolor={_escape_filter_value(fontcolor)}",
    f"bordercolor={_escape_filter_value(border_color)}",f"borderw={border_w}",f"fontsize={font_size}",f"line_spacing={line_spacing}",
    f"x={x_expr}",f"y={y_expr}",f"enable='between(t,{a-hook_start:.3f},{b-hook_start:.3f})'"
   ]))
  return ','.join(parts),created,root
 except Exception:
  for f in created:f.unlink(missing_ok=True)
  if temp_dir is None and root.exists():
   try:root.rmdir()
   except OSError:pass
  raise

def render(video,start,end,out,cfg,lyrics=None):
 req('ffmpeg');out=Path(out);out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix('.rendering.mp4');w=int(cfg['video_width']);h=int(cfg['video_height']);cw=float(cfg.get('source_crop_width',.7));ch=float(cfg.get('source_crop_height',.55));f=''
 if cfg.get('cinematic_enabled',True):f=f"eq=brightness={cfg.get('cinematic_brightness',0)}:contrast={cfg.get('cinematic_contrast',1.1)}:saturation={cfg.get('cinematic_saturation',1.03)}:gamma={cfg.get('cinematic_gamma',1.02)},unsharp=5:5:{cfg.get('cinematic_sharpen',.3)}:5:5:0,vignette=PI/{cfg.get('cinematic_vignette_divisor',7)}:eval=frame,"
 # Keep lyrics on the foreground video itself. The crop is first created and processed;
 # lyrics are drawn onto [fg] before it is overlaid onto the black canvas.
 fg_filter=f"[0:v]crop=iw*{cw}:ih*{ch}:(iw-ow)/2:(ih-oh)/2,scale={w}:-1:flags=lanczos,setsar=1,{f}format=yuv420p[fg]"
 lyric_lines=[];lyric_temp_files=[];lyric_temp_root=None
 if lyrics:
  from modules.lyrics import parse_lrc
  lyric_lines=parse_lrc(lyrics) if isinstance(lyrics,(str,Path)) else lyrics
  lyric_filter,lyric_temp_files,lyric_temp_root=_subtitle_filter(lyric_lines,float(start),float(end),w,h,cfg.get('lyrics_fontfile'),cfg.get('lyrics_font_size',52),temp_dir=out.parent/f'.{out.stem}_lyrics_tmp',cfg=cfg)
  # Foreground dimensions are w x variable h. drawtext expressions therefore refer to the
  # actual video area, guaranteeing that lyrics cannot fall into the outer black region.
  fg_filter += f";[fg]{lyric_filter}[fg_lyrics]"
  fg_label='fg_lyrics'
 else: fg_label='fg'
 filt=fg_filter+f";color=c=black:s={w}x{h}:r={cfg.get('video_fps',30)}[bg];[bg][{fg_label}]overlay=(W-w)/2:(H-h)/2:shortest=1[base]"
 # No lyric overlay is added after compositing; this guarantees all lyric pixels are inside the video.
 filt += ';[base]copy[v]'
 gpu=cfg.get('video_encoder','auto').lower() in {'auto','gpu','nvenc'} and nvenc();enc=['-c:v','h264_nvenc','-preset',cfg.get('nvenc_preset','p5'),'-cq',str(cfg.get('nvenc_cq',20)),'-b:v','0'] if gpu else ['-c:v','libx264','-preset',cfg.get('cpu_preset','medium'),'-crf',str(cfg.get('video_crf',18))]
 cmd=['ffmpeg','-y','-hide_banner','-loglevel','error','-ss',f'{float(start):.3f}','-i',str(video),'-t',f'{float(end-start):.3f}','-filter_complex',filt,'-map','[v]','-map','0:a?','-r',str(cfg.get('video_fps',30)),*enc,'-pix_fmt','yuv420p','-c:a','aac','-b:a',cfg.get('audio_bitrate','192k'),'-movflags','+faststart',str(tmp)]
 try:
  q=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
  if q.returncode:
   tmp.unlink(missing_ok=True);raise RuntimeError(q.stdout[-8000:] or 'FFmpeg render failed')
  tmp.replace(out)
  return {'command':cmd,'encoder':'h264_nvenc' if gpu else 'libx264','canvas':{'width':w,'height':h,'fps':cfg.get('video_fps',30),'aspect_ratio':f'{w}:{h}'},'crop':{'width_fraction':cw,'height_fraction':ch},'lyrics_rendered':bool(lyric_lines),'lyrics_line_count':len(lyric_lines),'lyrics_position':'foreground_lower_middle','lyrics_config':{k:cfg.get(k) for k in ['lyrics_fontfile','lyrics_font_size','lyrics_bold','lyrics_font_color','lyrics_border_color','lyrics_border_width','lyrics_opacity','lyrics_x','lyrics_y','lyrics_alignment','lyrics_line_spacing','lyrics_max_chars_per_line']},'probe':probe(out)}
 finally:
  for fpath in lyric_temp_files:Path(fpath).unlink(missing_ok=True)
  if lyric_temp_root and Path(lyric_temp_root).exists():
   try:Path(lyric_temp_root).rmdir()
   except OSError:pass
