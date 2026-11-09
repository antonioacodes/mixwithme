import copy
import io
import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient
from app.main import app

SESSION = {
    'daw':'FL Studio','bpm':140,'stage':'mix','beat_source':'stereo',
    'beat_already_limited':'unknown','export_sample_rate':48000,'export_bit_depth':'24',
    'listening_setup':'Headphones','intent':'Test vocal presence',
    'channels':[
        {'id':'vocal','name':'Vocal','kind':'vocal','fader_db':0,'pan':0,'width':1,'plugins':[]},
        {'id':'master','name':'Master','kind':'master','fader_db':0,'pan':0,'width':1,'plugins':[]}
    ],'routes':[{'source':'vocal','target':'master','kind':'output','gain_db':0}]
}


@pytest.fixture
def session():
    return copy.deepcopy(SESSION)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('API_TOKEN', 'a'*40)
    with TestClient(app) as c:
        c.headers['Authorization'] = 'Bearer ' + 'a'*40
        yield c


@pytest.fixture
def wav():
    t = np.arange(48000*2)/48000
    x = .5*np.sin(2*np.pi*1000*t)
    out = io.BytesIO()
    sf.write(out, np.column_stack([x,x]),48000,format='WAV',subtype='PCM_24')
    return out.getvalue()
