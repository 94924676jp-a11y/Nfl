"""Immutable board storage, an append-only index, and a `latest` pointer.

THE HISTORY IS THE RECORD; THE POINTER IS A CONVENIENCE.

Every board ever generated is written once, into a directory named by the
instant it was written and the run that produced it, and never touched again.
`LATEST.json` exists only so a person does not have to sort filenames -- it
holds no content of its own, and losing it would cost nothing but convenience.
That asymmetry is the whole design: a mutable pointer over an immutable set is
safe, and a mutable board would not be.

THE ORCHESTRATOR MAY WRITE NOWHERE ELSE. Every path this module produces is
under `nfl/product/boards/`, which contains no capture artifact, no governance
state and no model code. A product run that fails, hangs or writes garbage
cannot reach the capture or G0A workflows, because it has no path into them.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[2]
ROOT = _REPO / 'nfl' / 'product' / 'boards'
INDEX = ROOT / 'INDEX.jsonl'

# Everything the orchestrator is allowed to touch lives under this one
# directory. Asserted by the suite, not merely intended.
WRITABLE_ROOT = ROOT


class BoardExists(RuntimeError):
    """A generated board is never overwritten. Named, so a caller cannot
    mistake the refusal for an ordinary failure and retry over the top."""


def _compact(ts: str) -> str:
    d = dt.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
    return d.strftime('%Y%m%dT%H%M%SZ')


def board_dir(game_id: str, written_at: str, run_id: str) -> pathlib.Path:
    """Where this board lives. The name carries WHEN and WHICH RUN, so two
    boards can never collide unless they are the same board."""
    return ROOT / game_id / f'{_compact(written_at)}__{run_id}'


def input_fingerprint(information_set: dict) -> str:
    """One hash over the exact vintages a board would consume.

    THIS IS WHAT MAKES A REFRESH HONEST. Two runs whose fingerprints match
    have identical inputs, so a second board would be the first board with a
    newer timestamp on it -- a stale input restamped as fresh. The fingerprint
    covers each source's content hash AND its observation time, so neither a
    changed file nor a re-observation of the same file can pass unnoticed.
    """
    src = information_set.get('sources') or {}
    payload = sorted((name, rec['sha256'], rec['observed_at'])
                     for name, rec in src.items())
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()


def write(game_id, written_at, run_id, files: dict, meta: dict):
    """Write one board, once. Refuses if the directory already exists."""
    d = board_dir(game_id, written_at, run_id)
    if d.exists():
        raise BoardExists(
            f'BOARD_ALREADY_EXISTS: {d}. A generated board is immutable; a '
            f'refresh writes a NEW directory rather than replacing this one.')
    d.mkdir(parents=True)
    seal = []
    for name, data in sorted(files.items()):
        p = d / name
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
        seal.append(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {name}')
    (d / 'SEAL_SHA256.txt').write_text('\n'.join(seal) + '\n')
    (d / 'PROTOCOL_RECORD.json').write_text(
        json.dumps({**meta, 'immutable': True,
                    'board_dir': str(d.relative_to(_REPO))},
                   indent=1, sort_keys=True, default=str))
    return d


def append_index(row: dict) -> int:
    """Append-only. The index is a log of what happened, not a view that can
    be rebuilt to say something else."""
    ROOT.mkdir(parents=True, exist_ok=True)
    with open(INDEX, 'a') as fh:
        fh.write(json.dumps(row, sort_keys=True, default=str) + '\n')
    return 1


def read_index(game_id=None) -> list:
    if not INDEX.exists():
        return []
    rows = [json.loads(x) for x in INDEX.read_text().splitlines() if x.strip()]
    return [r for r in rows if not game_id or r.get('game_id') == game_id]


def set_latest(game_id: str, row: dict):
    """The pointer. Rewritten freely; it carries no content of its own."""
    p = ROOT / game_id
    p.mkdir(parents=True, exist_ok=True)
    (p / 'LATEST.json').write_text(
        json.dumps({**row,
                    'note': 'A POINTER, NOT A BOARD. The board it names is '
                            'immutable; this file is a convenience and may be '
                            'regenerated from INDEX.jsonl at any time.'},
                   indent=1, sort_keys=True, default=str))


def latest(game_id: str):
    p = ROOT / game_id / 'LATEST.json'
    return json.loads(p.read_text()) if p.exists() else None


def rebuild_latest(game_id: str):
    """Regenerate the pointer from the log, proving it holds nothing unique."""
    rows = [r for r in read_index(game_id) if r.get('status') == 'WRITTEN']
    if not rows:
        return None
    row = max(rows, key=lambda r: r['written_at'])
    set_latest(game_id, row)
    return row
