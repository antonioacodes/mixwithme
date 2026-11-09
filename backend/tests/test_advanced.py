import json
import copy
import numpy as np
import pytest
import soundfile as sf
from app.advanced import loudness, descriptors, reference_scores
from app.dsp import analyze
from app.worker import run_one


def tone(path, db=-20, seconds=4, channels=2, rate=48000):
    x=10**(db/20)*np.sin(2*np.pi*1000*np.arange(int(rate*seconds))/rate)
    sf.write(path,np.column_stack([x]*channels),rate,subtype='FLOAT')


@pytest.mark.parametrize('channels,expected',[(1,-23.0),(2,-20.0)])
def test_calibrated_loudness(channels,expected,tmp_path):
    p=tmp_path/'tone.wav';tone(p,channels=channels)
    m=loudness(p,4,False)
    assert m['integrated_lufs']==pytest.approx(expected,abs=.15)
    assert m['true_peak_dbtp']==pytest.approx(-20,abs=.05)
    assert m['lra_lu'] is None


def test_ebu_3342_level_step_lra(tmp_path):
    sr=48000;t=np.arange(sr*20)/sr
    x=np.concatenate([.1*np.sin(2*np.pi*1000*t),10**(-30/20)*np.sin(2*np.pi*1000*t)])
    p=tmp_path/'lra.wav';sf.write(p,np.column_stack([x,x]),sr,subtype='FLOAT')
    m=loudness(p,40,False)
    assert m['lra_lu']==pytest.approx(10,abs=1)


def test_intersample_peak_above_sample_peak(tmp_path):
    sr=48000;x=.9*np.sin(2*np.pi*.25*np.arange(sr*2)+np.pi/4)
    p=tmp_path/'isp.wav';sf.write(p,x,sr,subtype='FLOAT')
    m=loudness(p,2,False)
    assert m['true_peak_dbtp'] > 20*np.log10(abs(x).max())+2


def test_local_phase_and_gain_invariant_descriptors(tmp_path):
    sr=48000;x=.2*np.sin(2*np.pi*1000*np.arange(sr*3)/sr);r=x.copy();r[sr:2*sr]*=-1
    p=tmp_path/'phase.wav';sf.write(p,np.column_stack([x,r]),sr,subtype='FLOAT')
    a=descriptors(p)
    assert a['timeline'][0]['bands']['mid']['correlation']>.99
    assert a['timeline'][1]['bands']['mid']['correlation']<-.99
    assert a['timeline'][1]['bands']['mid']['side_pct']>99
    sf.write(p,np.column_stack([x,r])*.25,sr,subtype='FLOAT');b=descriptors(p)
    assert a['spectral_centroid_hz']==pytest.approx(b['spectral_centroid_hz'],rel=.001)


def test_attack_detector_and_sustained_signal(tmp_path):
    sr=48000;t=np.arange(sr*4)/sr;envelope=np.zeros_like(t)
    for start in (.5,1.5,2.5):
        elapsed=t-start;mask=(elapsed>=0)&(elapsed<.3)
        envelope[mask]=np.exp(-elapsed[mask]*20)
    p=tmp_path/'attacks.wav';sf.write(p,.5*envelope*np.sin(2*np.pi*1000*t),sr,subtype='FLOAT')
    m=descriptors(p)
    assert m['transient_event_count']==3
    assert m['attack_contrast_median_db']>10
    tone(p,seconds=4,channels=1)
    assert descriptors(p)['transient_event_count']==0


def test_reference_distance_and_no_quality_scores(tmp_path,session):
    p=tmp_path/'reference.wav';tone(p)
    a=analyze(p,session)
    assert all(s['score'] is None for s in a['scores'])
    scores=reference_scores(a,a)
    assert all(s['score']==100 for s in scores if s['components'])
    b=copy.deepcopy(a);b['metrics']['spectral_centroid_hz']+=3000
    assert next(s for s in reference_scores(a,b) if s['category']=='clarity')['score']<100
    b['engine']='old'
    with pytest.raises(ValueError):reference_scores(a,b)
    json.dumps(a,allow_nan=False)


def test_reanalysis_history_and_reference_api(client,session,wav):
    tid=client.post('/tracks',json={'title':'Test','session':session}).json()['id']
    ids=[]
    for i in range(2):
        vid=client.post(f'/tracks/{tid}/versions',content=wav,headers={'Content-Type':'audio/wav'}).json()['id']
        run_one(vid);ids.append(vid)
    result=client.get(f'/versions/{ids[0]}/reference/{ids[1]}')
    assert result.status_code==200
    assert len(result.json()['scores'])==5
    assert client.get(f'/versions/{ids[0]}/reference/{ids[0]}').status_code==422
    before=client.get('/versions/'+ids[0]).json()['result']
    assert client.post('/versions/'+ids[0]+'/reanalyze').status_code==202
    assert client.post('/versions/'+ids[0]+'/reanalyze').status_code==409
    assert client.get('/versions/'+ids[0]+'/analysis-history').json()[0]['result']==before
    run_one(ids[0])
    assert client.get('/versions/'+ids[0]).json()['status']=='done'
