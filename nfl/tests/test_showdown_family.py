#!/usr/bin/env python3.12
"""The Showdown family's own prospective lane (owner ruling 2). Each control forced both ways on a
seal written to a temporary root; discovery through the existing sealed index; the Q9 contract
provably untouched. The real W4 artifacts are sealed retrospectively and must read NOT evidence.
"""
from __future__ import annotations

import copy
import json
import pathlib
import shutil
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.prospective import showdown_family as SF  # noqa: E402
from nfl.prospective.q9shadow import reuse as REUSE  # noqa: E402
from nfl.research import sealed_index as SI  # noqa: E402
from sportsplatform.governance.outcome import State  # noqa: E402
from nfl.tests import _registry  # noqa: E402

RESULTS = []
TMP = pathlib.Path(tempfile.mkdtemp(prefix='showdown_family_'))
PROJ = _REPO / 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_PROJ.json'
DRAWS = _REPO / 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_DRAWS.json'
STATE = _REPO / 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_STATE.json'
EXPORT = _REPO / 'nfl/dfs/salaries/raw/DKEntries_PIT_CLE_SHOWDOWN_2026W4.csv'
INACT = _REPO / 'nfl/dfs/salaries/raw/OFFICIAL_INACTIVES_PIT_CLE_2026W4.json'
KICK = '2026-10-02T00:15:00Z'
_SEAL = {}


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _seal(**kw):
    args = dict(game_id='2026_04_PIT_CLE', proj_path=PROJ, draws_path=DRAWS, state_path=STATE,
                export_path=EXPORT, inactives_path=INACT, kickoff_utc=KICK,
                written_at='2026-10-02T00:01:57Z', written_at_basis='TEST_CLOCK',
                prospective_evidence=True, model_configuration='TEST_CFG', out_root=TMP)
    args.update(kw)
    return SF.seal(**args)


def _art(o):
    a = copy.deepcopy(o.value['artifact']); a['_dir'] = o.value['dir']; return a


@check('a seal is written with every required identity field, from inputs not typed in')
def _sealed():
    o = _seal()
    assert o.state is State.PASS, (o.code, o.detail)
    a = o.value['artifact']
    for k in ('model_family', 'code_identity', 'code_identity_sha256', 'projection_artifact',
              'draw_artifact', 'game_id', 'kickoff_utc', 'written_at', 'written_at_basis',
              'information_set', 'data_cutoff', 'availability_vintage', 'roster_vintage',
              'depth_vintage', 'source_captures', 'prospective_evidence'):
        assert k in a, k
    assert a['model_family'] == SF.MODEL_FAMILY
    assert len(a['code_identity']) == len(SF.EXECUTION_PATH)
    assert a['data_cutoff']['blob'].endswith('pbp_2026.79b02496d26004ee.csv.gz'), a['data_cutoff']
    assert len(a['roster_vintage']) == 11, len(a['roster_vintage'])
    assert a['depth_vintage']['basis'] == 'USAGE_DERIVED_FROM_PANEL'
    d = pathlib.Path(o.value['dir'])
    assert (d / 'forecast_artifact.json').exists() and (d / 'player_draws.npz').exists() \
        and (d / 'player_draws_manifest.json').exists()
    _SEAL['ok'] = o
    return (f"{d.relative_to(TMP)}; {len(a['code_identity'])} module hashes; cutoff "
            f"{a['information_set']['observed_before']}; per-stat {a['draw_artifact']['per_stat_layers']}")


@check('the existing sealed index discovers it with game_id, kickoff and a cutoff basis')
def _discovered():
    rec = SI._identify(pathlib.Path(_SEAL['ok'].value['dir']), SF.NAMESPACE)
    assert rec and rec['game_id'] == '2026_04_PIT_CLE', rec
    assert rec['kickoff_utc'] == KICK and rec['cutoff_utc'], rec
    assert rec['cutoff_basis'] == 'information_set.observed_before', rec['cutoff_basis']
    return f"cutoff {rec['cutoff_utc']} via {rec['cutoff_basis']}; namespace {rec['namespace']}"


@check('ADMISSIBLE when sealed live before kickoff with every field present')
def _admissible():
    o = REUSE.assert_currently_admissible(_art(_SEAL['ok']))
    assert o.state is State.PASS, (o.code, {k: v['code'] for k, v in (o.evidence.get('controls') or {}).items()})
    per = o.evidence.get('controls') or {}
    assert set(per) == set(SF.MANDATORY_CONTROLS), sorted(per)
    return f"{o.code}: {len(per)} family controls all ADMISSIBLE"


def _refused(mut, code_contains):
    a = _art(_SEAL['ok']); mut(a)
    o = REUSE.assert_currently_admissible(a)
    assert o.state is State.FAIL, (o.state.name, o.code)
    per = o.evidence['controls']
    hit = [n for n, v in per.items() if v['disposition'] == 'REFUSED' and code_contains in v['code']]
    assert hit, {n: v['code'] for n, v in per.items() if v['disposition'] != 'ADMISSIBLE'}
    return f"{hit[0]} -> {per[hit[0]]['code']}: {per[hit[0]]['detail'][:80]}"


@check('REFUSED on code drift: a module hash that no longer matches current source')
def _drift():
    def m(a): a['code_identity']['nfl.tools.proj_v1'] = '0000000000000000'
    return _refused(m, 'CODE_IDENTITY_DRIFT')


@check('REFUSED when the draw artifact on disk does not hash to what the seal recorded')
def _draw_mismatch():
    def m(a): a['draw_artifact']['file_sha256'] = 'f' * 64
    return _refused(m, 'DRAW_ARTIFACT_HASH_MISMATCH')


@check('REFUSED when the projection artifact on disk does not hash to what the seal recorded')
def _proj_mismatch():
    def m(a): a['projection_artifact']['sha256'] = 'e' * 64
    return _refused(m, 'PROJECTION_HASH_MISMATCH')


@check('REFUSED on time basis: a seal written at or after kickoff')
def _late():
    def m(a): a['written_at'] = '2026-10-02T00:15:00Z'
    return _refused(m, 'TIME_BASIS')


@check('REFUSED on time basis: a source capture newer than the seal clock')
def _capture_after_seal():
    def m(a): a['source_captures'][0]['retrieved_at'] = '2026-10-02T00:10:00Z'
    return _refused(m, 'TIME_BASIS')


@check('REFUSED when the seal declares itself NOT evidence -- a retrospective seal')
def _not_evidence():
    o = _seal(prospective_evidence=False, written_at_basis='GIT_COMMIT_TIMESTAMP_RETROSPECTIVE',
              reason='sealed after the fact from commit timestamps', model_configuration='RETRO')
    assert o.state is State.PASS
    a = _art(o)
    r = REUSE.assert_currently_admissible(a)
    assert r.state is State.FAIL
    v = r.evidence['controls']['prospective_evidence_eligibility']
    assert v['code'] == 'ARTIFACT_DECLARES_ITSELF_NOT_EVIDENCE', v
    return f"{v['code']}: {v['detail'][:70]}"


@check('REFUSED when availability or roster/depth vintage is missing')
def _vintages():
    def m1(a): a['availability_vintage'] = {}
    r1 = _refused(m1, 'AVAILABILITY_VINTAGE_UNDECLARED')
    def m2(a): a['roster_vintage'] = []
    r2 = _refused(m2, 'ROSTER_DEPTH_VINTAGE_UNDECLARED')
    return r1 + ' | ' + r2


@check('the Q9 contract is untouched: 7 controls, and a non-Showdown artifact never hits the family lane')
def _q9_untouched():
    assert len(REUSE.MANDATORY_CONTROLS) == 7, REUSE.MANDATORY_CONTROLS
    assert set(REUSE.MANDATORY_CONTROLS) <= set(REUSE.CONTROL_EVALUATORS)
    o = REUSE.assert_currently_admissible({'completeness': 'PARTIAL_PLAYER_COVERAGE'})
    per = o.evidence.get('controls') or {}
    assert set(per) == set(REUSE.MANDATORY_CONTROLS), sorted(per)
    assert 'model_family_declared' not in per
    return f"Q9 artifact judged by {len(per)} Q9 controls; family controls absent"


@check('the layered draw artifact round-trips: dk_scoring rows are gsis ids with teams, DSTs on a team axis')
def _layers():
    d = pathlib.Path(_SEAL['ok'].value['dir'])
    man = json.loads((d / 'player_draws_manifest.json').read_text())
    L = man['layers']
    assert L['dk_scoring']['row_axis'] == 'gsis_id' and all(r.startswith('00-') for r in L['dk_scoring']['row_ids'])
    assert L['dst']['row_axis'] == 'team' and sorted(L['dst']['row_ids']) == ['CLE', 'PIT'], L['dst']
    assert len(L['kicking']['row_ids']) == 2
    assert man['n_draws'] == 2000
    return (f"dk_scoring {len(L['dk_scoring']['row_ids'])} players, kicking 2, dst 2, "
            f"n_draws {man['n_draws']}, digest {man['content_digest'][:16]}")


_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    # The tally tripwire, in this module's own source because run_suite recognises it by shape.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    try:
        for fname in _EMITTED:
            try:
                globals()[fname]()
            except Exception:  # noqa: BLE001  -- already printed and counted by the wrapper
                pass
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
