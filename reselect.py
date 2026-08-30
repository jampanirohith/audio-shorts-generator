"""Manual YouTube reselection for an existing unfinished/error serial.
Spotify track, Spotify audio and Spotify LRC remain authoritative.
"""
import argparse, json
from pathlib import Path
from dotenv import load_dotenv
from modules.db import PlaylistDB, ReelDB, SongsDB
from modules.youtube import search, rank, choose, download_video
from modules.spotify import song_key
from modules.lyrics import parse_lrc, hook_relative_lines
from modules.sync import synchronize
from modules.video import probe, render
from modules.songfile import make_canonical
from main import load, ensure, sha, clean, youtube_query


def main():
    load_dotenv('.env'); ap=argparse.ArgumentParser(); ap.add_argument('--config',default='config.json'); ap.add_argument('serial_pos',nargs='?',type=int); ap.add_argument('--serial',dest='serial_opt',type=int); args=ap.parse_args(); cfg=load(args.config); ensure(cfg); serial=args.serial_opt if args.serial_opt is not None else args.serial_pos
    if serial is None: ap.error('a serial is required (example: python reselect.py 1)')
    with PlaylistDB(cfg['playlist_db_path']) as pdb, ReelDB(cfg['reel_db_path']) as rdb, SongsDB(cfg['songs_db_path']) as sdb:
        reel=rdb.get(serial)
        if not reel: raise SystemExit(f'Serial {serial:04d} does not exist in reel.db.')
        entry=pdb.by_serial(serial)
        if not entry: raise SystemExit(f'No playlist entry is associated with serial {serial:04d}.')
        job=Path(cfg['temp_dir'])/f'{serial:04d}'
        audio=next((p for p in job.iterdir() if p.suffix.lower() in {'.mp3','.m4a','.flac','.ogg','.opus','.wav'} and not p.name.startswith('.')),None) if job.is_dir() else None
        lrc=job/'spotify.lrc'
        if not audio: raise SystemExit('Spotify audio is not available in the serial temp directory; rerun main.py to rebuild the stage.')
        track={'name':entry['title'],'artists':[x.strip() for x in (entry['artists'] or '').split(',') if x.strip()],'album_name':entry['album'] or '', 'url':entry['url'],'spotify_id':entry['spotify_id'],'song_id':entry['spotify_id'],'isrc':entry['isrc']}
        print('='*78);print(f'MANUAL YOUTUBE RESELECTION — SERIAL {serial:04d}');print('='*78)
        default_q=youtube_query(track)
        print(f'Default YouTube query: {default_q}',flush=True)
        q=input('Enter YouTube search query (required; type your own search): ').strip()
        if not q: raise SystemExit('YouTube search query cannot be empty.')
        print(f'Query: {q}\n',flush=True)
        results=search(q,cfg.get('top_youtube_results',10)); ranked=rank(results,track['name'],', '.join(track['artists']),track['album_name'],None,cfg); selected,_=choose(ranked,'manual')
        print(f'\nSelected YouTube: {selected["title"]}\nURL: {selected["url"]}',flush=True)
        video=job/'youtube_source.mp4'; video.unlink(missing_ok=True); print('\nYouTube video download: STARTING',flush=True); video=download_video(selected['url'],job); print('YouTube video download: COMPLETE',flush=True)
        # Hook was already selected from Spotify in main.py. Reuse it from reel metadata when available.
        hook=None
        try: hook=json.loads(reel['metadata_json'] or '{}').get('hook')
        except Exception: hook=None
        if not hook: raise SystemExit('Existing hook metadata is unavailable. Rerun main.py so Spotify hook analysis can be completed first.')
        sync=synchronize(video,audio,hook_start=float(hook['start']),cfg=cfg); print(f'\nSynchronization: offset={sync["offset_seconds"]:+.4f}s confidence={sync["confidence"]:.4f}',flush=True)
        if sync['confidence'] < float(cfg.get('sync_min_confidence',.45)): raise RuntimeError(f'Synchronization confidence too low: {sync["confidence"]:.4f}')
        yt_start=float(hook['start'])+float(sync['offset_seconds']); duration=float(hook['duration']); render_lrc=hook_relative_lines(lrc,float(hook['start']),float(hook['end'])) if lrc.is_file() else []
        out=Path(cfg['reels_dir'])/f'{serial:04d}.mp4'; print('\nRendering final 16:9 reel: STARTING',flush=True); rr=render(video,yt_start,duration,audio,float(hook['start']),out,cfg,lyrics=render_lrc); print('Rendering final 16:9 reel: COMPLETE',flush=True); print(f'Reel: {out.resolve().as_uri()}',flush=True)
        metadata={'schema_version':'8.0-reselect','serial':serial,'status':'FINISHED','playlist':dict(entry),'spotify':track,'hook':hook,'youtube':{'selected':selected,'search_query':q,'candidates':ranked},'synchronization':sync,'final_reel':{'lyrics_source':'spotify_lrc','lyrics_count':len(render_lrc),'video_aspect_ratio':'16:9'},'files':{'reel':str(out),'reel_sha256':sha(out)}}
        jp=out.with_suffix('.json');tmp_json=jp.with_suffix('.json.tmp');tmp_json.write_text(json.dumps(metadata,ensure_ascii=False,indent=2,default=str),encoding='utf-8');json.loads(tmp_json.read_text(encoding='utf-8'));tmp_json.replace(jp);print(f'Metadata JSON: {jp.resolve()}',flush=True);rdb.set_youtube(serial,selected);rdb.finish(serial,metadata,out,jp);pdb.set_finished(entry['playlist_id'],entry['spotify_id'],serial);clean(job);print('\nRESELECTION FINISHED.',flush=True)
if __name__=='__main__': main()
