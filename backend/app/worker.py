"""One persistent SQLite worker; each DSP task runs in a disposable CPU process."""
import fcntl
import json
import os
import subprocess
import sys
import time
from .db import connect, data_dir, init


def run_one(vid):
    from .dsp import analyze
    with connect() as db:
        row = db.execute('SELECT * FROM versions WHERE id=?', (vid,)).fetchone()
    result = analyze(data_dir()/row['filename'], json.loads(row['session']))
    with connect() as db:
        db.execute("UPDATE versions SET status='done',result=?,error=NULL WHERE id=?", (json.dumps(result, allow_nan=False), vid))


def serve():
    init()
    with (data_dir()/'worker.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another worker is already running.')
        with connect() as db:
            db.execute("UPDATE versions SET status='queued' WHERE status='running'")
        while True:
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute("SELECT id FROM versions WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
                if row:
                    db.execute("UPDATE versions SET status='running' WHERE id=?", (row['id'],))
            if not row:
                time.sleep(1)
                continue
            error = None
            try:
                completed = subprocess.run([sys.executable, '-m', 'app.worker', '--one', row['id']],
                    timeout=180, capture_output=True, env={**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
                if completed.returncode:
                    error = 'Não foi possível analisar este WAV. Verifique os dados e reenvie.'
            except subprocess.TimeoutExpired:
                error = 'Análise excedeu o limite de 180 segundos.'
            if error:
                with connect() as db:
                    db.execute("UPDATE versions SET status='failed',error=? WHERE id=?", (error, row['id']))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--one':
        run_one(sys.argv[2])
    else:
        serve()
