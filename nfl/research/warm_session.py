"""Reuse the expensive shared history across refreshes, and nothing else.

WHAT IS ACTUALLY SLOW, MEASURED.

A fresh process pays about 65s before its first forecast; every game after
that costs about 11s. Profiling the first `build_one` put the cost inside
`football_engine.slate_fits` (53.9s), dominated by
`appearance_r8.enriched_frame` (51.1s), which builds on
`appearance_r7.build_frame` (16.6s) and the historical loaders underneath.

WHY THOSE OBJECTS ARE SAFE TO KEEP, AND HOW FAR THAT GOES.

`build_frame` and `enriched_frame` read exactly two things: the twelve
historical leaves staged through `appearance_model.stage_inputs` -- seasons
2020 to 2025, every one hash-checked against `INPUT_MANIFEST.json` before use
-- and `dc25_daily.csv.gz`. NO 2026 VINTAGE REACHES THEM. They are a pure
function of immutable history, which is why they were already memoised and
why games two through twelve of a slate cost a sixth of game one.

What is NOT cached here, and must never be: anything a game consumes. Team
volume, the QB allocation, appearance for a given slate, and every forecast
output stay per-game and are recomputed whenever that game's consumed slice
moves. Caching a forecast would hit the benchmark by faking it.

THE DEFECT IN THE CACHE AS IT STOOD.

`_FRAME` and `_ENRICHED` were module-level dicts keyed on NOTHING. They
served whatever they held for the life of the process, so a dependency
changing underneath -- a restaged leaf, an edited daily file -- would have
been served stale for as long as that process lived. That is precisely the
hidden global mutable state this work is forbidden to introduce, and it was
already there. The caches are now keyed on a content fingerprint of their
declared dependencies and evict themselves when it moves.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State   # noqa: E402

SPEC_VERSION = 'warm-session-1'

# The declared dependencies of the shared historical frames. Anything added
# to the frames' inputs must be added here, or the fingerprint stops covering
# them and staleness becomes possible again.
def _dependency_paths():
    from nfl.production.nonqb import appearance_model as AM
    from nfl.production.nonqb import appearance_r7 as R7
    return [AM.MANIFEST, R7.DAILY_LEAF]


def dependency_fingerprint() -> Outcome:
    """A content hash over everything the shared frames read.

    INPUT_MANIFEST.json already carries a hash of every staged leaf, so
    hashing the manifest covers all twelve of them; the daily depth leaf is
    hashed directly. A missing dependency is a refusal, not a fingerprint of
    nothing -- an empty hash would compare equal to another empty hash and
    make every cache look fresh.
    """
    h = hashlib.sha256()
    parts = {}
    for p in _dependency_paths():
        if not pathlib.Path(p).exists():
            return Outcome.blocked(
                'WARM_DEPENDENCY_MISSING',
                f'{p} is absent, so no honest fingerprint can be computed '
                f'over the shared historical inputs', cause=Cause.DATA,
                missing=str(p))
        b = pathlib.Path(p).read_bytes()
        d = hashlib.sha256(b).hexdigest()
        parts[pathlib.Path(p).name] = d[:16]
        h.update(d.encode())
    return Outcome.ok('WARM_FINGERPRINT', value=h.hexdigest()[:32],
                      spec_version=SPEC_VERSION, parts=parts,
                      n_dependencies=len(parts))


def shared_state_status():
    """Whether the shared historical frames are primed AND still valid."""
    from nfl.production.nonqb import appearance_r7 as R7
    from nfl.production.nonqb import appearance_r8 as R8
    fp = R7._dependency_fingerprint()
    return {
        'fingerprint': fp,
        'r7_frame_primed': bool(R7._FRAME.get('rows')),
        'r7_frame_valid': R7._FRAME.get('fingerprint') == fp
                          and bool(R7._FRAME.get('rows')),
        'r8_enriched_primed': bool(R8._ENRICHED.get('rows')),
        'r8_enriched_valid': R8._ENRICHED.get('fingerprint') == fp
                             and bool(R8._ENRICHED.get('rows')),
    }


class SlateSession:
    """A live process that services repeated slate refreshes.

    The saving is NOT a cached forecast. Every game is still forecast by the
    same code on the same inputs, and a game whose consumed slice moved is
    still recomputed in full. What survives between refreshes is the shared
    historical frame -- a pure function of immutable inputs, keyed on their
    content hash -- so the second refresh does not rebuild what cannot have
    changed.
    """

    def __init__(self, date, candidate='R8', market=None):
        self.date, self.candidate, self.market = date, candidate, market
        self.history = []
        self.warm_seconds = None
        self.fingerprint_at_warm = None

    def warm(self):
        """Prime the shared frames once. Nothing game-specific is touched."""
        from nfl.production.nonqb import appearance_r8 as R8
        fp = dependency_fingerprint()
        if fp.state is not State.PASS:
            return fp
        t = time.perf_counter()
        o = R8.enriched_frame()
        el = round(time.perf_counter() - t, 4)
        self.warm_seconds = el
        self.fingerprint_at_warm = fp.value
        if o.state is not State.PASS:
            return Outcome.blocked(
                'WARM_SHARED_STATE_UNAVAILABLE',
                f'the shared historical frame could not be built: '
                f'{o.state.name}[{o.code}]', cause=Cause.DATA,
                seconds=el, inner_code=o.code)
        return Outcome.ok('WARM_SHARED_STATE_READY', value=fp.value,
                          spec_version=SPEC_VERSION, seconds=el,
                          was_already_cached=bool(o.evidence.get('cached')),
                          n_rows=len(o.value or []))

    def refresh(self, **kw):
        """One slate refresh in this process. Returns (outcome, stats)."""
        from nfl.research import slate_runner as SR
        before = shared_state_status()
        hit = before['r7_frame_valid'] and before['r8_enriched_valid']
        t = time.perf_counter()
        o = SR.run(self.date, self.candidate, self.market, **kw)
        el = round(time.perf_counter() - t, 4)
        after = shared_state_status()
        stats = {
            'wall_seconds': el,
            'shared_state_cache': 'HIT' if hit else 'MISS',
            'fingerprint_before': before['fingerprint'],
            'fingerprint_after': after['fingerprint'],
            'fingerprint_stable': before['fingerprint'] == after['fingerprint'],
            'r7_valid_after': after['r7_frame_valid'],
            'r8_valid_after': after['r8_enriched_valid'],
        }
        self.history.append(stats)
        return o, stats

    def summary(self):
        hits = sum(1 for h in self.history
                   if h['shared_state_cache'] == 'HIT')
        return {'n_refreshes': len(self.history),
                'cache_hits': hits,
                'cache_misses': len(self.history) - hits,
                'warm_seconds': self.warm_seconds,
                'fingerprint': self.fingerprint_at_warm,
                'per_refresh_wall_seconds': [h['wall_seconds']
                                             for h in self.history]}
