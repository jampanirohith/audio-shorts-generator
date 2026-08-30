import argparse, hashlib, json, os, platform, shutil
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from modules.db import PlaylistDB, ReelDB, SongsDB
from modules.spotify import playlist as spotify_playlist, song_key
from modules.youtube import search as ytsearch, rank as ytrank, choose as ytchoose, download_video
from modules.lyrics import fetch_librelyrics, parse_lrc, hook_relative_lines
from modules.hooks import detect
from modules.sync import synchronize
from modules.video import probe, render
from modules.songfile import make_canonical


def utc(): return datetime.now(timezone.utc).isoformat()

def load(path='config.json'):
    load_dotenv(Path('.env'), override=False)
    return json.loads(Path(path).read_text(encoding='utf-8'))

def ensure(cfg):
    for k in ('temp_dir','songs_dir','reels_dir','playlist_db_path','reel_db_path','songs_db_path'):
        p=Path(cfg[k]);(p.parent if p.suffix else p).mkdir(parents=True,exist_ok=True)

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def clean(path):
    if path and Path(path).exists(): shutil.rmtree(path,ignore_errors=True)

def banner(text):print('\n'+'='*78+'\n'+text+'\n'+'='*78,flush=True)

def show(label,value):
    if value is not None: print(f'  {label:<20}: {value}',flush=True)

def validate_environment(cfg):
    import shutil
    print('Dependency check:',flush=True)
    for exe in ('ffmpeg','ffprobe'):
        ok=shutil.which(exe) is not None;print(f'  {exe:<12}: {"OK" if ok else "MISSING"}',flush=True)
        if not ok:raise RuntimeError(f'{exe} was not found on PATH.')
    import yt_dlp, spotdl, librosa, scipy
    print('  Python packages: OK',flush=True)
    if not os.getenv('SPOTIFY_CLIENT_ID') or not os.getenv('SPOTIFY_CLIENT_SECRET'):raise RuntimeError('Spotify client credentials are missing from .env')
    if cfg.get('librelyrics',{}).get('enabled',True) and not os.getenv('SPOTIFY_SP_DC'):raise RuntimeError('SPOTIFY_SP_DC is missing from .env')
    font=Path(cfg.get('lyrics_fontfile',''))
    if not font.is_file():raise RuntimeError(f'Configured lyric font not found: {font.resolve()}')

def youtube_query(track):
    title=track.get('name','');artists=track.get('artists') or [];primary=artists[0] if artists else ''
    album=track.get('album_name') or ''
    keyword=str(track.get('_youtube_search_keyword') or '').strip()
    return ' '.join(x for x in [title,primary,album,keyword] if x)

def print_candidates(ranked):
    print('\nYouTube candidates:',flush=True)
    for x in ranked[:5]:
        r=x['result'];print(f"[{x['rank']}] score={x['score']:.3f} | {r.get('title','')}",flush=True);show('Channel',r.get('channel'));show('Views',r.get('view_count') or 0);show('URL',r.get('url'))

def process_entry(cfg,pdb,rdb,sdb,pid,playlist_title,entry):
    track={
        '_youtube_search_keyword': cfg.get('youtube_search_keyword','full video song'),
        'name':entry['title'],'artists':[x.strip() for x in (entry['artists'] or '').split(',') if x.strip()],
        'album_name':entry['album'] or '', 'url':entry['url'],'spotify_id':entry['spotify_id'],'song_id':entry['spotify_id'],'isrc':entry['isrc'],
        'duration':entry['duration'] if 'duration' in entry.keys() else None
    }
    serial=None;job=None;started=utc(); playlist_snapshot=pdb.snapshot(pid,entry['spotify_id']); reel_snapshot=None
    banner(f"PLAYLIST ENTRY [{entry['playlist_order']}] : {entry['title']}")
    show('Spotify URL',entry['url']);show('Artist',entry['artists']);show('Album',entry['album']);show('ISRC',entry['isrc'] or 'NOT AVAILABLE')
    try:
        dup=sdb.find_duplicate_isrc(entry['isrc'])
        if dup:
            pdb.set_finished(pid,entry['spotify_id'],dup['serial']);print(f"\nDuplicate ISRC already completed as serial {dup['serial']:04d}; skipping.",flush=True);return 'duplicate'
        active=rdb.active_for_playlist(pid)
        if active and active['spotify_id']==entry['spotify_id']:
            serial=int(active['serial']);reel_snapshot=rdb.snapshot_before_new_serial();job=Path(cfg['temp_dir'])/f'{serial:04d}';job.mkdir(parents=True,exist_ok=True);print(f'\nResuming existing serial: {serial:04d}',flush=True)
        else:
            serial=rdb.allocate_serial();reel_snapshot=rdb.snapshot_before_new_serial();job=Path(cfg['temp_dir'])/f'{serial:04d}';job.mkdir(parents=True,exist_ok=False);rdb.create(serial,track,entry['spotify_id']);print(f'\nAssigned permanent serial: {serial:04d}',flush=True)
        # Stage 1: Spotify audio.
        audio_files=[p for p in job.iterdir() if p.suffix.lower() in {'.mp3','.m4a','.flac','.ogg','.opus','.wav'} and not p.name.startswith('.')]
        if not audio_files:
            from modules.spotify import download as spdownload
            print('\nSpotify audio download: STARTING',flush=True);audio,artwork=spdownload(track,cfg,job);print('Spotify audio download: COMPLETE',flush=True);show('Audio file',audio)
            rdb.stage(serial,'AUDIO_READY');pdb.mark_stage(pid,entry['spotify_id'],'AUDIO_READY')
        else:
            audio=max(audio_files,key=lambda p:p.stat().st_mtime);artwork=next((p for p in job.iterdir() if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'}),None);print('\nSpotify audio: REUSED',flush=True)
        # Stage 2: Spotify LRC. Missing lyrics is recoverable.
        lrc=job/'spotify.lrc'
        if lrc.is_file() and parse_lrc(lrc):
            spotify_lrc=lrc;print('Spotify LRC: REUSED',flush=True)
        else:
            print('Spotify LRC: FETCHING',flush=True);spotify_lrc=fetch_librelyrics(track['url'],lrc,cfg);print('Spotify LRC: '+('FOUND' if spotify_lrc else 'NOT AVAILABLE — continuing without lyrics'),flush=True)
        rdb.stage(serial,'LRC_READY');pdb.mark_stage(pid,entry['spotify_id'],'LRC_READY')
        # Stage 3: hook analysis ONLY on Spotify audio.
        print('\nHook analysis: scanning the entire Spotify recording ...',flush=True)
        hook=detect(audio,job,cfg,spotify_lrc=spotify_lrc);print(f"Hook selected: {hook['start']:.3f}s → {hook['end']:.3f}s ({hook['duration']:.3f}s)",flush=True);print(f"Candidates evaluated: {hook['candidates_evaluated']}",flush=True);print(f"Hook lyric source: {'Spotify LRC' if spotify_lrc else 'none'}",flush=True)
        rdb.stage(serial,'HOOK_READY');pdb.mark_stage(pid,entry['spotify_id'],'HOOK_READY')
        # Stage 4: YouTube search only after hook selection.
        query=youtube_query(track);print('\nYouTube search: STARTING',flush=True);show('Query',query)
        results=ytsearch(query,cfg.get('top_youtube_results',10));ranked=ytrank(results,track['name'],', '.join(track['artists']),track['album_name'],track.get('duration'),cfg);print_candidates(ranked)
        selected,ranked=ytchoose(ranked,cfg.get('youtube_selection_mode','automatic'));print('\nSelected YouTube video:',flush=True);show('Title',selected.get('title'));show('Channel',selected.get('channel'));show('Views',selected.get('view_count') or 0);show('URL',selected.get('url'));rdb.set_youtube(serial,selected);rdb.stage(serial,'YOUTUBE_SELECTED');pdb.mark_stage(pid,entry['spotify_id'],'YOUTUBE_SELECTED')
        # Stage 5: download YouTube visual.
        video=job/'youtube_source.mp4'
        if not video.is_file():
            print('\nYouTube video download: STARTING',flush=True);video=download_video(selected['url'],job);print('YouTube video download: COMPLETE',flush=True);show('Downloaded file',video)
        else:print('\nYouTube video: REUSED',flush=True)
        ytprobe=probe(video);rdb.stage(serial,'YOUTUBE_READY');pdb.mark_stage(pid,entry['spotify_id'],'YOUTUBE_READY')
        # Stage 6: synchronize after hook analysis. Spotify is master timeline.
        print('\nSynchronization: STARTING',flush=True);sync=synchronize(video,audio,hook_start=hook['start'],cfg=cfg);print(f"Offset: {sync['offset_seconds']:+.4f}s",flush=True);print(f"Confidence: {sync['confidence']:.4f}",flush=True);print(f"Peak correlation: {sync['peak_correlation']:.4f}",flush=True)
        print(f"Second peak: {sync.get('second_peak_correlation',0):.4f}",flush=True)
        print(f"Peak margin: {sync.get('peak_margin',0):.4f}",flush=True)
        if cfg.get('sync_diagnostics_enabled', True):
            print('Synchronization diagnostics:',flush=True)
            for reason in sync.get('diagnostics',[]): print(f'  - {reason}',flush=True)
        if sync['confidence'] < float(cfg.get('sync_min_confidence',.45)):raise RuntimeError(f"Synchronization confidence too low: {sync['confidence']:.4f}")
        yt_start=float(hook['start'])+float(sync['offset_seconds']);duration=float(hook['duration'])
        if yt_start < 0: yt_start=0.0
        yt_duration=float(ytprobe.get('format',{}).get('duration') or 0)
        if yt_start+duration>yt_duration:raise RuntimeError(f'YouTube visual does not contain the synchronized hook: need {yt_start+duration:.3f}s, video duration is {yt_duration:.3f}s')
        rdb.stage(serial,'SYNC_READY');pdb.mark_stage(pid,entry['spotify_id'],'SYNC_READY')
        # Final lyrics are ALWAYS Spotify LRC; no YouTube LRC path exists.
        render_lrc=hook_relative_lines(spotify_lrc,hook['start'],hook['end']) if spotify_lrc else []
        out=Path(cfg['reels_dir'])/f'{serial:04d}.mp4';jsonpath=out.with_suffix('.json')
        print('\nRendering final 16:9 reel: STARTING',flush=True);rr=render(video,yt_start,duration,audio,hook['start'],out,cfg,lyrics=render_lrc);print('Rendering final 16:9 reel: COMPLETE',flush=True);show('Reel file',out.resolve().as_uri());show('Metadata JSON',jsonpath.resolve().as_uri())
        rdb.stage(serial,'RENDERED');pdb.mark_stage(pid,entry['spotify_id'],'RENDERED')
        # Canonical song is permanent only after successful reel rendering.
        print('\nCreating canonical Spotify song: STARTING',flush=True);canonical=make_canonical(audio,artwork,spotify_lrc,cfg['songs_dir'],serial);print('Canonical Spotify song: COMPLETE',flush=True);show('Song file',canonical.resolve().as_uri())
        metadata={'schema_version':'8.0','serial':serial,'status':'FINISHED','timestamps':{'started_at':started,'finished_at':utc()},'playlist':{'playlist_id':pid,'title':playlist_title,'order':entry['playlist_order'],'spotify_id':entry['spotify_id']},'spotify':track,'hook':hook,'youtube':{'selected':selected,'search_query':query,'candidates':ranked,'visual_file':str(video),'ffprobe':ytprobe},'synchronization':sync,'final_reel':{'lyrics_source':'spotify_lrc','lyrics_count':len(render_lrc),'video_aspect_ratio':'16:9','video_file':str(out),'audio_file':str(audio)},'files':{'reel':str(out),'song':str(canonical),'json':str(jsonpath),'reel_sha256':sha(out),'song_sha256':sha(canonical)},'runtime':{'python':platform.python_version(),'platform':platform.platform()},'config_snapshot':cfg}
        json_tmp=jsonpath.with_suffix('.json.tmp');json_tmp.write_text(json.dumps(metadata,ensure_ascii=False,indent=2,default=str),encoding='utf-8');json.loads(json_tmp.read_text(encoding='utf-8'));json_tmp.replace(jsonpath);print('  Metadata JSON     : '+str(jsonpath.resolve()),flush=True)
        # Validate every permanent artifact BEFORE committing FINISHED state to the databases.
        final=probe(out);streams=final.get('streams') or [];v=next((s for s in streams if s.get('codec_type')=='video'),None);a=next((s for s in streams if s.get('codec_type')=='audio'),None)
        if not v or not a:raise RuntimeError('Final validation failed: missing video or audio stream.')
        ratio=float(v.get('width',0))/max(float(v.get('height',1)),1)
        if abs(ratio-16/9)>0.01:raise RuntimeError(f'Final validation failed: output is not 16:9 ({v.get("width")}x{v.get("height")}).')
        if not out.is_file() or not canonical.is_file() or not jsonpath.is_file():raise RuntimeError('Final validation failed: permanent file missing.')
        sdb.insert({'serial':serial,'song_key':song_key(track),'isrc':track.get('isrc'),'title':track.get('name'),'artists':json.dumps(track.get('artists') or [],ensure_ascii=False),'album':track.get('album_name'),'spotify_url':track.get('url'),'spotify_track_id':track.get('spotify_id'),'youtube_video_id':selected.get('id'),'youtube_url':selected.get('url'),'spotify_source_file':str(audio),'spotdl_source_url':track.get('url'),'canonical_file':str(canonical),'artwork_file':str(artwork) if artwork else None,'lrc_file':str(spotify_lrc) if spotify_lrc else None,'lrc_source':'spotify_librelyrics' if spotify_lrc else None,'sync_json':json.dumps(sync),'hook_json':json.dumps(hook),'metadata_json':json.dumps(metadata),'created_at':utc()})
        rdb.finish(serial,metadata,out,jsonpath)
        pdb.set_finished(pid,entry['spotify_id'],serial);print('\nFINAL VALIDATION: PASS',flush=True);print('  Reel file       : VALID',flush=True);print('  Aspect ratio    : 16:9',flush=True);print('  Audio source    : Spotify',flush=True);print('  Lyrics source   : Spotify LRC',flush=True);print('  Song file       : VALID',flush=True);print('  playlist.db     : FINISHED',flush=True);clean(job);return 'finished'
    except KeyboardInterrupt:
        print('\nSTOP REQUESTED: finishing cleanup for the current song, then stopping the run.',flush=True)
        if job: clean(job)
        if serial is not None and reel_snapshot is not None:
            try:rdb.restore_snapshot(serial,reel_snapshot)
            except Exception as restore_exc: print(f'WARNING: could not fully restore reel DB state: {restore_exc}',flush=True)
        try:pdb.restore_snapshot(playlist_snapshot)
        except Exception as restore_exc: print(f'WARNING: could not fully restore playlist DB state: {restore_exc}',flush=True)
        print('Current song cleaned. Database state for the current song was restored. Run stopped; the next song will NOT be started.',flush=True)
        return 'stopped'
    except Exception as exc:
        msg=f'{type(exc).__name__}: {exc}'
        print(f'\nERROR: {msg}',flush=True)
        if serial is not None:
            try:rdb.stage(serial,'ERROR',{'error':msg,'timestamp':utc()})
            except Exception:pass
        try:pdb.reset(pid,entry['spotify_id'],msg,'ERROR')
        except Exception:pass
        if job: clean(job)
        # Remove incomplete permanent outputs produced by this failed attempt.
        if serial is not None:
            candidates = [Path(cfg['reels_dir'])/f'{serial:04d}.mp4', Path(cfg['reels_dir'])/f'{serial:04d}.json']
            songs_dir = Path(cfg['songs_dir'])
            candidates.extend(songs_dir.glob(f'{serial:04d}.*'))
            for candidate in candidates:
                try:
                    if candidate.exists(): candidate.unlink()
                except Exception: pass
        print(f'Current song marked ERROR; serial {serial:04d} remains permanently consumed.' if serial else 'Current song marked ERROR.',flush=True)
        print('All temporary files for the current song were deleted. Moving to the next playlist song.',flush=True)
        return 'error'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',default='config.json');args=ap.parse_args();cfg=load(args.config);ensure(cfg)
    print('='*78+'\nAUDIO SHORTS GENERATOR — SPOTIFY PLAYLIST / 16:9\n'+'='*78,flush=True)
    print(f"Continue on error: {'YES' if cfg.get('continue_on_error',True) else 'NO'}",flush=True);print(f"YouTube selection: {cfg.get('youtube_selection_mode','automatic')}",flush=True);print('Final audio: Spotify',flush=True);print('Final lyrics: Spotify LRC',flush=True);print('Hook analysis: Spotify audio',flush=True);print('Credentials: loaded from .env',flush=True)
    validate_environment(cfg)
    print('\nReading Spotify playlist ...',flush=True);pid,ptitle,tracks=spotify_playlist(cfg['spotify_playlist_url']);print(f'Playlist: {ptitle}\nPlaylist tracks found: {len(tracks)}',flush=True)
    with PlaylistDB(cfg['playlist_db_path']) as pdb,ReelDB(cfg['reel_db_path']) as rdb,SongsDB(cfg['songs_db_path']) as sdb:
        pdb.sync(pid,cfg['spotify_playlist_url'],ptitle,tracks)
        processed=finished=errors=duplicates=0
        while True:
            entry=pdb.first_pending(pid)
            if not entry:break
            processed+=1;result=process_entry(cfg,pdb,rdb,sdb,pid,ptitle,entry)
            if result=='finished':finished+=1
            elif result=='duplicate':duplicates+=1
            elif result=='stopped':
                print('\nRun stopped by user. No next song will be processed.',flush=True);break
            elif result=='error':
                errors+=1
                if not cfg.get('continue_on_error',True):print('\ncontinue_on_error=false; stopping queue.',flush=True);break
        banner('QUEUE COMPLETE');print(f'Processed this run : {processed}\nFinished           : {finished}\nDuplicates         : {duplicates}\nErrors/skipped     : {errors}',flush=True)

if __name__=='__main__':main()
