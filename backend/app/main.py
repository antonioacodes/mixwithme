import asyncio
import hmac
import json
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .db import connect, data_dir, init
from .models import TrackCreate, Session, Answer
from .dsp import inspect
from .security import RequestGuard

MAX_UPLOAD = 250 * 1024 * 1024
MAX_LIBRARY = 40  # <= 10 GiB of WAVs; reserve slots before accepting bytes


@asynccontextmanager
async def lifespan(app):
    if len(os.environ.get('API_TOKEN', '')) < 32:
        raise RuntimeError('Set API_TOKEN to a random secret of at least 32 characters.')
    init()
    # Deployment runs exactly one API process. Incomplete uploads cannot be resumed.
    with connect() as db:
        interrupted = db.execute("SELECT filename FROM versions WHERE status='uploading'").fetchall()
        db.execute("UPDATE versions SET status='failed',error='Upload interrompido; remova e reenvie.' WHERE status='uploading'")
    for row in interrupted:
        (data_dir()/row['filename']).unlink(missing_ok=True)
    yield


app = FastAPI(title='MixWithMe', lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(RequestGuard)
bearer = HTTPBearer(auto_error=False)


def auth(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    token = os.environ.get('API_TOKEN', '')
    if not token or not credentials or not hmac.compare_digest(credentials.credentials, token):
        raise HTTPException(401, 'Acesso não autorizado.', headers={'WWW-Authenticate': 'Bearer'})


def version_or_404(db, vid):
    row = db.execute('SELECT * FROM versions WHERE id=?', (vid,)).fetchone()
    if not row:
        raise HTTPException(404, 'Versão não encontrada.')
    return row


def serialize(row):
    out = dict(row)
    out.pop('filename', None)
    for key in ('session', 'result'):
        if key in out and out[key]:
            out[key] = json.loads(out[key])
    return out


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/tracks', dependencies=[Depends(auth)])
def tracks():
    with connect() as db:
        return [serialize(r) for r in db.execute('SELECT * FROM tracks ORDER BY created_at DESC')]


@app.post('/tracks', status_code=201, dependencies=[Depends(auth)])
def create_track(body: TrackCreate):
    tid = uuid.uuid4().hex
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT COUNT(*) FROM tracks').fetchone()[0] >= 100:
            raise HTTPException(409, 'Limite de 100 músicas atingido.')
        db.execute('INSERT INTO tracks(id,title,session) VALUES (?,?,?)',
                   (tid, body.title, body.session.model_dump_json()))
    return {'id': tid}


@app.put('/tracks/{tid}/session', dependencies=[Depends(auth)])
def update_session(tid: str, body: Session):
    with connect() as db:
        if not db.execute('UPDATE tracks SET session=? WHERE id=?', (body.model_dump_json(), tid)).rowcount:
            raise HTTPException(404, 'Música não encontrada.')
    return {'saved': True}


@app.get('/tracks/{tid}/versions', dependencies=[Depends(auth)])
def versions(tid: str):
    with connect() as db:
        return [serialize(r) for r in db.execute('SELECT * FROM versions WHERE track_id=? ORDER BY created_at DESC', (tid,))]


@app.post('/tracks/{tid}/versions', status_code=202, dependencies=[Depends(auth)])
async def upload(tid: str, request: Request, label: str = 'Nova versão'):
    if not 1 <= len(label.strip()) <= 80:
        raise HTTPException(422, 'Nome da versão deve ter entre 1 e 80 caracteres.')
    if request.headers.get('content-type', '').split(';')[0] not in ('audio/wav', 'audio/x-wav', 'application/octet-stream'):
        raise HTTPException(415, 'Envie o WAV como corpo binário.')
    vid = uuid.uuid4().hex
    filename = vid + '.wav'
    path = data_dir()/filename
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        track = db.execute('SELECT session FROM tracks WHERE id=?', (tid,)).fetchone()
        if not track:
            raise HTTPException(404, 'Música não encontrada.')
        if db.execute('SELECT COUNT(*) FROM versions WHERE track_id=?', (tid,)).fetchone()[0] >= 5:
            raise HTTPException(409, 'Máximo de cinco WAVs por música. Remova uma versão antes de enviar outra.')
        if db.execute('SELECT COUNT(*) FROM versions').fetchone()[0] >= MAX_LIBRARY:
            raise HTTPException(409, 'Limite local de 40 WAVs atingido.')
        if db.execute("SELECT COUNT(*) FROM versions WHERE status IN ('uploading','queued','running')").fetchone()[0] >= 3:
            raise HTTPException(429, 'Fila cheia: aguarde uma análise terminar.')
        if shutil.disk_usage(data_dir()).free < 2*1024**3:
            raise HTTPException(507, 'Espaço em disco insuficiente.')
        db.execute('INSERT INTO versions(id,track_id,label,session,status,filename) VALUES (?,?,?,?,?,?)',
                   (vid, tid, label.strip(), track['session'], 'uploading', filename))
    try:
        async def receive():
            size = 0
            with path.open('xb') as f:
                os.chmod(path, 0o600)
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        raise HTTPException(413, 'Limite de 250 MiB por WAV.')
                    f.write(chunk)
        await asyncio.wait_for(receive(), timeout=120)
        await asyncio.to_thread(inspect, path)
        with connect() as db:
            db.execute("UPDATE versions SET status='queued' WHERE id=?", (vid,))
    except BaseException as exc:
        path.unlink(missing_ok=True)
        with connect() as db:
            db.execute('DELETE FROM versions WHERE id=?', (vid,))
        if isinstance(exc, HTTPException):
            raise
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
            raise HTTPException(408, 'Upload excedeu 120 segundos.') from exc
        if isinstance(exc, (ValueError, RuntimeError)):
            raise HTTPException(422, 'WAV inválido: verifique formato, duração e canais.') from exc
        raise
    return {'id': vid, 'status': 'queued'}


@app.get('/versions/{vid}', dependencies=[Depends(auth)])
def get_version(vid: str):
    with connect() as db:
        out = serialize(version_or_404(db, vid))
        out['answers'] = [dict(r) for r in db.execute('SELECT question_id,answer,updated_at FROM answers WHERE version_id=?', (vid,))]
        return out


@app.get('/versions/{vid}/audio', dependencies=[Depends(auth)])
def audio(vid: str):
    with connect() as db:
        row = version_or_404(db, vid)
    path = data_dir()/row['filename']
    if row['status'] == 'uploading' or not path.exists():
        raise HTTPException(409, 'Áudio indisponível.')
    return FileResponse(path, media_type='audio/wav', headers={'Cache-Control': 'no-store'})


@app.delete('/versions/{vid}', dependencies=[Depends(auth)])
def delete_version(vid: str):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = version_or_404(db, vid)
        if row['status'] in ('running', 'uploading'):
            raise HTTPException(409, 'Aguarde o trabalho ativo terminar.')
        (data_dir()/row['filename']).unlink(missing_ok=True)
        db.execute('DELETE FROM versions WHERE id=?', (vid,))
    return {'deleted': True}


@app.post('/versions/{vid}/answers', dependencies=[Depends(auth)])
def answer(vid: str, body: Answer):
    with connect() as db:
        row = version_or_404(db, vid)
        result = json.loads(row['result'] or '{}')
        if body.question_id not in {h['id'] for h in result.get('hypotheses', [])}:
            raise HTTPException(422, 'Pergunta não pertence a esta análise.')
        db.execute("INSERT INTO answers(version_id,question_id,answer) VALUES (?,?,?) ON CONFLICT(version_id,question_id) DO UPDATE SET answer=excluded.answer,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')",
                   (vid, body.question_id, body.answer))
    return {'saved': True, 'notice': 'Resposta registrada como relato do usuário; não altera a medição nem confirma a hipótese automaticamente.'}


@app.get('/tracks/{tid}/compare', dependencies=[Depends(auth)])
def compare(tid: str, a: str, b: str):
    with connect() as db:
        rows = [version_or_404(db, vid) for vid in (a, b)]
    if a == b or any(r['track_id'] != tid or r['status'] != 'done' for r in rows):
        raise HTTPException(422, 'Escolha duas versões analisadas da mesma música.')
    results = [json.loads(r['result']) for r in rows]
    keys = ('sample_peak_dbfs', 'rms_dbfs', 'crest_db', 'lr_correlation', 'mono_downmix_change_db', 'integrated_lufs', 'true_peak_dbtp', 'lra_lu', 'spectral_contrast_db', 'spectral_flatness', 'spectral_centroid_hz', 'attack_median_ms', 'attack_contrast_median_db', 'low_band_crest_median_db')
    changes = {}
    for k in keys:
        av, bv = [r['metrics'].get(k) for r in results]
        changes[k] = {'a': av, 'b': bv, 'delta_b_minus_a': bv-av if av is not None and bv is not None else None}
    return {'a': a, 'b': b, 'changes': changes,
            'warning': 'B − A, sem alinhamento temporal ou normalização. Diferença não significa melhora. Compare trechos equivalentes e iguale loudness na DAW.',
            'same_engine': results[0]['engine'] == results[1]['engine'],
            'duration_difference_s': results[1]['metrics']['duration_s']-results[0]['metrics']['duration_s']}


@app.post('/versions/{vid}/reanalyze', status_code=202, dependencies=[Depends(auth)])
def reanalyze(vid: str):
    """Keep the previous report as an audit record; reuse the original WAV/session."""
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=version_or_404(db,vid)
        if row['status'] not in ('done','failed'):
            raise HTTPException(409,'Esta versão já está em processamento.')
        if not (data_dir()/row['filename']).is_file():
            raise HTTPException(409,'WAV original indisponível.')
        if db.execute("SELECT COUNT(*) FROM versions WHERE status IN ('uploading','queued','running')").fetchone()[0]>=3:
            raise HTTPException(429,'Fila cheia; aguarde uma análise terminar.')
        if db.execute('SELECT COUNT(*) FROM analysis_history WHERE version_id=?',(vid,)).fetchone()[0]>=10:
            raise HTTPException(409,'Limite de dez revisões de análise nesta versão.')
        if row['result']:
            answers=[dict(a) for a in db.execute('SELECT question_id,answer,updated_at FROM answers WHERE version_id=?',(vid,))]
            db.execute('INSERT INTO analysis_history(version_id,result,answers) VALUES (?,?,?)',(vid,row['result'],json.dumps(answers)))
        db.execute("UPDATE versions SET status='queued',error=NULL WHERE id=?",(vid,))
    return {'id':vid,'status':'queued'}


@app.get('/versions/{vid}/analysis-history', dependencies=[Depends(auth)])
def analysis_history(vid: str):
    with connect() as db:
        version_or_404(db,vid)
        return [{'created_at':r['created_at'],'result':json.loads(r['result']),'answers':json.loads(r['answers'])} for r in db.execute('SELECT created_at,result,answers FROM analysis_history WHERE version_id=? ORDER BY id DESC',(vid,))]


@app.get('/versions/{vid}/reference/{reference_id}', dependencies=[Depends(auth)])
def compare_reference(vid: str, reference_id: str):
    from .advanced import reference_scores
    if vid==reference_id: raise HTTPException(422,'Escolha outra versão como referência.')
    with connect() as db:
        current=version_or_404(db,vid); reference=version_or_404(db,reference_id)
    if current['status']!='done' or reference['status']!='done':
        raise HTTPException(409,'As duas versões precisam estar analisadas.')
    a=json.loads(current['result']); b=json.loads(reference['result'])
    try: scores=reference_scores(a,b)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    differences=[]
    for part in scores[0]['components']:
        if abs(part['delta'])>=3:
            differences.append({'band':part['metric'][5:],'delta_db':part['delta'],
                'recommendation':'Compare esta faixa por escuta com volume igualado; ajuste primeiro a fonte na DAW. A diferença é de proporção de energia e não é um valor de EQ a aplicar.'})
    return {'reference_id':reference_id,'reference_label':reference['label'],'scores':scores,
        'frequency_differences':differences,
        'duration_difference_s':a['metrics']['duration_s']-b['metrics']['duration_s'],
        'listening_gain_db':b['metrics']['integrated_lufs']-a['metrics']['integrated_lufs'] if a['metrics'].get('integrated_lufs') is not None and b['metrics'].get('integrated_lufs') is not None else None,
        'warning':'Referência escolhida por você. Sem alinhamento temporal ou alteração do áudio. Compare arranjos e trechos equivalentes; proximidade não implica melhora. O ganho sugerido é apenas para comparação na DAW e pode causar clipping se aplicado sem margem.'}
