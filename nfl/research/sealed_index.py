"""Every sealed forecast this project holds, whatever namespace it lives in.

THE DEFECT THIS MODULE EXISTS FOR.

On 2026-09-11 a live-game review asserted that NE@SEA "was NEVER FORECAST".
That was false. `nfl/research/shadow/g1_ne_sea/` held a V1_CANDIDATE forecast
sealed before the outcome was opened (commit bba6f0b) and scored against the
realised game (commit 604eaac). Both were committed, both were still in the
working tree, and both were invisible to the evaluator.

The cause was DISCOVERY, with a namespace-migration component, and nothing
else. The artifact had not been deleted, moved out of git, or left on another
branch. `research.daily_board.discover` simply hard-coded one root
(`nfl/research/live/`) and one label grammar
(`{pre,post}_inactives_V1_CANDIDATE[_R<n>]`), and the shadow artifact matched
neither: a different root, no cutoff/candidate label, files at the top of the
directory, `SEALED_FORECAST.json` beside `forecast_artifact.json` rather than
a `board.json`.

So the evidence base silently shrank by one game out of two, and absence of a
match was reported as absence of a forecast. A prospective ledger that can
only see the namespace currently in fashion will keep doing that every time a
layout changes.

THE RULE THIS ENCODES. Discovery is by CONTENT, not by path convention. A
directory is a sealed forecast if it carries a recognisable sealed artifact,
wherever it sits, and every namespace this project has ever used is searched.
Adding a namespace here is how a migration stays non-destructive.
"""
from __future__ import annotations

import gzip
import io
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

SPEC_VERSION = 'sealed-index-1'

# Every namespace that has ever held a sealed forecast. Append, never replace:
# removing one is how a historical artifact becomes undiscoverable again.
NAMESPACES = (
    ('live', _REPO / 'nfl' / 'research' / 'live'),
    ('shadow', _REPO / 'nfl' / 'research' / 'shadow'),
    ('product', _REPO / 'nfl' / 'product' / 'boards'),
)

# Any one of these marks a directory as a sealed forecast.
SEAL_MARKERS = ('board.json', 'SEALED_FORECAST.json', 'forecast_artifact.json')


def _read_json(p):
    try:
        return json.loads(p.read_text())
    except Exception:                                        # noqa: BLE001
        return {}


def load_draws(d: pathlib.Path):
    """Stored draws for a sealed directory, plain or gzipped."""
    for name in ('player_draws.npz', 'player_draws.npz.gz'):
        p = d / name
        if not p.exists():
            continue
        import numpy as np
        if p.suffix == '.gz':
            return np.load(io.BytesIO(gzip.open(p, 'rb').read()),
                           allow_pickle=True)
        return np.load(p, allow_pickle=True)
    return None


def _identify(d: pathlib.Path, namespace: str):
    """One sealed directory, described from its CONTENT rather than its path."""
    present = [m for m in SEAL_MARKERS if (d / m).exists()]
    if not present:
        return None
    doc = {}
    for m in ('board.json', 'forecast_artifact.json', 'SEALED_FORECAST.json'):
        if (d / m).exists():
            doc = _read_json(d / m)
            if doc:
                break
    run = doc.get('run') or {}
    fresh = doc.get('freshness') or {}
    info = doc.get('information_set') or {}
    gid = (doc.get('game_id') or run.get('game_id')
           or _game_from_path(d))
    return {
        'namespace': namespace,
        'dir': str(d),
        'markers': present,
        'game_id': gid,
        'kickoff_utc': (doc.get('kickoff_utc') or fresh.get('kickoff_utc')
                        or info.get('kickoff_utc') or run.get('kickoff_utc')),
        'written_at': (fresh.get('written_at') or run.get('written_at')
                       or doc.get('written_at')),
        'model_configuration': (doc.get('model_configuration')
                                or run.get('model_configuration')),
        'promoted': bool(doc.get('promoted')),
        'has_draws': any((d / n).exists() for n in
                         ('player_draws.npz', 'player_draws.npz.gz')),
        'has_evaluation': (d / 'EVALUATION.json').exists(),
        'label': d.name,
    }


def _game_from_path(d: pathlib.Path):
    """Recover a game id from any path segment that looks like one."""
    for part in reversed(d.parts):
        bits = part.split('_')
        if len(bits) >= 4 and bits[0].isdigit() and len(bits[0]) == 4:
            return part
        if part.lower().startswith('g') and '_' in part:
            # g1_ne_sea -> 2026_01_NE_SEA is NOT inferable; say so by
            # returning None rather than guessing a season and week.
            return None
    return None


def discover_all():
    """Every sealed forecast, across every namespace, keyed by directory."""
    out = []
    for ns, root in NAMESPACES:
        if not root.exists():
            continue
        for d in sorted(p for p in root.rglob('*') if p.is_dir()):
            rec = _identify(d, ns)
            if rec:
                out.append(rec)
        rec = _identify(root, ns)
        if rec:
            out.append(rec)
    return out


def for_game(game_id, alias=()):
    """Every sealed forecast for one game, including historical namespaces.

    `alias` carries the other names a game has been filed under -- the shadow
    run recorded 2026_01_NE_SEA inside a directory called `g1_ne_sea`, and a
    ledger that matches only on the canonical id would miss it.
    """
    want = {game_id, *alias}
    hits = []
    for rec in discover_all():
        if rec['game_id'] in want:
            hits.append(rec)
            continue
        lab = rec['label'].lower()
        if any(_looks_like(a, lab) for a in want):
            hits.append(rec)
    return hits


def _looks_like(game_id, label):
    """`2026_01_NE_SEA` against a label like `g1_ne_sea`."""
    bits = [b.lower() for b in str(game_id).split('_')[2:4] if b]
    return bool(bits) and all(b in label for b in bits)
