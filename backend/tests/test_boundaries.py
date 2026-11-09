import numpy as np
import soundfile as sf
from app.dsp import analyze
from app.models import Session
from pydantic import ValidationError
import pytest


def test_single_sample_tail(tmp_path,session):
    path=tmp_path/'tail.wav'
    sf.write(path,np.ones(48001)*.1,48000,subtype='FLOAT')
    assert analyze(path,session)['metrics']['duration_s']==48001/48000


def test_bus_cycle_and_disconnected_channel(session):
    session['channels'].append({'id':'bus','name':'Bus','kind':'bus'})
    session['routes']=[{'source':'vocal','target':'bus'},{'source':'bus','target':'vocal'}]
    with pytest.raises(ValidationError):Session(**session)
    session['routes']=[{'source':'vocal','target':'master'}]
    with pytest.raises(ValidationError):Session(**session)
