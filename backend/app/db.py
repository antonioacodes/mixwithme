import os
import sqlite3
from pathlib import Path


def data_dir():
    p = Path(os.environ.get('DATA_DIR', './data')).resolve()
    p.mkdir(mode=0o700, parents=True, exist_ok=True)
    return p


def connect():
    db = sqlite3.connect(data_dir() / 'mixwithme.sqlite3', timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=15000')
    return db


def init():
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS tracks (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, session TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
        CREATE TABLE IF NOT EXISTS versions (
          id TEXT PRIMARY KEY, track_id TEXT NOT NULL REFERENCES tracks(id),
          label TEXT NOT NULL, session TEXT NOT NULL, status TEXT NOT NULL,
          filename TEXT NOT NULL, reference_filename TEXT, result TEXT, error TEXT,
          created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
        CREATE TABLE IF NOT EXISTS analysis_history (
          id INTEGER PRIMARY KEY, version_id TEXT NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
          result TEXT NOT NULL, answers TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
        CREATE INDEX IF NOT EXISTS versions_track ON versions(track_id);
        CREATE TABLE IF NOT EXISTS answers (
          version_id TEXT NOT NULL REFERENCES versions(id) ON DELETE CASCADE,
          question_id TEXT NOT NULL, answer TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
          PRIMARY KEY(version_id, question_id));
        ''')
        columns = {r[1] for r in db.execute('PRAGMA table_info(versions)')}
        if 'reference_filename' not in columns:
            db.execute('ALTER TABLE versions ADD COLUMN reference_filename TEXT')
        track_columns = {r[1] for r in db.execute('PRAGMA table_info(tracks)')}
        if 'flp_filename' not in track_columns:
            db.execute('ALTER TABLE tracks ADD COLUMN flp_filename TEXT')
        if 'flp_context' not in track_columns:
            db.execute('ALTER TABLE tracks ADD COLUMN flp_context TEXT')
