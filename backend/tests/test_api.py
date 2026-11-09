import copy
from concurrent.futures import ThreadPoolExecutor
from app.db import connect
from app.worker import run_one


def create(client, session):
    r=client.post('/tracks',json={'title':'Diamonds','session':session})
    assert r.status_code==201,r.text
    return r.json()['id']


def upload(client,tid,wav):
    return client.post(f'/tracks/{tid}/versions?label=v1',content=wav,headers={'Content-Type':'audio/wav'})


def test_authentication_and_required_context(client,session):
    assert client.get('/tracks',headers={'Authorization':'Bearer wrong'}).status_code==401
    assert client.post('/tracks',json={'title':'No context'}).status_code==422
    bad=copy.deepcopy(session);bad['bpm']=0
    assert client.post('/tracks',json={'title':'Bad','session':bad}).status_code==422
    assert client.post('/tracks',content=b'x'*600000).status_code==413
    assert client.post('/tracks',content=b'invalid json',headers={'Authorization':'Bearer wrong'}).status_code==401


def test_cycle_and_duplicate_routing_rejected(client,session):
    session['routes'][0]['target']='vocal'
    assert client.post('/tracks',json={'title':'Cycle','session':session}).status_code==422
    session['routes'][0]['target']='master'
    session['routes'].append(session['routes'][0])
    assert client.post('/tracks',json={'title':'Duplicate','session':session}).status_code==422


def test_version_snapshot_analysis_answers_compare_delete(client,session,wav):
    tid=create(client,session)
    r=upload(client,tid,wav);assert r.status_code==202,r.text
    a=r.json()['id'];run_one(a)
    session['daw']='Reaper'
    assert client.put(f'/tracks/{tid}/session',json=session).status_code==200
    b=upload(client,tid,wav).json()['id'];run_one(b)
    v=client.get('/versions/'+a).json()
    assert v['session']['daw']=='FL Studio'
    assert v['status']=='done'
    assert client.get('/versions/'+b).json()['session']['daw']=='Reaper'
    question=v['result']['hypotheses'][0]['id']
    assert client.post(f'/versions/{a}/answers',json={'question_id':question,'answer':'Não sei'}).status_code==200
    assert client.post(f'/versions/{a}/answers',json={'question_id':question,'answer':'3 dB'}).status_code==200
    assert len(client.get('/versions/'+a).json()['answers'])==1
    assert client.post(f'/versions/{a}/answers',json={'question_id':'fake','answer':'test'}).status_code==422
    comparison=client.get(f'/tracks/{tid}/compare?a={a}&b={b}').json()
    assert comparison['changes']['rms_dbfs']['delta_b_minus_a']==0
    assert client.get(f'/versions/{a}/audio').content==wav
    other=create(client,session)
    assert client.get(f'/tracks/{other}/compare?a={a}&b={b}').status_code==422
    assert client.delete('/versions/'+a).status_code==200
    assert client.get('/versions/'+a).status_code==404


def test_five_version_limit_including_race(client,session,wav):
    tid=create(client,session)
    for _ in range(4):
        vid=upload(client,tid,wav).json()['id'];run_one(vid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:upload(client,tid,wav).status_code,range(2)))
    assert sorted(results)==[202,409]
    assert len(client.get(f'/tracks/{tid}/versions').json())==5


def test_queue_limit_and_invalid_wav_cleanup(client,session,wav):
    tid=create(client,session)
    assert upload(client,tid,b'not wav').status_code==422
    assert client.get(f'/tracks/{tid}/versions').json()==[]
    for _ in range(3): assert upload(client,tid,wav).status_code==202
    assert upload(client,tid,wav).status_code==429


def test_upload_size_limit_cleanup(client,session,wav,monkeypatch):
    monkeypatch.setattr('app.main.MAX_UPLOAD',100)
    tid=create(client,session)
    assert upload(client,tid,wav).status_code==413
    assert client.get(f'/tracks/{tid}/versions').json()==[]


def test_running_version_cannot_be_deleted(client,session,wav):
    tid=create(client,session);vid=upload(client,tid,wav).json()['id']
    with connect() as db:db.execute("UPDATE versions SET status='running' WHERE id=?",(vid,))
    assert client.delete('/versions/'+vid).status_code==409
