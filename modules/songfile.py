import shutil
from pathlib import Path
from .lyrics import embed_lrc_mp3
def make_canonical(audio,artwork,lrc,songs_dir,serial):
 outdir=Path(songs_dir);outdir.mkdir(parents=True,exist_ok=True);out=outdir/f'{serial:04d}{Path(audio).suffix.lower()}';shutil.copy2(audio,out)
 if artwork and out.suffix=='.mp3':
  from mutagen.mp3 import MP3
  from mutagen.id3 import ID3,APIC
  a=MP3(str(out),ID3=ID3)
  try:a.add_tags()
  except:pass
  mime='image/png' if Path(artwork).suffix.lower()=='.png' else 'image/jpeg';a.tags.delall('APIC');a.tags.add(APIC(encoding=3,mime=mime,type=3,desc='Cover',data=Path(artwork).read_bytes()));a.save()
 if lrc and out.suffix=='.mp3':embed_lrc_mp3(out,Path(lrc).read_text(encoding='utf-8-sig',errors='replace'))
 return out
