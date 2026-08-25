import json, shutil, sys, hashlib
from pathlib import Path
from dotenv import load_dotenv
from modules.db import DB
from modules.youtube import playlist, search, choose_youtube, download, info, metadata_clues
from modules.spotify import search_top5, choose_top5, download_and_finalize
from modules.fingerprint import fingerprint
from modules.align import align
from modules.hooks import detect
from modules.video import preview, make_ass, render


def qid_for(entry):
    return entry.get('id') or hashlib.sha1(entry['url'].encode('utf-8')).hexdigest()[:20]

def absolute(p): return str(Path(p).resolve())

def _row_data(row):
    if not row or not row['data_json']:
        return {}
    try:
        return json.loads(row['data_json'])
    except Exception:
        return {}

def process_one(entry,pos,total,db,cfg):
    qid=qid_for(entry); db.upsert(qid,entry['title'],entry.get('playlist_index'),entry['url'],entry.get('playlist_added'))
    row=db.get(qid)
    was_failed = bool(row and row['status']=='FAILED')
    saved_before = _row_data(row)
    if row and row['status']=='DONE': return 'done'
    print('\n'+'='*88)
    print(f'[{pos}/{total}] {entry["title"]}')
    print(f'Playlist position: {entry.get("playlist_index")} | added: {entry.get("playlist_added") or "fallback: playlist order"}')
    print('='*88)
    auto=cfg.get('automation',{})
    if auto.get('auto_continue',False):
        print('AUTO-CONTINUE enabled: starting without confirmation.')
    else:
        action=input('Press ENTER to process, s=skip this song, q=quit: ').strip().lower()
        if action=='q': return 'quit'
        if action=='s': db.set_status(qid,'SKIPPED'); db.event(qid,'SKIP','Skipped before any download'); return 'skipped'

    staging=Path(cfg['temp_dir'])/'_youtube_downloads'/str(entry.get('id') or hashlib.sha1(entry['url'].encode()).hexdigest()[:16])
    try:
        db.set_status(qid,'YOUTUBE_SEARCHING'); db.event(qid,'YOUTUBE_SEARCH','Searching top YouTube results')
        search_limit = int(cfg.get('top_youtube_results',5))
        if auto.get('auto_youtube_selection',False):
            search_limit = max(search_limit, int(auto.get('auto_youtube_result_limit',10)))
        results=search(entry['title'],search_limit); sel=choose_youtube(results,entry['title'],cfg)
        if sel=='quit': return 'quit'
        if sel=='skip': db.set_status(qid,'SKIPPED'); return 'skipped'
        yid=sel['id']
        db.save_json(qid,'youtube_selected',sel)
        if db.youtube_exists(yid):
            print('This exact YouTube video was already finalized in the database. Skipping duplicate.')
            db.set_status(qid,'DUPLICATE',youtube_id=yid); return 'skipped'

        db.set_status(qid,'YOUTUBE_DOWNLOADING',youtube_id=yid); db.event(qid,'YOUTUBE_DOWNLOAD',sel['url'])
        yfile=download(sel['url'],staging)
        yi=info(sel['url']); clues=metadata_clues(yi); clues['automation']=cfg.get('automation',{}); db.save_json(qid,'youtube_metadata',clues)
        row_now=db.get(qid); saved=saved_before if was_failed else _row_data(row_now); saved_sp=saved.get('spotify_selected')
        if saved_sp and was_failed and saved_sp.get('url') and saved_sp.get('isrc'):
            sp=saved_sp
            sp_results=saved.get('spotify_candidates') or [sp]
            print(f'\nRESUMING saved Spotify selection: {sp["title"]} — {sp["artist"]} | {sp["album"]} | ISRC={sp["isrc"]}')
        else:
            db.set_status(qid,'SPOTIFY_SEARCHING'); db.event(qid,'SPOTIFY_SEARCH','Searching top 5 using title/artist/movie metadata')
            sp_results=search_top5(clues)
            if not sp_results: raise RuntimeError('No Spotify matches found')
            sp=choose_top5(sp_results,cfg)
            if sp=='quit': return 'quit'
            if sp=='skip': db.set_status(qid,'SKIPPED'); return 'skipped'
            print(f'\nSELECTED Spotify: {sp["title"]} — {sp["artist"]} | {sp["album"]} | ISRC={sp["isrc"]}')
            db.set_status(qid,'SPOTIFY_SELECTED',isrc=sp['isrc'],selected_spotify=sp_results.index(sp)+1)
            db.save_json(qid,'spotify_candidates',[{k:v for k,v in x.items() if k!='raw'} for x in sp_results])
            db.save_json(qid,'spotify_selected',{k:v for k,v in sp.items() if k!='raw'})

        # Avoid duplicates by both the exact YouTube video and the selected Spotify ISRC.
        if db.song_exists(sp['isrc']):
            audio_path,reel_path=db.song_final_paths(sp['isrc'])
            if audio_path and reel_path and Path(audio_path).exists() and Path(reel_path).exists():
                print(f'Duplicate ISRC already finalized: {sp["isrc"]}. Skipping duplicate song.')
                db.set_status(qid,'DUPLICATE',isrc=sp['isrc'],youtube_id=yid); return 'skipped'

        songtemp=Path(cfg['temp_dir'])/sp['isrc']; songtemp.mkdir(parents=True,exist_ok=True)
        target=songtemp/yfile.name; shutil.move(str(yfile),target); shutil.rmtree(staging,ignore_errors=True)
        db.set_status(qid,'SPOTIFY_DOWNLOADING',isrc=sp['isrc'])
        final_audio,lrc,meta,art=download_and_finalize(sp,songtemp,Path(cfg['songs_final_dir']),cfg)
        db.save_song(sp,yid,{'youtube':clues,'spotify_metadata':str(meta),'lyrics':str(lrc) if lrc else None},final_audio=str(final_audio))

        db.set_status(qid,'FINGERPRINTING'); db.event(qid,'FINGERPRINT','Fingerprinting both Spotify and YouTube audio')
        spfp,_=fingerprint(final_audio,songtemp,'spotify'); ytfp,_=fingerprint(target,songtemp,'youtube')
        db.save_json(qid,'fingerprints',{'spotify':spfp,'youtube':ytfp})

        db.set_status(qid,'ALIGNING'); db.event(qid,'ALIGN','Multi-anchor onset+chroma alignment')
        alignment=align(final_audio,target,songtemp); db.save_json(qid,'alignment',alignment)
        print(f'\nAudio alignment: offset={alignment["spotify_to_youtube_offset_seconds"]:.3f}s, confidence={alignment["confidence"]:.3f}, spread={alignment["offset_spread_seconds"]:.3f}s')

        db.set_status(qid,'HOOK_DETECTION'); db.event(qid,'HOOKS','Detecting hooks from YouTube audio only')
        hooks=detect(target,songtemp,cfg); (songtemp/'hooks.json').write_text(json.dumps(hooks,ensure_ascii=False,indent=2),encoding='utf-8')
        print('\nTHREE HOOK OPTIONS (analysis uses ONLY the YouTube video audio):')
        for h in hooks: print(f'  [{h["rank"]}] {h["start"]:.2f}s -> {h["end"]:.2f}s | score={h["score"]:.4f}')

        print('\nCreating three clickable 9:16 preview reels (lyrics are added only after you choose one)...')
        previews=[]
        for h in hooks:
            p=songtemp/f'reel_option_{h["rank"]}.mp4'; preview(target,h,p,cfg); previews.append(p)
            print(f'OPTION {h["rank"]}: {absolute(p)}')
            print(f'          file:///{absolute(p).replace(chr(92), "/")}')
        print('\nThe absolute paths above are clickable in VS Code terminal. Open each preview and choose the best hook.')
        if auto.get('auto_hook_selection',False):
            eligible=[h for h in hooks if float(h.get('score',0)) >= float(auto.get('auto_hook_min_score',0.0))]
            if not eligible:
                raise RuntimeError('Automatic hook selection found no hook above the configured minimum score.')
            hook=max(eligible,key=lambda h: float(h.get('score',0)))
            choice=int(hook['rank'])
            print(f'\nAUTO selected hook [{choice}] with highest score={hook["score"]:.4f} ({hook["start"]:.2f}s -> {hook["end"]:.2f}s)')
        else:
            db.set_status(qid,'AWAITING_HOOK_CHOICE')
            while True:
                x=input('Choose final reel [1-3], or s=skip, q=quit: ').strip().lower()
                if x=='q': return 'quit'
                if x=='s': db.set_status(qid,'SKIPPED'); return 'skipped'
                if x in ('1','2','3'): choice=int(x); break
            hook=hooks[choice-1]

        db.set_status(qid,'FINAL_RENDERING',selected_hook=choice)
        ass=songtemp/'lyrics.ass'
        has_lyrics=False
        if lrc and Path(lrc).exists():
            has_lyrics=make_ass(lrc,hook['start'],hook['end'],alignment,ass,cfg)
        finaldir=Path(cfg['reels_finished_dir']); finaldir.mkdir(parents=True,exist_ok=True)
        out=finaldir/f'{sp["isrc"]}_reel.mp4'
        render(target,hook['start'],hook['end'],ass if has_lyrics else None,out,cfg)
        detail={'isrc':sp['isrc'],'spotify':{k:v for k,v in sp.items() if k!='raw'},
                'youtube':{'id':yid,'url':sel['url'],'title':sel['title'],'channel':sel.get('channel')},
                'youtube_metadata':clues,'fingerprints':{'spotify':spfp,'youtube':ytfp},'alignment':alignment,
                'hooks':hooks,'chosen_hook':hook,'lyrics_source':'Spotify synced LRC' if lrc else None,
                'lyrics_embedded':has_lyrics,'final_reel':absolute(out),'final_audio':absolute(final_audio),
                'video_layout':'1080x1920; pure black background; small centered source-edge crop removes border/watermark pixels; landscape foreground is never cropped to portrait and is never stretched',
                'font':cfg.get('telugu_font','Noto Serif Telugu')}
        (finaldir/f'{sp["isrc"]}_reel.json').write_text(json.dumps(detail,ensure_ascii=False,indent=2),encoding='utf-8')
        db.mark_youtube_done(yid,sp['isrc'],sp['title'],str(out))
        db.save_song(sp,yid,detail,final_audio=str(final_audio),final_reel=str(out))
        db.save_json(qid,'result',detail); db.set_status(qid,'DONE',selected_hook=choice,error=None)
        db.event(qid,'DONE',str(out))
        # Only successful completion deletes temp. Failed/quit runs retain temp for resume/debugging.
        shutil.rmtree(songtemp,ignore_errors=True); shutil.rmtree(Path(cfg['temp_dir'])/'_youtube_downloads',ignore_errors=True)
        print(f'\nDONE: {absolute(out)}')
        print(f'FINAL AUDIO: {absolute(final_audio)}')
        return 'done'
    except KeyboardInterrupt: raise
    except Exception as e:
        db.set_status(qid,'FAILED',error=str(e)); db.event(qid,'FAILED',str(e))
        print('\nThe item was NOT marked DONE. Fix the issue and rerun main.py; the state DB will resume this item.')
        raise

def main():
    load_dotenv()
    cfg=json.loads(Path('config.json').read_text(encoding='utf-8'))
    auto=cfg.get('automation',{})
    print('Automation:', json.dumps(auto, ensure_ascii=False))
    for d in [cfg['temp_dir'],cfg['songs_final_dir'],cfg['reels_finished_dir'],'state']: Path(d).mkdir(parents=True,exist_ok=True)
    db=DB(cfg['db_path'])
    entries=playlist(cfg['playlist_url'])
    print(f'Playlist entries: {len(entries)}')
    # Freeze queue order in the DB. Existing rows retain their original order metadata.
    for pos,e in enumerate(entries,1):
        qid=qid_for(e); db.upsert(qid,e['title'],e.get('playlist_index'),e['url'],e.get('playlist_added'))
    # Process the freshly read playlist in true added-date order when API metadata is available;
    # otherwise playlist index is the deterministic fallback.
    entries.sort(key=lambda e:(e.get('playlist_added') is None,e.get('playlist_added') or '',e.get('playlist_index') or 0))
    for pos,e in enumerate(entries,1):
        result=process_one(e,pos,len(entries),db,cfg)
        if result=='quit': return

if __name__=='__main__': main()
