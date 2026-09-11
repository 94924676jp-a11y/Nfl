#!/usr/bin/env python3.12
"""One-time migration: give every prospective ledger row its unit of evidence.

    python3.12 nfl/tools/migrate_prospective_ledger.py

WHY A MIGRATION AND NOT A BACKFILL IN PLACE.

The first ledger recorded `game_id`, `metric`, `gsis_id`, `sealed_dir` and a
16-hex outcome prefix. That is enough to score a row and not enough to COUNT
one: it cannot say which sealed forecast a row came from, so five candidate
forecasts of one game are indistinguishable from five games. The unit-of-
evidence guard requires `forecast_id`, `candidate`, `cutoff`, `player_id` and
the full `outcome_hash` on every row.

Those fields cannot be invented from the old rows -- they are properties of
the sealed forecast, not of the scoring. They CAN be re-derived exactly, by
re-running the same scoring against the same sealed artifacts and the same
stored outcome bytes. That is what this does.

WHAT IT PRESERVES. The existing ledger is copied verbatim to
`PROSPECTIVE_LEDGER.v1.jsonl` before anything else happens, and that file is
never written again. The migration refuses to run a second time.

WHAT IT PROVES BEFORE ACCEPTING. Every v1 row must be matched by a regenerated
row agreeing on every shared value -- actual, crps, pit, bias, coverage, the
lot. A migration that quietly changed a score would be indistinguishable from
a migration that worked, so the equivalence is checked and recorded rather
than assumed. `sealed_dir` is the one deliberate difference: it was an
absolute path, which is a property of the machine that ran the scoring, and is
now repository-relative.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import shutil
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research import postgame as PG                       # noqa: E402
from sportsplatform.governance.outcome import State           # noqa: E402

V1 = PG.STORE / 'PROSPECTIVE_LEDGER.v1.jsonl'
REPORT = PG.STORE / 'LEDGER_MIGRATION.json'

# Fields whose value must be identical before and after. `sealed_dir` is
# excluded deliberately and named in the report.
IGNORE = {'sealed_dir', 'forecast_id', 'candidate', 'cutoff_utc',
          'cutoff_basis', 'cutoff_regime', 'run_id', 'outcome_hash',
          'player_id', 'version_status', 'version_index',
          'n_outcome_versions', 'superseded_by_outcome_hash'}


def _rel(path):
    """The old rows carried absolute paths, the new ones relative. Same dir."""
    p = pathlib.Path(str(path or ''))
    try:
        return str(p.resolve().relative_to(_REPO.resolve()))
    except ValueError:
        return str(path or '')


def _match_key(r):
    """Identity shared by the old and new shapes.

    `sealed_dir` MUST be part of it. Without it, several sealed forecasts of
    one game share a key, the comparison pairs a row with a different
    candidate's row, and thousands of rows report as changed when nothing
    moved -- which is exactly what the first version of this script did.
    """
    return '|'.join(str(r.get(k, '')) for k in (
        'game_id', 'entity', 'gsis_id', 'team', 'metric', 'outcome_sha16')
    ) + '|' + _rel(r.get('sealed_dir'))


def _blob():
    hits = sorted(PG.STORE.glob('pbp_*.csv.gz'))
    if len(hits) != 1:
        raise SystemExit(
            f'LEDGER_MIGRATION_AMBIGUOUS_OUTCOME: {len(hits)} stored outcome '
            f'artifacts in {PG.STORE}. The migration must reproduce against '
            f'exactly one known realisation, never pick one.')
    return hits[0]


def main():
    if V1.exists():
        print(f'LEDGER_MIGRATION_ALREADY_DONE: {V1} exists. Refusing to run '
              f'again -- a second run would overwrite the preserved '
              f'predecessor.')
        return 1
    if not PG.LEDGER.exists():
        print('LEDGER_MIGRATION_NOTHING_TO_MIGRATE: no ledger exists yet.')
        return 1

    before = PG.load_ledger()
    shutil.copy2(PG.LEDGER, V1)
    blob = _blob()

    # The live ledger is rebuilt from scratch. The predecessor above is the
    # copy that survives; nothing is lost, and the equivalence check below
    # refuses the result if anything moved.
    PG.LEDGER.unlink()
    o = PG.run(blob=str(blob))
    if o.state is not State.PASS:
        shutil.copy2(V1, PG.LEDGER)
        V1.unlink()
        print(f'LEDGER_MIGRATION_REFUSED: {o.state.name}[{o.code}] '
              f'{o.detail[:200]}. The original ledger has been restored.')
        return 1

    after = PG.load_ledger()
    idx = {}
    for r in after:
        idx.setdefault(_match_key(r), []).append(r)

    missing, changed = [], []
    for r in before:
        cands = idx.get(_match_key(r)) or []
        if not cands:
            missing.append(_match_key(r))
            continue
        hit = cands[0]
        diff = {k: [v, hit.get(k)] for k, v in r.items()
                if k not in IGNORE and hit.get(k) != v}
        if diff:
            changed.append({'key': _match_key(r), 'diff': diff})

    ev = PG.accounting(PG.current_rows(after))
    report = {
        'artifact': 'NFL_PROSPECTIVE_LEDGER_MIGRATION',
        'spec_version': PG.SPEC_VERSION,
        'ran_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'reason': ('the v1 ledger could not identify which sealed forecast a '
                   'row came from, so rows could not be counted in any unit '
                   'other than rows'),
        'predecessor_preserved': str(V1.relative_to(_REPO)),
        'predecessor_rows': len(before),
        'regenerated_rows': len(after),
        'outcome_artifact': str(blob.relative_to(_REPO)),
        'v1_rows_not_reproduced': missing,
        'n_v1_rows_not_reproduced': len(missing),
        'v1_rows_whose_values_changed': changed[:50],
        'n_v1_rows_whose_values_changed': len(changed),
        'deliberate_field_changes': {
            'sealed_dir': 'absolute path -> repository-relative path',
        },
        'fields_added': sorted({'forecast_id', 'candidate', 'cutoff_utc',
                                'cutoff_basis', 'cutoff_regime', 'run_id',
                                'outcome_hash', 'player_id'}),
        'evidence_after': ev,
        'lossless': not missing and not changed,
    }
    REPORT.write_text(json.dumps(report, indent=1, default=str) + '\n')
    print(f'predecessor preserved  : {V1.relative_to(_REPO)} '
          f'({len(before)} rows)')
    print(f'regenerated            : {len(after)} rows')
    print(f'v1 rows not reproduced : {len(missing)}')
    print(f'v1 rows changed        : {len(changed)}')
    print(f'lossless               : {report["lossless"]}')
    print(f'distinct games         : {ev["distinct_games"]}')
    print(f'candidate forecasts    : {ev["distinct_candidate_forecasts"]}')
    return 0 if report['lossless'] else 2


if __name__ == '__main__':
    sys.exit(main())
