"""What the shadow forecast is allowed to read, and the refusals that enforce it.

    python3.12 -m nfl.prospective.q9shadow.inputs --game 2026_01_CHI_CAR

THREE SEPARATE GUARDS, BECAUSE THEY FAIL IN THREE DIFFERENT WAYS

1. AN OUTCOME-SHAPED KEY IN THE INPUT BUNDLE. The bundle is assembled from the
   capture manifest, and a capture whose name or payload key looks like a
   realised result (`actual_`, `final_`, `home_score`, `pbp`, ...) is refused
   BY NAME rather than skipped. Skipping it would let a later reader believe
   the bundle was clean.

2. AN OUTCOME READER REACHABLE FROM THE SEAL PATH. The modules that fetch,
   store and score realised play-by-play are named here, and
   `assert_no_outcome_reader_imported` refuses if the sealing path has one in
   its namespace. This is the structural half of "cannot read outcomes": the
   dry-run proof then poisons those functions and shows the seal still
   completes, which is the behavioural half.

3. A REALISED COLUMN REACHING THE MODEL THROUGH A PANEL ROW. This is the real
   risk and the subtlest. The historical panel row carries `targets` --
   the realised value -- because that is what the panel is FOR. `featurise`
   does not read it, but "does not read it" is a property of code that could
   change. So the row handed to the frozen featuriser is PROJECTED onto the
   exact key set the featuriser reads, derived from the featuriser's own
   source rather than typed out here. A realised column cannot reach the model
   because it is not in the dictionary the model is given.

WHAT THIS MODULE DELIBERATELY DOES NOT DO. It does not decide eligibility and
it does not seal. `nfl.research.shadow.information_set` already selects the
lawful vintage of each source against a consumed clock and already reports
what it could not obtain; that is imported, never reimplemented.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State   # noqa: E402
from sportsplatform.governance.provenance import Provenance           # noqa: E402
from nfl.identity.execution_identity import ConsumedPartition         # noqa: E402
from nfl.research.q9 import hurdle as Q9                              # noqa: E402
from nfl.research.shadow import information_set as ISET               # noqa: E402

SPEC_VERSION = 'q9-shadow-inputs-1'

# ---------------------------------------------------------------- guard 1
#
# Substrings that mark a key or a source as carrying a realised result. Chosen
# to be specific enough not to fire on a pregame field: the project has been
# bitten before by a substring guard that matched `yardline_100` on `_line`,
# so each entry here is either a full field name or an unambiguous prefix.
OUTCOME_SHAPED_KEYS = (
    'actual_', 'realized_', 'realised_', 'final_score', 'home_score',
    'away_score', 'play_by_play', 'boxscore', 'postgame', 'outcome_hash',
    'result_', 'graded', 'settled',
)

# Capture sources that ARE realised results. A source, not a key: the whole
# partition is refused, because a pregame forecast that consumed play-by-play
# of its own game is not a forecast whatever it did with the bytes.
#
# MATCHED EXACTLY, NOT AS A SUBSTRING, AND THE FIRST DRAFT PROVED WHY. This
# list contained `'weekly'` and was matched with `in`, so it refused the whole
# bundle on `weekly_rosters` -- a roster feed, not a result. That is the same
# defect as Track 1's market guard matching `yardline_100` on `_line`, hit
# again three tasks later by the person who wrote the warning.
OUTCOME_SOURCES = frozenset((
    'pbp', 'play_by_play', 'nflverse_pbp', 'player_stats',
    'weekly_player_stats', 'stats_player_week', 'ftn_charting'))

# SOURCES THAT MAY BE IN THE BUNDLE BUT MAY NOT REACH STAGE 1. `weekly_rosters`
# is the case that matters: `status == INA` is game-day information, so Q9
# names it in FORBIDDEN_INPUTS -- yet the R8 appearance pool legitimately
# reads the same file for its ACT filter. Refusing the bundle over it would
# refuse the production arm too, and permitting it without a control would put
# an INA flag one dictionary lookup away from the hurdle.
#
# The control is guard 3 and it is structural: none of the ten keys the
# featuriser reads is sourced from this file, and the projection means the
# hurdle is handed a dictionary that does not contain one.
RESTRICTED_SOURCES = frozenset(('weekly_rosters', 'official_inactives'))

# ---------------------------------------------------------------- guard 2
#
# The functions this project uses to read a realised outcome. Named here so
# the dry-run can poison exactly these and so a future import of one into the
# seal path is a failing check rather than a code review someone has to catch.
OUTCOME_READERS = (
    'nfl.research.postgame.fetch_outcomes',
    'nfl.research.postgame.stored_outcome',
    'nfl.research.postgame._rows',
    'nfl.research.postgame.load_ledger',
    'nfl.research.postgame.score_game',
    'nfl.research.shadow.actuals.team_actuals',
    'nfl.research.shadow.actuals.player_actuals',
)

OUTCOME_READER_MODULES = tuple(sorted(
    {r.rsplit('.', 1)[0] for r in OUTCOME_READERS}))

# ---------------------------------------------------------------- guard 3
#
# The panel keys the FROZEN featuriser reads, derived from its own source.
# Typed constants drift; a derivation cannot.
_KEY_RE = re.compile(r"""r(?:\.get\(|\[)\s*['"]([A-Za-z0-9_]+)['"]""")


def derive_feature_row_keys():
    """The exact row keys `Q9.featurise` reads, from the function's source."""
    import inspect
    src = inspect.getsource(Q9.featurise)
    return tuple(sorted(set(_KEY_RE.findall(src))))


FEATURE_ROW_KEYS = derive_feature_row_keys()


def project_feature_row(r):
    """The row the featuriser is given: only the keys it is allowed to read.

    A KeyError is impossible because the projection uses `.get`, and a
    realised column is impossible because it is simply not present.
    """
    return {k: r.get(k) for k in FEATURE_ROW_KEYS}


def assert_projection_excludes_outcomes() -> Outcome:
    """No derived feature key may itself be outcome-shaped."""
    bad = [k for k in FEATURE_ROW_KEYS
           if any(s in k.lower() for s in Q9.FORBIDDEN_INPUTS)
           or any(s in k.lower() for s in OUTCOME_SHAPED_KEYS)]
    if bad:
        return Outcome.fail(
            'Q9_FEATURE_KEY_OUTCOME_SHAPED',
            f'{bad} are read by the frozen featuriser and are outcome-shaped. '
            f'The projection cannot make an input lawful; the feature set '
            f'would have to change, which is a new candidate.', keys=bad)
    return Outcome.ok('Q9_FEATURE_PROJECTION_CLEAN',
                      value=list(FEATURE_ROW_KEYS),
                      detail=f'{len(FEATURE_ROW_KEYS)} feature row key(s), '
                             f'none outcome-shaped',
                      n_keys=len(FEATURE_ROW_KEYS))


def assert_no_outcome_shaped_inputs(bundle) -> Outcome:
    """Refuse an input bundle carrying a realised result, by name."""
    offences = []
    for src, rec in sorted((bundle.get('sources') or {}).items()):
        if src.lower() in OUTCOME_SOURCES:
            offences.append({'source': src, 'why': 'OUTCOME_SOURCE'})
        for k in rec:
            if any(s in str(k).lower() for s in OUTCOME_SHAPED_KEYS):
                offences.append({'source': src, 'key': k,
                                 'why': 'OUTCOME_SHAPED_KEY'})
    if offences:
        return Outcome.fail(
            'Q9_SHADOW_OUTCOME_SHAPED_INPUT',
            f'{len(offences)} outcome-shaped input(s) in the bundle: '
            f'{offences[:5]}. A pregame seal that consumed a realised result '
            f'is not a forecast, and dropping the offending key quietly would '
            f'leave the bundle looking clean to the next reader.',
            offences=offences)
    restricted = sorted(s for s in (bundle.get('sources') or {})
                        if s.lower() in RESTRICTED_SOURCES)
    return Outcome.ok(
        'Q9_SHADOW_INPUTS_PREGAME_ONLY',
        value=sorted(bundle.get('sources') or {}),
        detail=f'{len(bundle.get("sources") or {})} source(s), none '
               f'outcome-shaped'
               + (f'; {len(restricted)} restricted from stage 1 and kept out '
                  f'of it by the feature projection: {restricted}'
                  if restricted else ''),
        restricted_from_stage_1=restricted)


def assert_no_outcome_reader_imported(module) -> Outcome:
    """Refuse if an outcome reader is reachable from a sealing module."""
    ns = vars(module)
    found = []
    for name, obj in sorted(ns.items()):
        mod = getattr(obj, '__module__', None) or getattr(obj, '__name__', None)
        if mod and str(mod) in OUTCOME_READER_MODULES:
            found.append({'binding': name, 'module': str(mod)})
    if found:
        return Outcome.fail(
            'Q9_SEAL_PATH_IMPORTS_OUTCOME_READER',
            f'{module.__name__} has {found} in its namespace. The sealing '
            f'path must not be able to reach an outcome reader at all: a '
            f'guard that depends on nobody calling the function it imported '
            f'is a convention, not a control.', found=found)
    return Outcome.ok(
        'Q9_SEAL_PATH_HAS_NO_OUTCOME_READER', value=module.__name__,
        detail=f'{module.__name__} imports none of '
               f'{len(OUTCOME_READER_MODULES)} outcome-reader module(s)')


# ------------------------------------------------------- the input bundle
def bundle(kickoff_utc, written_at, sources=None) -> Outcome:
    """The lawful vintage of every source as of `written_at`, hashed.

    `written_at` is the CONSUMED CLOCK, so selection is bounded by it and
    `retrieved_at <= written_at` holds by construction rather than by a later
    check that refuses a board it should have produced.
    """
    try:
        iset = ISET.build(kickoff_utc, sources=sources,
                          observed_before=written_at)
    except ISET.InformationSetError as exc:
        return Outcome.blocked('Q9_SHADOW_INFORMATION_SET_UNAVAILABLE',
                               str(exc), cause=Cause.DATA)
    chosen = iset.get('sources') or {}
    if not chosen:
        return Outcome.blocked(
            'Q9_SHADOW_NO_LAWFUL_VINTAGE',
            f'no source has an observation before the consumed clock '
            f'{written_at}. An empty information set is not a clean one.',
            cause=Cause.DATA, absent=iset.get('absent'))
    g = assert_no_outcome_shaped_inputs(iset)
    if g.state is not State.PASS:
        return g
    return Outcome.ok(
        'Q9_SHADOW_BUNDLE_OK', value=iset,
        detail=f'{len(chosen)} source(s) selected before {written_at}; '
               f'{len(iset.get("absent") or [])} absent',
        n_sources=len(chosen), absent=sorted(iset.get('absent') or []))


def partitions(iset, written_at, effective_for_date) -> list:
    """One ConsumedPartition per selected source, with real provenance.

    `source_timestamp` is set to the observation instant rather than invented:
    the manifest records when we obtained the bytes, not when the publisher
    stamped them, and claiming a publisher clock we do not hold would be a
    fabricated provenance field. `generated_at` is the forecast's own
    `written_at`, which is when this wrapper was assembled.
    """
    out = []
    for src, rec in sorted((iset.get('sources') or {}).items()):
        out.append(ConsumedPartition(
            partition_id=f'{src}@{rec["sha256"][:16]}',
            source=src,
            url=rec.get('blob') or f'vintage://{src}',
            sha256=rec['sha256'],
            provenance=Provenance(
                source=src,
                source_timestamp=rec['observed_at'],
                retrieved_at=rec['observed_at'],
                generated_at=written_at,
                effective_for_date=effective_for_date,
                schema_version=f'vintage/{src}/1',
                cache_timestamp=None,
                url=rec.get('blob'))))
    return out


def bundle_sha256(iset) -> str:
    """One digest over every selected content hash, in source order."""
    payload = {s: r['sha256']
               for s, r in sorted((iset.get('sources') or {}).items())}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()
                          ).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--kickoff', default='2026-09-13T17:00:00Z')
    ap.add_argument('--written', default=None)
    a = ap.parse_args(argv)
    written = a.written or dt.datetime.now(dt.timezone.utc).isoformat(
        timespec='seconds').replace('+00:00', 'Z')
    print(f'feature row keys ({len(FEATURE_ROW_KEYS)}): '
          f'{", ".join(FEATURE_ROW_KEYS)}')
    print(assert_projection_excludes_outcomes())
    b = bundle(a.kickoff, written)
    print(b)
    if b.state is State.PASS:
        print(f'  bundle sha256 {bundle_sha256(b.value)[:16]}')
        print(f'  partitions    {len(partitions(b.value, written, "2026-09-13"))}')
    return 0 if b.state is State.PASS else 1


if __name__ == '__main__':
    sys.exit(main())
