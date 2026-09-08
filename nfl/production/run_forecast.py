"""The canonical production entrypoint.

    python3.12 -m nfl.production.run_forecast \
        --season 2026 --week 1 --game-id 2026_01_NE_SEA \
        --arm A --written-at 2026-09-09T22:00:00Z --out-dir /path

FAILS CLOSED. Every stage that cannot be executed correctly returns a named
refusal, and the run reports REFUSED rather than emitting a forecast.

`--written-at` is REQUIRED. The wall clock may stamp operational fields; it may
never stand in for a scientific clock, and there is no default that would let
it.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State   # noqa: E402
from nfl.production import authorization as AUTH                      # noqa: E402
from nfl.production import pipeline as PL                             # noqa: E402
from nfl.production import refusal as RF                              # noqa: E402
from nfl.prospective import artifact as ART                           # noqa: E402
from nfl.capture import registry as REG                               # noqa: E402
from nfl.production import qb_accounting as QBACC
from nfl.production import team_volume_v1 as TV
from nfl.production import qb_v1 as QBV1                             # noqa: E402

ARMS = ('A', 'B', 'C')


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _parse(ts):
    d = _dt.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)


def execution_identity(args, source_hashes: dict, code_commit: str) -> str:
    """Changing ANY input hash must change this. Tested."""
    payload = {'season': args.season, 'week': args.week,
               'game_id': args.game_id, 'arm': args.arm,
               'written_at': args.written_at, 'seed': args.seed,
               'code_commit': code_commit,
               'sources': dict(sorted(source_hashes.items()))}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def code_commit() -> str:
    import subprocess
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(_REPO),
                              capture_output=True, text=True,
                              timeout=20).stdout.strip() or 'UNKNOWN'
    except Exception:                                             # noqa: BLE001
        return 'UNKNOWN'


def build(args, fixtures: dict = None) -> dict:
    """Run the pipeline. `fixtures` supplies inputs for a historical dry run."""
    fx = fixtures or {}
    commit = code_commit()
    src = fx.get('source_hashes', {})
    run_id = execution_identity(args, src, commit)[:16]
    out_dir = pathlib.Path(args.out_dir) / run_id
    p = PL.Pipeline(run_id=run_id, out_dir=out_dir, arm=args.arm,
                    written_at=args.written_at)

    wrote = _parse(args.written_at)
    kickoff = fx.get('kickoff_utc')

    # --- 1. capture / input validation ---------------------------------
    def _capture():
        if not src:
            return RF.refuse('SOURCE_MISSING', 'capture_validation',
                             'no source captures were supplied', run_id)
        for name, meta in src.items():
            if name not in REG.BY_NAME:
                return RF.refuse('UNAUTHORIZED_INPUT', 'capture_validation',
                                 f'{name} is not in the source registry', run_id)
            if not meta.get('sha256'):
                return RF.refuse('RAW_HASH_MISMATCH', 'capture_validation',
                                 f'{name} carries no sha256', run_id)
            if meta.get('expected_sha256') and \
                    meta['expected_sha256'] != meta['sha256']:
                return RF.refuse('RAW_HASH_MISMATCH', 'capture_validation',
                                 f'{name} hash differs from the recorded one',
                                 run_id)
            got = meta.get('retrieved_at')
            if not got:
                return RF.refuse('SOURCE_CHRONOLOGY_FAILURE',
                                 'capture_validation',
                                 f'{name} has no retrieved_at', run_id)
            if _parse(got) > wrote:
                return RF.refuse('SOURCE_TOO_LATE', 'capture_validation',
                                 f'{name} retrieved at {got}, after '
                                 f'written_at {args.written_at}', run_id)
            if meta.get('schema_ok') is False:
                return RF.refuse('SCHEMA_DRIFT', 'capture_validation',
                                 f'{name} schema does not match', run_id)
        if kickoff and not wrote < _parse(kickoff):
            return RF.refuse('SOURCE_CHRONOLOGY_FAILURE', 'capture_validation',
                             f'written_at {args.written_at} is not before '
                             f'kickoff {kickoff}', run_id)
        if args.arm == 'A' and fx.get('consumes_2026_outcomes'):
            return RF.refuse('ARM_RULE_VIOLATION', 'capture_validation',
                             'arm A may consume no 2026 outcome at any point '
                             'in the season', run_id)
        if fx.get('cold_start_identity_mismatch'):
            return RF.refuse('COLD_START_VIOLATION', 'capture_validation',
                             'the cold-start freeze identity does not match',
                             run_id)
        return Outcome.ok('INPUTS_VALIDATED', value=src,
                          input_hashes={k: v['sha256'] for k, v in src.items()})
    p.run_stage('capture_validation', _capture,
                declared_inputs=list(src), spec_version=PL.PIPELINE_VERSION)

    # --- 2. identity resolution ----------------------------------------
    def _identity():
        players = fx.get('players', [])
        if not players:
            return RF.refuse('IDENTITY_UNRESOLVED', 'identity_resolution',
                             'no players supplied for the slate', run_id)
        bad = [q for q in players if not q.get('gsis_id')]
        # AN UNIDENTIFIABLE PLAYER IS EXCLUDED AND NAMED, NOT SILENTLY DROPPED
        # AND NOT GUESSED. The guard's purpose is that we never forecast a
        # player we cannot identify and never fuzzy-match a name; excluding him
        # satisfies both. Refusing the whole game does not: measured on the
        # 2026 week 1 roster, ONE practice-squad NYJ running back with no
        # gsis_id -- present in all three roster vintages, so upstream rather
        # than a capture defect -- blocked an entire game's forecast.
        #
        # The escape hatch is bounded. Above EXCLUSION_LIMIT the roster feed is
        # broken rather than merely incomplete, and the run refuses.
        EXCLUSION_LIMIT = 0.01
        if players and len(bad) / len(players) > EXCLUSION_LIMIT:
            return RF.refuse('IDENTITY_UNRESOLVED', 'identity_resolution',
                             f'{len(bad)} of {len(players)} player(s) have no '
                             f'gsis_id, above the {EXCLUSION_LIMIT:.0%} limit; '
                             f'that is a broken roster feed, not an incomplete '
                             f'one. Fuzzy name matching is forbidden.', run_id)
        resolved = [q for q in players if q.get('gsis_id')]
        if not resolved:
            return RF.refuse('IDENTITY_UNRESOLVED', 'identity_resolution',
                             'no player on the slate carries a gsis_id',
                             run_id)
        fx['_excluded_unidentified'] = [
            {'team': q.get('team'), 'position': q.get('position'),
             'reason': 'NO_GSIS_ID'} for q in bad]
        players = resolved
        if fx.get('game_missing'):
            return RF.refuse('REQUIRED_GAME_MISSING', 'identity_resolution',
                             'a requested game is absent from the schedule',
                             run_id)
        return Outcome.ok('IDENTITY_RESOLVED', value=players,
                          n_resolved=len(players), n_excluded=len(bad),
                          excluded=fx['_excluded_unidentified'],
                          warnings=([f'{len(bad)} player(s) excluded: no '
                                     f'gsis_id'] if bad else []))
    p.run_stage('identity_resolution', _identity, declared_inputs=['players'])

    # --- 3..10 modelling stages ----------------------------------------
    for stage, key, spec in (
            ('feature_build', 'features', 'prior-only, ordinal prefix cut'),
            ('team_environment', 'team_env', TV.SPEC_VERSION),
            ('appearance', 'appearance', 'P3 appearance'),
            ('participation', 'participation', 'Stage2 ewma_hl2 ACCEPTED'),
            ('targets_carries', 'targets_carries', 'P4C system C ACCEPTED'),
            ('conversion', 'conversion', 'RC1 baseline; SIGNAL_WEAK'),
            ('td_layer', 'td', 'TD1 identity; conversion baseline'),
            ('qb_layer', 'qb', QBV1.SPEC_VERSION)):
        def _model(_k=key, _s=spec, _st=stage):
            # ARTIFACT AND HASH CHECKS COME FIRST, ALWAYS. Running the model
            # before verifying its artifact would let a hash mismatch produce a
            # forecast and only then be noticed -- and in an earlier draft of
            # this file the QB branch sat above these and did exactly that.
            if fx.get(f'{_k}_missing'):
                return RF.refuse('MODEL_ARTIFACT_MISSING', _st,
                                 f'{_k} model artifact is absent', run_id)
            if fx.get(f'{_k}_hash_mismatch'):
                return RF.refuse('MODEL_HASH_MISMATCH', _st,
                                 f'{_k} artifact hash differs', run_id)
            if fx.get(f'{_k}_not_implemented'):
                return RF.refuse('STAGE_NOT_IMPLEMENTED', _st,
                                 f'{_k} has no production model; a named '
                                 f'refusal is returned rather than a '
                                 f'fabricated forecast', run_id)
            if _st == 'qb_layer' and (fx.get('qb_rows') is not None
                                      or fx.get('qb_slate')):
                # REAL MODEL LOGIC, not a dummy dictionary.
                fh = QBV1.artifact_hash()
                if fh.state is not State.PASS:
                    return RF.refuse('MODEL_ARTIFACT_MISSING', _st,
                                     fh.detail, run_id)
                if fx.get('qb_rows') is None:
                    qbp = [q for q in fx.get('players', [])
                           if q.get('position') == 'QB' and q.get('gsis_id')]
                    sl = (QBV1.slate_prospective(args.season, args.week, qbp)
                          if fx['qb_slate'].get('prospective')
                          else QBV1.slate(args.season, args.week,
                                          fx['qb_slate'].get('game_ids')))
                    if sl.state is not State.PASS:
                        return sl
                    fx['qb_rows'], fx['qb_allrows'] = sl.value
                o = QBV1.forecast(fx['qb_rows'], args.season,
                                  fx.get('qb_allrows', fx['qb_rows']),
                                  seed=args.seed, m=fx.get('qb_draws', 200))
                if o.state is not State.PASS:
                    return o
                ident = QBV1.identity_check(o.value)
                if ident.state is not State.PASS:
                    return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', _st,
                                     ident.detail, run_id)
                acct = QBACC.reconcile_draws(o.value)
                if acct.state is not State.PASS:
                    return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', _st,
                                     f'{acct.code}: {acct.detail}', run_id)
                team = QBACC.reconcile_team(
                    o.value, fx['qb_rows'],
                    team_rush_draws=fx.get('team_rush_draws'),
                    team_rushes_realised=fx.get('team_rushes_realised'))
                if team.state is not State.PASS:
                    return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', _st,
                                     f'{team.code}: {team.detail}', run_id)
                fx['_qb_draws_out'] = o.value
                fx['_qb_accounting'] = {'per_draw': acct.value,
                                        'team': team.value}
                return Outcome.ok(
                    'QB_LAYER_OK', value=o.value,
                    draw_generation_seconds=o.evidence.get(
                        'draw_generation_seconds'),
                    qb_frame_sha256=fh.value,
                    n_qb_games=o.evidence.get('n_qb_games'),
                    n_draws=o.evidence.get('n_draws'),
                    draw_cells=o.evidence.get('draw_cells'),
                    warnings=[f'known limitation: {k}'
                              for k in QBV1.KNOWN_LIMITATIONS]
                    + list(team.evidence.get('warnings') or []))
            # A STAGE MAY NOT CLAIM AN ACCEPTED SPEC AND PRODUCE NOTHING.
            # Six stages carried strings like 'P4C system C ACCEPTED' while
            # returning {} and reporting PASS. The accepted research baseline
            # exists; a PRODUCTION IMPLEMENTATION of it does not, and the
            # pipeline said nothing about the difference.
            if _st == 'team_environment' and fx.get('team_volume'):
                o = TV.forecast(args.season, args.week, fx.get('team_ids', []),
                                m=fx.get('qb_draws', 200), seed=args.seed)
                if o.state is not State.PASS:
                    return o
                fx['_team_volume'] = o.value
                return Outcome.ok(
                    'TEAM_ENVIRONMENT_OK', value={'n': len(o.value)},
                    implemented=True, spec_version=TV.SPEC_VERSION,
                    n_metrics=len(TV.METRICS),
                    warnings=[f'known limitation: {k}'
                              for k in TV.KNOWN_LIMITATIONS])
            _v = fx.get(_k)
            if not _v:
                return Outcome.ok(
                    'STAGE_DECLARED_UNIMPLEMENTED', value={},
                    detail=f'{_st}: the accepted research baseline {_s!r} has '
                           f'no production implementation. Declared as debt '
                           f'rather than reported as a successful forecast.',
                    implemented=False, layer=_k)
            return Outcome.ok(f'{_st.upper()}_OK', value=_v, implemented=True)
        p.run_stage(stage, _model, declared_inputs=['h_history', 'q_pos_mean'],
                    spec_version=spec)

    # --- 11. joint reconciliation ---------------------------------------
    def _joint():
        if fx.get('joint_fails'):
            return RF.refuse('JOINT_RECONCILIATION_FAILURE',
                             'joint_reconciliation',
                             'team totals could not be reconciled', run_id)
        if fx.get('accounting_fails'):
            return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING',
                             'joint_reconciliation',
                             'team and player totals do not reconcile', run_id)
        j = dict(fx.get('joint', {}))
        if fx.get('_qb_draws_out') is not None:
            x = QBACC.reconcile_cross_layer(
                fx['_qb_draws_out'], receiving=fx.get('receiving_yard_draws'),
                receiving_td=fx.get('receiving_td_draws'))
            if x.state is State.FAIL:
                return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING',
                                 'joint_reconciliation',
                                 f'{x.code}: {x.detail}', run_id)
            # DEFERRED is carried into the artifact as OWED, never as passed.
            j['qb_cross_layer'] = {'state': x.state.value, 'code': x.code,
                                   'owed': x.evidence.get('owed') if x.state is State.DEFERRED
                                   else None}
            j['qb_accounting'] = fx.get('_qb_accounting')
        return Outcome.ok('JOINT_RECONCILED', value=j)
    p.run_stage('joint_reconciliation', _joint,
                declared_inputs=['player_draws', 'team_volume'],
                spec_version='minimum-viable production coupling')

    # --- 12. player draws / 13. scoring / 14. sealing --------------------
    def _draws():
        """Assemble every layer's draws into one player-keyed structure.

        Previously this returned fx['draws'] -- a fixture key nothing ever set
        -- so the stage passed with {} while the QB layer's real draws were
        computed and thrown away. The rehearsal sealed 16 artifacts containing
        zero forecasts and reported PASS on all of them.
        """
        import numpy as _np
        out, produced = {}, {}
        D = fx.get('_qb_draws_out')
        rows = fx.get('qb_rows') or []
        if D is not None and rows:
            for i, r in enumerate(rows):
                pid = r['gsis_id']
                out.setdefault(pid, {})['qb'] = {
                    f: {'mean': float(D[f][i].mean()),
                        'p10': float(_np.quantile(D[f][i], 0.10)),
                        'p50': float(_np.quantile(D[f][i], 0.50)),
                        'p90': float(_np.quantile(D[f][i], 0.90))}
                    for f in QBV1.FIELDS}
            produced['qb_layer'] = len(rows)
        for _k in ('receiving', 'rushing', 'td', 'team_volume'):
            v = fx.get(f'{_k}_draws')
            if v:
                produced[_k] = len(v)
        return Outcome.ok('DRAWS_BUILT', value=out,
                          n_players_with_draws=len(out),
                          layers_producing_draws=produced,
                          layers_absent=[k for k in
                                         ('receiving', 'rushing', 'td',
                                          'team_volume')
                                         if k not in produced])
    p.run_stage('player_draws', _draws,
                declared_inputs=['joint'], spec_version='nfl-player-draw-1')
    p.run_stage('scoring', lambda: Outcome.ok(
        'SCORED', value='downstream view only; never an upstream input'),
        declared_inputs=['draws'], spec_version='deterministic')

    def _seal():
        # AN ARTIFACT WITH NO FORECASTS IS NOT A FORECAST ARTIFACT. Without
        # this the pipeline sealed 16 of 16 games carrying `distributions: {}`
        # and reported PASS -- absence read as success, inside the production
        # path itself.
        _dr = next((r for r in p.results if r.stage == 'player_draws'), None)
        _dist = (_dr.value if _dr is not None and _dr.value
                 else fx.get('distributions') or {})
        # Which model layers declared themselves unimplemented. Written
        # plainly: an earlier one-liner mixed union and difference, where `-`
        # binds tighter than `|`, so a None survived into sorted() and the
        # sealing stage raised on all 16 games.
        _absent = sorted({r.stage for r in p.results
                          if r.code == 'STAGE_DECLARED_UNIMPLEMENTED'})
        _completeness = 'COMPLETE' if not _absent else 'PARTIAL_PLAYER_COVERAGE'
        if not _dist:
            return RF.refuse('EMPTY_FORECAST_ARTIFACT', 'artifact_sealing',
                             'no model layer produced a player distribution, '
                             'so there is nothing to seal. Sealing an empty '
                             'artifact would report success for a run that '
                             'forecast nothing.', run_id)
        if fx.get('sealing_fails'):
            return RF.refuse('ARTIFACT_SEALING_FAILURE', 'artifact_sealing',
                             'the artifact failed its own contract', run_id)
        art = {
            'game_id': args.game_id, 'kickoff_utc': kickoff,
            'written_at': args.written_at,
            'source_captures': [{'source': k, 'sha256': v['sha256'],
                                 'retrieved_at': v['retrieved_at']}
                                for k, v in src.items()],
            'model_arm': args.arm, 'spec_hash': run_id,
            'code_commit': commit, 'seed_protocol': f'per-row seed {args.seed}',
            'feature_set_hash': hashlib.sha256(
                json.dumps(sorted(src)).encode()).hexdigest()[:32],
            'eligibility_verdict': 'PASS',
            'player_ids': [q['gsis_id'] for q in fx.get('players', [])],
            'team_ids': fx.get('team_ids', []),
            'distributions': _dist,
            'completeness': _completeness,
            'absent_layers': _absent,
            'excluded_unidentified': fx.get('_excluded_unidentified', []),
            'contract_version': ART.CONTRACT_VERSION,
        }
        v = ART.validate(art)
        if v.state is not State.PASS:
            return RF.refuse('ARTIFACT_SEALING_FAILURE', 'artifact_sealing',
                             f'{v.code}: {v.detail[:200]}', run_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / 'forecast_artifact.json').write_text(
            json.dumps(art, indent=1, sort_keys=True) + '\n')
        return Outcome.ok('ARTIFACT_SEALED', value=ART.artifact_id(art))
    p.run_stage('artifact_sealing', _seal, declared_inputs=['draws'],
                spec_version=ART.CONTRACT_VERSION)

    summary = p.summary()
    summary['execution_identity'] = execution_identity(args, src, commit)
    summary['code_commit'] = commit
    summary['dry_run'] = bool(args.dry_run)
    summary['prospective_eligible'] = False if args.dry_run else None
    # publication is a SEPARATE gate and is checked last, never assumed
    pub = AUTH.may_publish()
    summary['publication'] = {'state': pub.state.value, 'code': pub.code,
                              'detail': pub.detail[:200]}
    p.out_dir.mkdir(parents=True, exist_ok=True)
    (p.out_dir / 'run_status.json').write_text(
        json.dumps(summary, indent=1, default=str) + '\n')
    RF.persist(p.refusals, p.out_dir)
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--season', type=int, required=True)
    ap.add_argument('--week', type=int, required=True)
    ap.add_argument('--game-id', required=True)
    ap.add_argument('--arm', required=True, choices=ARMS)
    ap.add_argument('--written-at', required=True,
                    help='REQUIRED. There is no wall-clock default for a '
                         'scientific clock.')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--seed', type=int, default=20260908)
    ap.add_argument('--dry-run', action='store_true',
                    help='historical fixture run; NEVER prospective evidence')
    ap.add_argument('--fixtures', default=None)
    a = ap.parse_args(argv)
    fx = json.loads(pathlib.Path(a.fixtures).read_text()) if a.fixtures else {}
    s = build(a, fx)
    print(f"run {s['run_id']}  arm {s['arm']}  status {s['status']}  "
          f"{s['elapsed_s']:.3f}s"
          + ('  [DRY RUN -- not prospective evidence]' if a.dry_run else ''))
    for r in s['stages']:
        mark = {'PASS': 'ok  ', 'BLOCKED': 'STOP', 'FAIL': 'FAIL'}.get(
            r['state'], r['state'])
        print(f"  {mark} {r['stage']:<24}{r['code']}")
        if r['state'] != 'PASS':
            print(f"       {r['detail'][:160]}")
    print(f"  publication: {s['publication']['code']}")
    return 0 if s['status'] == 'SEALED' else 1


if __name__ == '__main__':
    sys.exit(main())
