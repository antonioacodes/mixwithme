import json
import numpy as np
import pytest
import soundfile as sf
from app.dsp import analyze, inspect


def test_sine_calibration_and_spectral_band(tmp_path, wav, session):
    path = tmp_path/'tone.wav'
    path.write_bytes(wav)
    r = analyze(path, session)
    m = r['metrics']
    assert m['sample_peak_dbfs'] == pytest.approx(-6.0206, abs=.001)
    assert m['rms_dbfs'] == pytest.approx(-9.0309, abs=.001)
    assert m['crest_db'] == pytest.approx(3.0103, abs=.001)
    assert m['lr_correlation'] == pytest.approx(1)
    assert m['mono_downmix_change_db'] == pytest.approx(0)
    assert m['band_energy_pct']['mid'] > 99.9
    assert m['integrated_lufs'] == pytest.approx(-6.05, abs=.15)
    assert m['true_peak_dbtp'] == pytest.approx(-6.02, abs=.05)
    json.dumps(r, allow_nan=False)


def test_antiphase_keeps_spectrum_and_flags_mono(tmp_path, session):
    x=.5*np.sin(2*np.pi*1000*np.arange(48000)/48000)
    path=tmp_path/'anti.wav'
    sf.write(path,np.column_stack([x,-x]),48000,subtype='FLOAT')
    r=analyze(path,session)
    assert r['metrics']['lr_correlation']==pytest.approx(-1)
    assert r['metrics']['mono_downmix_change_db']==pytest.approx(-120)
    assert r['metrics']['band_energy_pct']['mid']>99.9
    assert 'phase-mid' in [h['id'] for h in r['hypotheses']]


@pytest.mark.parametrize('channels',[1,2])
def test_silence_does_not_receive_good_scores(tmp_path,session,channels):
    path=tmp_path/'silence.wav'
    sf.write(path,np.zeros((48000,channels)),48000,subtype='PCM_24')
    r=analyze(path,session)
    assert r['metrics']['silent']
    assert r['metrics']['sample_peak_dbfs'] is None
    assert all(s['score'] is None for s in r['scores'])
    json.dumps(r,allow_nan=False)


def test_nonfinite_audio_rejected(tmp_path,session):
    path=tmp_path/'bad.wav'
    x=np.zeros(48000);x[10]=np.nan
    sf.write(path,x,48000,subtype='FLOAT')
    with pytest.raises(ValueError): analyze(path,session)


def test_dc_and_missing_stereo_are_not_misrepresented(tmp_path,session):
    path=tmp_path/'dc.wav'
    sf.write(path,np.ones(48000)*.25,48000,subtype='FLOAT')
    r=analyze(path,session)
    assert r['metrics']['lr_correlation'] is None
    assert r['metrics']['dc_offset']==pytest.approx([.25])
    assert r['metrics']['band_energy_pct']['mid']<.001


@pytest.mark.parametrize('samples,channels,subtype',[(100,2,'PCM_24'),(48000,3,'PCM_24'),(48000,2,'PCM_32')])
def test_invalid_audio_formats(tmp_path,samples,channels,subtype):
    path=tmp_path/'bad.wav'
    sf.write(path,np.zeros((samples,channels)),48000,subtype=subtype)
    with pytest.raises(ValueError):inspect(path)
