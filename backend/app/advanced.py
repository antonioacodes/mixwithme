"""CPU-only, bounded audio descriptors. No isolated-instrument inference."""
import json
import math
import re
import subprocess
import numpy as np
import soundfile as sf
from scipy.signal import stft, butter, sosfilt, find_peaks
from imageio_ffmpeg import get_ffmpeg_exe, get_ffmpeg_version

BANDS = [('sub',20,60),('bass',60,250),('low_mid',250,500),('mid',500,2000),('presence',2000,6000),('air',6000,20001)]

def finite(value):
    x = float(value)
    return x if math.isfinite(x) else None

def dbpower(x):
    return float(10*np.log10(x)) if x > 1e-16 else None

def loudness(path, duration, silent):
    if silent:
        return {'integrated_lufs':None,'true_peak_dbtp':None,'lra_lu':None,'loudness_engine':'FFmpeg loudnorm; signal below analysis floor'}
    proc = subprocess.run([get_ffmpeg_exe(), '-hide_banner','-nostdin','-threads','1',
        '-filter_threads','1','-i',str(path),'-map','0:a:0','-vn','-sn','-dn',
        '-af','loudnorm=I=-16:TP=-1:LRA=11:print_format=json','-f','null','-'],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=90, check=True)
    matches = re.findall(rb'\{[^{}]*"input_i"[^{}]*\}', proc.stderr)
    if not matches: raise RuntimeError('FFmpeg loudness report unavailable')
    raw = json.loads(matches[-1])
    return {'integrated_lufs':finite(raw['input_i']), 'true_peak_dbtp':finite(raw['input_tp']),
            'lra_lu':finite(raw['input_lra']) if duration >= 30 else None,
            'loudness_engine':'FFmpeg '+get_ffmpeg_version()+' loudnorm input measurements',
            'lra_note':'LRA withheld below 30 seconds; short programme statistics are unstable.' if duration < 30 else 'EBU LRA; not crest factor or loudness quality.'}

def descriptors(path):
    timeline=[]; envelopes=[]; contrasts=[]; flatness=[]; centroids=[]; totals={}
    with sf.SoundFile(path) as audio:
        sr=audio.samplerate; channels=audio.channels
        low_filter=butter(4,[40,min(250,sr*.45)],btype='bandpass',fs=sr,output='sos')
        state=np.zeros((len(low_filter),2,channels))
        for index,x in enumerate(audio.blocks(blocksize=sr,dtype='float64',always_2d=True)):
            if len(x)<64: continue
            energy=float(np.mean(x*x)); active=energy>1e-12
            size=min(2048,len(x)); overlap=size//2
            f,_,z=stft(x,fs=sr,nperseg=size,noverlap=overlap,axis=0,boundary=None,padded=False)
            # z shape: frequency, channels, time. Never mono-sum spectral analysis.
            power=np.mean(np.abs(z)**2,axis=(1,2)); total=float(power.sum())
            audible=(f>=20)&(f<=min(20000,sr/2))
            p=power[audible]; freq=f[audible]
            centroid=float(np.sum(freq*p)/p.sum()) if active and p.sum()>1e-16 else None
            flat=float(np.exp(np.mean(np.log(np.maximum(p,1e-20))))/np.mean(p)) if active else None
            band_rows={}; local_contrast=[]
            for name,lo,hi in BANDS:
                mask=(f>=lo)&(f<hi)
                share=float(100*power[mask].sum()/total) if active and total>1e-16 else None
                zz=z[mask]; lr=side=None
                if channels==2 and zz.size and active:
                    l=zz[:,0,:]; r=zz[:,1,:]
                    el=float(np.sum(abs(l)**2)); er=float(np.sum(abs(r)**2))
                    cross=float(np.sum(np.real(l*np.conj(r))))
                    if min(el,er)>1e-16: lr=float(np.clip(cross/np.sqrt(el*er),-1,1))
                    if el+er>1e-16: side=float(100*np.sum(abs((l-r)/2)**2)/((el+er)/2))
                    t=totals.setdefault(name,[0.,0.,0.]);t[0]+=el;t[1]+=er;t[2]+=cross
                bp=power[mask]
                if active and len(bp)>=4 and bp.sum()>1e-16:
                    local_contrast.append(float(10*np.log10((np.quantile(bp,.9)+1e-20)/(np.quantile(bp,.1)+1e-20))))
                band_rows[name]={'energy_pct':share,'correlation':lr,'side_pct':side}
            contrast=float(np.mean(local_contrast)) if local_contrast else None
            if active:
                contrasts.append(contrast);flatness.append(flat);centroids.append(centroid)
            low,state=sosfilt(low_filter,x,axis=0,zi=state)
            lowrms=float(np.sqrt(np.mean(low*low)))
            lowcrest=float(20*np.log10(np.max(abs(low))/lowrms)) if lowrms>1e-8 else None
            peak=float(np.max(abs(x)))
            crest=float(20*np.log10(peak/np.sqrt(energy))) if active else None
            timeline.append({'start_s':index,'end_s':index+len(x)/sr,'active':active,
                'rms_dbfs':dbpower(energy),'crest_db':crest,'centroid_hz':centroid,
                'flatness':flat,'contrast_db':contrast,'low_band_crest_db':lowcrest,'bands':band_rows})
            # 10 ms envelope; keep one entry per real frame including partial last frame.
            hop=max(1,round(sr*.01))
            for start in range(0,len(x),hop):
                frame=x[start:start+hop];envelopes.append((index+start/sr,float(np.sqrt(np.mean(frame*frame)))))
    levels=np.array([20*np.log10(max(e[1],1e-10)) for e in envelopes])
    # Envelope rise and local maxima; not instrument identification or original transient preservation.
    peaks,_=find_peaks(levels,prominence=4,distance=8,height=-60)
    events=[]
    for i in peaks:
        begin=max(0,i-20); segment=levels[begin:i+1]
        valley=begin+int(np.argmin(segment))
        rise=float(levels[i]-levels[valley]); attack=(envelopes[i][0]-envelopes[valley][0])*1000
        if rise>=4 and attack>0:
            events.append({'time_s':round(envelopes[i][0],3),'attack_ms':round(attack,2),'contrast_db':round(rise,2)})
    def median(values):
        valid=[v for v in values if v is not None]
        return float(np.median(valid)) if valid else None
    band_stereo={}
    for name,(el,er,cross) in totals.items():
        band_stereo[name]={'correlation':float(np.clip(cross/np.sqrt(el*er),-1,1)) if min(el,er)>1e-16 else None,
                          'side_pct':float(50*(1-2*cross/(el+er))) if el+er>1e-16 else None}
    return {'timeline':timeline,'band_stereo':band_stereo,'transient_events':events[:200],
        'transient_event_count':len(events),'transient_events_truncated':len(events)>200,
        'attack_median_ms':median([e['attack_ms'] for e in events]),
        'attack_contrast_median_db':median([e['contrast_db'] for e in events]),
        'onsets_per_second':len(events)/max(timeline[-1]['end_s'] if timeline else 1,1),
        'low_band_crest_median_db':median([t['low_band_crest_db'] for t in timeline if t['active']]),
        'spectral_contrast_db':median(contrasts),'spectral_flatness':median(flatness),'spectral_centroid_hz':median(centroids),
        'active_seconds':sum(t['end_s']-t['start_s'] for t in timeline if t['active'])}

def reference_scores(current, reference):
    """Distance to a user-selected recording, not musical-quality scoring."""
    a=current['metrics']; b=reference['metrics']
    if current['engine']!=reference['engine'] or not current['engine'].endswith('/0.2.0'):
        raise ValueError('Reanalise ambas as versões com o mesmo motor 0.2.0.')
    if a['sample_rate_hz'] != b['sample_rate_hz']:
        raise ValueError('Use referências com a mesma taxa de amostragem para comparar o espectro na mesma faixa.')
    if a['silent'] or b['silent']: raise ValueError('Silêncio não é uma referência musical válida.')
    result=[]
    groups={
      'frequencies':[(f'band:{k}',6) for k,_,_ in BANDS],
      'dynamics':[('integrated_lufs',6),('lra_lu',6),('crest_db',6)],
      'stereo':[('lr_correlation',.5),('side_energy_pct',25),('mono_downmix_change_db',6)],
      'clarity':[('spectral_contrast_db',12),('spectral_flatness',.2),('spectral_centroid_hz',3000)],
      'transients':[('attack_median_ms',100),('attack_contrast_median_db',12),('low_band_crest_median_db',8)]}
    for category,keys in groups.items():
        parts=[]
        for key,scale in keys:
            if key.startswith('band:'):
                k=key[5:];av=a['band_energy_pct'].get(k);bv=b['band_energy_pct'].get(k)
                if av is None or bv is None or max(av,bv)<.01: continue
                # Relative band powers: gain-invariant; floor at 0.01% bounds ratios.
                delta=10*math.log10(max(av,.01)/max(bv,.01))
            else:
                av=a.get(key);bv=b.get(key)
                if av is None or bv is None: continue
                delta=av-bv
            parts.append({'metric':key,'current':av,'reference':bv,'delta':delta,'scale':scale,
                          'distance':min(1,abs(delta)/scale)})
        score=round(100*(1-sum(p['distance'] for p in parts)/len(parts))) if parts else None
        result.append({'category':category,'score':score,'components':parts,
                       'coverage':f'{len(parts)}/{len(keys)}','reason':'Proximidade à referência escolhida; 100 = descritores iguais, não qualidade perfeita. Média de distâncias absolutas limitadas a 1; escalas heurísticas publicadas.'})
    return result
