from __future__ import annotations
from pathlib import Path
import json
import numpy as np
from .audio_io import decode_wav, write_stereo_wav, loudness_normalize
from .utils import Phase3Error, clamp


class Audio8DEngine:
    """Render the exact selected local-song hook from Demucs stems as a timeline-preserving 8D mix.

    The source for every rendered sample is the selected [reel_start_ms, reel_end_ms]
    interval of the Demucs vocals/drums/bass/other stems. No pitch or speed change is
    applied. Vocals and bass remain centered; drums stay center-weighted; the "other"
    stem receives the strongest smooth left-right motion that creates the 8D effect.
    """

    STEMS = ('vocals', 'drums', 'bass', 'other')

    def __init__(self, cfg, work_dir, logger):
        self.cfg = cfg
        self.work = Path(work_dir)
        self.logger = logger
        self.manifest = None

    @staticmethod
    def _mono(x: np.ndarray) -> np.ndarray:
        return x.mean(axis=0) if x.ndim > 1 else x

    @staticmethod
    def _equal_power_pan(mono: np.ndarray, pan: np.ndarray | float) -> np.ndarray:
        if np.isscalar(pan):
            theta=(float(pan)+1.0)*np.pi/4.0
            return np.vstack((mono*np.cos(theta), mono*np.sin(theta)))
        p=np.asarray(pan, dtype=np.float32)
        theta=(p+1.0)*np.pi/4.0
        return np.vstack((mono*np.cos(theta), mono*np.sin(theta)))

    @staticmethod
    def _stereo_center_weighted(stereo: np.ndarray, center_weight: float, width: float) -> np.ndarray:
        mono=stereo.mean(axis=0)
        center=np.vstack((mono, mono))
        return center*float(center_weight) + stereo*float(width)

    @staticmethod
    def _smooth_pan(length: int, sr: int, width: float, freq: float, phase: float=0.0) -> np.ndarray:
        t=np.arange(length, dtype=np.float32)/float(sr)
        # Sine motion is deliberately slow and smooth: this is spatial movement,
        # not a time/pitch effect.
        return np.clip(np.sin(2*np.pi*float(freq)*t + float(phase))*float(width), -1.0, 1.0)

    def _crop_stems(self, stems: dict, reel_start_ms: int, reel_end_ms: int):
        audio_dir=self.work/'audio'; crop_dir=audio_dir/'cropped_stems'
        audio_dir.mkdir(parents=True, exist_ok=True)
        crop_dir.mkdir(parents=True, exist_ok=True)
        arrays={}; rates={}
        target_sr=int(self.cfg.get('audio_8d.stem_sample_rate',44100))
        for name in self.STEMS:
            if name not in stems:
                raise Phase3Error('AUDIO_RENDER_FAILED', f'Missing Demucs stem: {name}')
            src=Path(stems[name])
            if not src.exists():
                raise Phase3Error('AUDIO_RENDER_FAILED', f'Demucs stem not found: {src}')
            y,rate=decode_wav(src,target_sr,False)
            if y.ndim==1: y=y[None,:]
            st=int(round(reel_start_ms*rate/1000.0)); en=int(round(reel_end_ms*rate/1000.0))
            st=max(0,st); en=min(y.shape[1],en)
            if en<=st:
                raise Phase3Error('AUDIO_RENDER_FAILED', f'Invalid {name} stem crop for {reel_start_ms}-{reel_end_ms} ms')
            seg=np.asarray(y[:,st:en],dtype=np.float32)
            arrays[name]=seg; rates[name]=rate
            if bool(self.cfg.get('audio_8d.save_cropped_stems',True)):
                crop_path=crop_dir/f'{name}_hook.wav'
                write_stereo_wav(crop_path, seg if seg.shape[0]==2 else np.vstack((seg[0],seg[0])), rate)
        n=min(a.shape[1] for a in arrays.values())
        arrays={k:v[:,:n] for k,v in arrays.items()}
        return arrays, target_sr, crop_dir

    def render(self, stems:dict, reel_start_ms:int, reel_end_ms:int, duration_ms:int, mode='chorus')->Path:
        actual_ms=int(reel_end_ms-reel_start_ms)
        if actual_ms<=0:
            raise Phase3Error('AUDIO_RENDER_FAILED','Selected Reel duration is not positive')

        arrays,sr,crop_dir=self._crop_stems(stems,reel_start_ms,reel_end_ms)
        n=min(x.shape[1] for x in arrays.values())
        chorus=mode.upper() in ('CHORUS','FINAL_CHORUS','REFRAIN','BUILD','VOCAL_HIGHLIGHT')

        # 1) VOCALS — anchor the lyric at the center. Optional stereo send is tiny by design.
        vocal_mono=self._mono(arrays['vocals'])
        vocal=np.vstack((vocal_mono,vocal_mono))
        vocal_send=float(self.cfg.get('audio_8d.vocal_stereo_send',0.0))
        if vocal_send>0:
            t=np.arange(n,dtype=np.float32)/sr
            pan=np.sin(2*np.pi*(0.035 if chorus else 0.025)*t)*0.25
            side=self._equal_power_pan(vocal_mono,pan)
            vocal=(1.0-vocal_send)*vocal + vocal_send*side

        # 2) BASS — mono/centered for translation and mono compatibility.
        bass_mono=self._mono(arrays['bass'])
        bass=self._equal_power_pan(bass_mono,float(self.cfg.get('audio_8d.bass_pan_amount',0.0)))

        # 3) DRUMS — retain some source stereo, but keep the center dominant.
        drums=arrays['drums']
        center=float(self.cfg.get('audio_8d.drums_center_weight',0.85))
        width=float(self.cfg.get('audio_8d.drums_stereo_width',0.15))
        drums_mix=self._stereo_center_weighted(drums,center,width)
        drum_motion=float(self.cfg.get('audio_8d.drums_pan_amount',0.15))
        if drum_motion>0:
            t=np.arange(n,dtype=np.float32)/sr
            dpan=np.sin(2*np.pi*(0.035 if chorus else 0.025)*t + 0.7)*drum_motion
            moved=self._equal_power_pan(self._mono(drums),dpan)
            drums_mix=0.85*drums_mix+0.15*moved

        # 4) OTHER — this is the main 8D travel bed. Slow LFO pan with wider movement
        # during chorus/refrain sections, while preserving the song timeline exactly.
        other=self._mono(arrays['other'])
        width_key='audio_8d.other_lfo_width_chorus' if chorus else 'audio_8d.other_lfo_width_verse'
        freq_key='audio_8d.other_lfo_frequency_chorus_hz' if chorus else 'audio_8d.other_lfo_frequency_verse_hz'
        pan_width=float(self.cfg.get(width_key,0.8 if chorus else 0.4))
        pan_freq=float(self.cfg.get(freq_key,0.10 if chorus else 0.05))
        pan=self._smooth_pan(n,sr,pan_width,pan_freq)
        other_8d=self._equal_power_pan(other,pan)

        mix=vocal+bass+drums_mix+other_8d

        # Preserve exact start/end timing; only amplitude fades are used.
        fi=min(n,int(sr*float(self.cfg.get('audio_8d.fade_in_ms',150))/1000.0))
        fo=min(n,int(sr*float(self.cfg.get('audio_8d.fade_out_ms',250))/1000.0))
        if fi>0: mix[:,:fi]*=np.linspace(0,1,fi,dtype=np.float32)[None,:]
        if fo>0: mix[:,-fo:]*=np.linspace(1,0,fo,dtype=np.float32)[None,:]

        peak=float(np.max(np.abs(mix))+1e-9)
        if peak>0.98: mix*=0.95/peak

        audio_dir=self.work/'audio'
        raw=audio_dir/'reel_8d_pre_loudnorm.wav'
        out=audio_dir/'reel_8d.wav'
        write_stereo_wav(raw,mix,sr)
        loudness_normalize(raw,out,float(self.cfg.get('audio_8d.target_lufs',-14)),float(self.cfg.get('audio_8d.true_peak_db',-1)))

        self.manifest={
            'mode':'8d_spatial_4stem',
            'source':'local_song_demucs_stems',
            'reel_start_ms':int(reel_start_ms),
            'reel_end_ms':int(reel_end_ms),
            'duration_ms':int(actual_ms),
            'sample_rate':int(sr),
            'cropped_stems':{name:str(crop_dir/f'{name}_hook.wav') for name in self.STEMS},
            'stem_roles':{
                'vocals':'centered',
                'bass':'mono_centered',
                'drums':'center_weighted_light_motion',
                'other':'smooth_dynamic_left_right_pan',
            },
            'pitch_or_speed_change':False,
            'timeline_preserved':True,
            'chorus_mode':bool(chorus),
            'other_pan_width':float(pan_width),
            'other_pan_frequency_hz':float(pan_freq),
            'target_lufs':float(self.cfg.get('audio_8d.target_lufs',-14)),
            'true_peak_db':float(self.cfg.get('audio_8d.true_peak_db',-1)),
            'output_wav':str(out),
        }
        (audio_dir/'audio_8d_manifest.json').write_text(json.dumps(self.manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        return out
