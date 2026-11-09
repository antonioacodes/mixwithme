"""Bounded-memory measurements of the submitted mix; never infer isolated stems."""
import hashlib
import numpy as np
import soundfile as sf
from scipy.signal import welch

ENGINE = 'mixwithme-dsp/0.1.0'
BANDS = [('sub', 20, 60), ('bass', 60, 250), ('low_mid', 250, 500),
         ('mid', 500, 2000), ('presence', 2000, 6000), ('air', 6000, 20001)]


def db(value):
    return float(20 * np.log10(value)) if value > 1e-12 else None


def inspect(path):
    info = sf.info(path)
    if info.format not in ('WAV', 'WAVEX') or info.subtype not in ('PCM_16', 'PCM_24', 'FLOAT'):
        raise ValueError('Envie WAV PCM 16/24 bits ou float 32 bits.')
    if info.channels not in (1, 2) or not 8000 <= info.samplerate <= 96000:
        raise ValueError('Aceitamos mono/estéreo entre 8 e 96 kHz.')
    if not 1 <= info.duration <= 600:
        raise ValueError('A duração deve estar entre 1 segundo e 10 minutos.')
    return info


def analyze(path, session):
    info = inspect(path)
    total = 0
    sums = np.zeros(info.channels)
    squares = np.zeros(info.channels)
    cross = 0.0
    mid_power = side_power = 0.0
    peak = 0.0
    full_scale = 0
    powers = np.zeros(len(BANDS))
    spectrum_total = 0.0
    windows = []
    crest_windows = []
    # One second per block: <2 MB of audio even at the maximum sample rate.
    with sf.SoundFile(path) as audio:
        for x in audio.blocks(blocksize=info.samplerate, dtype='float64', always_2d=True):
            if not np.isfinite(x).all() or np.max(np.abs(x)) > 16:
                raise ValueError('WAV contém valores não finitos ou amplitude fora do limite de segurança.')
            n = len(x)
            total += n
            sums += x.sum(axis=0)
            squares += (x*x).sum(axis=0)
            block_peak = float(np.max(np.abs(x)))
            peak = max(peak, block_peak)
            full_scale += int(np.sum(np.abs(x) >= 1.0 - 1/32768))
            rms = float(np.sqrt(np.mean(x*x)))
            windows.append(rms)
            if rms > 1e-12:
                crest_windows.append(float(20*np.log10(block_peak/rms)))
            if info.channels == 2:
                cross += float(np.sum(x[:, 0]*x[:, 1]))
                mid_power += float(np.sum(((x[:, 0]+x[:, 1])/2)**2))
                side_power += float(np.sum(((x[:, 0]-x[:, 1])/2)**2))
            if n < 2:
                continue  # Last single sample participates in RMS/peak, not the spectral estimate.
            # Average channel powers, NOT mono sum: anti-phase content must remain visible.
            f, psd = welch(x, fs=info.samplerate, window='hann', nperseg=min(4096, n),
                           detrend=False, scaling='density', axis=0)
            p = np.mean(psd, axis=1)
            df = f[1] - f[0]
            spectrum_total += float(p.sum()*df*n)
            for i, (_, lo, hi) in enumerate(BANDS):
                powers[i] += float(p[(f >= lo) & (f < hi)].sum()*df*n)
    if total != info.frames:
        raise ValueError('Arquivo incompleto: número de amostras decodificadas difere do cabeçalho.')
    rms = float(np.sqrt(squares.sum()/(total*info.channels)))
    silent = rms < 1e-8
    correlation = None
    mono_loss = None
    if info.channels == 2 and not silent:
        variance = squares - sums*sums/total
        denom = float(np.sqrt(max(0, variance[0])*max(0, variance[1])))
        if denom > 1e-12:
            correlation = float(np.clip((cross-sums[0]*sums[1]/total)/denom, -1, 1))
        original = float(squares.sum()/2)
        mono_loss = float(10*np.log10(max(mid_power/original, 1e-12)))
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    metrics = {
        'duration_s': info.duration, 'sample_rate_hz': info.samplerate,
        'channels': info.channels, 'subtype': info.subtype, 'silent': silent,
        'sample_peak_dbfs': db(peak), 'rms_dbfs': db(rms),
        'crest_db': float(20*np.log10(peak/rms)) if not silent else None,
        'near_full_scale_pct': 100*full_scale/(total*info.channels),
        'dc_offset': [float(s/total) for s in sums],
        'lr_correlation': correlation, 'mono_downmix_change_db': mono_loss,
        'side_energy_pct': 100*side_power/(mid_power+side_power) if mid_power+side_power > 1e-12 else None,
        'band_energy_pct': {name: float(100*p/spectrum_total) if spectrum_total > 1e-12 else None
                            for (name, _, _), p in zip(BANDS, powers)},
        'window_rms_dbfs': [db(r) for r in windows],
        'window_crest_median_db': float(np.median(crest_windows)) if crest_windows else None,
        'integrated_lufs': None, 'true_peak_dbtp': None,
    }
    hypotheses = []
    def hypothesis(key, text, evidence, question, confidence='low'):
        hypotheses.append({'id': key, 'hypothesis': text, 'evidence': evidence,
                           'confidence': confidence, 'question': question})
    if peak >= 1-1/32768:
        hypothesis('peak', 'Amostras próximas de full scale merecem revisão; isso não prova clipping audível.',
                   f'{metrics["near_full_scale_pct"]:.5f}% das amostras ≥ −0,00027 dBFS.',
                   'Há limiter/clipper no master? Qual o ceiling e a redução de ganho máxima?')
    if correlation is not None and correlation < 0:
        hypothesis('mono', 'Há energia anticorrelacionada no mix. Confira a compatibilidade mono.',
                   f'Correlação L/R {correlation:.3f}; downmix mono {mono_loss:.2f} dB.',
                   'Ao ouvir em mono, algum elemento perde presença? Há expansores de estéreo?')
    if not silent and metrics['crest_db'] < 6:
        hypothesis('crest', 'Crest factor baixo pode refletir arranjo denso, limitação ou compressão.',
                   f'Pico/RMS global: {metrics["crest_db"]:.2f} dB.',
                   'O beat já veio limitado? Quanto os compressores e limiters reduzem nos trechos mais fortes?')
    for channel in session['channels']:
        active = [p for p in channel['plugins'] if not p['bypass']]
        compressors = [p['name'] for p in active if p['kind'] in ('compressor', 'limiter')]
        if len(compressors) >= 2:
            hypothesis('chain-'+channel['id'], f'{channel["name"]}: estágios de dinâmica em série podem compartilhar o trabalho.',
                       'Cadeia declarada: ' + ' → '.join(compressors) + '. Não há medição isolada deste canal.',
                       'Qual a redução de ganho aproximada em cada estágio? Pode responder “não sei”.')
        for i in range(len(active)-1):
            if active[i]['kind'] == 'compressor' and active[i+1]['kind'] == 'eq':
                hypothesis('order-'+channel['id'], f'{channel["name"]}: a posição do EQ muda o sinal que aciona o compressor.',
                           'Compressor antes de EQ na cadeia informada; ambas as ordens podem ser válidas.',
                           'O EQ está corrigindo ressonâncias ou definindo timbre? Um teste A/B com ganho igualado ajuda?')
                break
    if not hypotheses:
        hypothesis('intent', 'Os indicadores implementados não apontaram um alerta específico; isso não confirma qualidade perceptiva.',
                   'Análise global do WAV; sem acesso aos canais da sessão.',
                   'Qual trecho e elemento você gostaria de investigar ao ouvir?')
    scores = []
    for category, value, reason in [
        ('frequencies', None, 'Distribuição espectral é descritiva; não existe curva TRAP universal.'),
        ('dynamics', None if silent else (50 if peak >= 1-1/32768 else 100), 'Triagem de sample peak: 50 se há amostras próximas de full scale; 100 caso contrário. Não avalia loudness ou compressão.'),
        ('stereo', None if correlation is None else (50 if correlation < 0 else 100), 'Triagem global: 50 se correlação negativa; 100 caso contrário. Não garante compatibilidade mono em cada trecho.'),
        ('clarity', None, 'Clareza e mascaramento de elementos exigem escuta; mix estéreo não identifica causas por canal.'),
        ('transients', None, 'Crest factor é um proxy global; não permite pontuar ataques de kick ou snare isoladamente.'),
    ]:
        scores.append({'category': category, 'score': value, 'provisional': True, 'reason': reason})
    warnings = ['Sem separação de stems, processamento corretivo ou julgamento perceptivo automático.',
                'LUFS e true peak não implementados. Sample peak não detecta picos intersample.',
                'Pontuações são triagens heurísticas, não notas de qualidade. Nulo significa evidência insuficiente.',
                'Mixer e plugins são contexto declarado; não são aplicados ao WAV.']
    if silent:
        warnings.append('Silêncio ou sinal quase nulo: não há base para avaliação musical.')
    declared_subtype = {'16': 'PCM_16', '24': 'PCM_24', '32-float': 'FLOAT'}[session['export_bit_depth']]
    if info.samplerate != session['export_sample_rate'] or info.subtype != declared_subtype:
        warnings.append('O formato detectado difere do contexto declarado. As medições usam o arquivo real.')
    return {'engine': ENGINE, 'sha256': digest.hexdigest(), 'metrics': metrics,
            'scores': scores, 'hypotheses': hypotheses, 'warnings': warnings,
            'methods': {'spectrum': 'Welch/Hann 4096 samples, 50% overlap within 1 s blocks; channel-power mean; duration weighted; shares of all-bin power.',
                        'rms': 'Unweighted, all samples and channels. dBFS = 20 log10(amplitude).',
                        'stereo': 'Pearson L/R, DC removed; mono=(L+R)/2; energy relative to mean L/R power.',
                        'transients': 'Median of per-second peak/RMS crest; no event detection.'}}
