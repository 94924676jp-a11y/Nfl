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
from nfl.production import derived as DERIVED                       # noqa: E402
from nfl.production import candidate_mode as CAND                   # noqa: E402
from nfl.production import draws_artifact as DA                     # noqa: E402

ARMS = ('A', 'B', 'C')

# B14. WHICH INVARIANT A DRAW-ARTIFACT REFUSAL BELONGS TO.
#
# The hard/diagnostic classification itself lives in ONE place --
# `nfl.prospective.artifact.INVARIANTS` -- and this table only says which
# declared invariant a given refusal code is evidence about. Keeping the two
# apart is deliberate: a reader who wants to know what gates reads the
# registry, and nothing here can change a class.
DRAW_CODE_INVARIANT = {
    'DRAW_SET_EMPTY': 'draw_set_non_empty',
    'DRAW_SET_NO_DRAW_INDEX': 'draw_set_non_empty',
    'DRAW_LAYER_NO_ROWS': 'draw_set_non_empty',
    'DRAW_LAYER_NO_METRICS': 'draw_set_non_empty',
    'DRAW_MATRIX_NO_DRAWS': 'draw_set_non_empty',
    'DRAW_INDEX_RAGGED': 'draw_index_shared',
    'DRAW_INDEX_MANIFEST_MISMATCH': 'draw_index_shared',
    'DRAW_MATRIX_NOT_2D': 'draw_index_shared',
    'DRAW_MATRIX_ROW_MISMATCH': 'draw_index_shared',
    'DRAW_ENCODING_LOSSY': 'draw_encoding_lossless',
    'DRAW_MATRIX_NOT_FINITE': 'draw_encoding_lossless',
}
# Anything not named above is evidence about the container itself.
DRAW_CODE_INVARIANT_DEFAULT = 'draw_artifact_integrity'


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
               # The configuration is part of the identity. Without it a
               # candidate run and a baseline run of the same game would share
               # a run id while containing different numbers.
               'model_configuration': getattr(
                   args, 'model_configuration', None)
               or CAND.PRODUCTION_BASELINE,
               'sources': dict(sorted(source_hashes.items()))}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def code_commit() -> str:
    '''HEAD, plus an explicit dirty marker.

    This returned a bare HEAD with no working-tree check, so an artifact
    could name a commit while the code that produced it carried
    uncommitted changes -- observed live: a sealed artifact recorded
    72f0d13 while run_forecast.py held 125 modified lines. The artifact
    was not reproducible from the commit it named and said nothing about
    it. A dirty tree is now part of the identity rather than hidden, so
    `execution_identity` changes with it too.
    '''
    import subprocess
    try:
        h = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(_REPO),
                           capture_output=True, text=True,
                           timeout=20).stdout.strip()
        if not h:
            return 'UNKNOWN'
        d = subprocess.run(['git', 'status', '--porcelain'], cwd=str(_REPO),
                           capture_output=True, text=True, timeout=60).stdout
        n = len([x for x in d.splitlines() if x.strip()])
        return h if n == 0 else h + '+dirty[' + str(n) + ']'
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
    def _candidate_qb():
        """The QB half of the V1 candidate architecture, from the canonical
        entrypoint rather than from an internal-only rehearsal path.

        R2, C0 and A3G execute here. C3 and A1 need the receiving and rushing
        budgets, which the engine builds from the appearance layer -- and that
        layer is currently DEFERRED on the injury feed, so those two report as
        not reached rather than as satisfied. That is the honest state and it
        is written into the artifact; an operator must not read "candidate
        mode" as "every candidate component ran".
        """
        from nfl.production.nonqb import football_engine as FE
        fl = _mode['flags']
        qbp = [q for q in fx.get('players', [])
               if q.get('position') == 'QB' and q.get('gsis_id')]
        if not qbp:
            return RF.refuse('QB_SLATE_EMPTY', 'qb_layer',
                             'no quarterback on the roster for this game',
                             run_id)
        teams = list(fx.get('team_ids') or [])
        m = fx.get('qb_draws', 200)
        sl = FE.qb_slate(args.season, args.week, qbp, m=m, seed=args.seed,
                         include_cold_start=bool(fl.get('include_cold_start')))
        if sl.state is not State.PASS:
            return sl
        qb = sl.value
        qa = FE.QA.allocate(args.season, args.week, teams, qbp, m=m,
                            seed=args.seed)
        if qa.state is not State.PASS:
            return qa
        qb['allocation'] = qa.value
        gc = fl.get('game_coupling')
        tv = (FE.TV.forecast(args.season, args.week, teams, m=m,
                             seed=args.seed, joint_residuals=True,
                             game_pairs=[(teams[0], teams[1])],
                             game_coupling=gc)
              if gc and gc != 'none' and len(teams) == 2
              else FE.TV.forecast(args.season, args.week, teams, m=m,
                                  seed=args.seed))
        if tv.state is not State.PASS:
            return tv
        applied = ['C0'] if fl.get('include_cold_start') else []
        if gc and gc != 'none' and len(teams) == 2:
            applied.append('A3G')
        if fl.get('r2'):
            r2o = FE.apply_r2_level(qb, qa.value, tv, teams)
            if r2o.state is not State.PASS:
                return r2o
            qb = r2o.value
            applied.append('R2')
        # The two that need budgets the appearance layer has not produced.
        not_reached = [c for c, on in (('C3', fl.get('shared_pass') == 'c3'),
                                       ('A1', bool(fl.get('rushing_a1'))))
                       if on]
        fx['qb_rows'] = qb['rows']
        fx['_qb_draws_out'] = qb['draws']
        fx['_candidate_applied'] = sorted(applied)
        fx['_candidate_not_reached'] = sorted(not_reached)
        # EVERY DECLARED HARD INVARIANT GETS A VERDICT ON THIS PATH TOO.
        # The candidate path first shipped without them and the B14 gate
        # refused all 16 games with INVARIANT_VERDICT_MISSING -- the guard
        # working, on my own incomplete path. Silence is not a state.
        _inv = fx.setdefault('_inv', {})
        ident = QBV1.identity_check(qb['draws'])
        _inv['qb_dropback_identity'] = ident
        if ident.state is not State.PASS:
            return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', 'qb_layer',
                             ident.detail, run_id)
        acct = QBACC.reconcile_draws(qb['draws'])
        _inv['qb_per_draw_accounting'] = acct
        if acct.state is not State.PASS:
            return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', 'qb_layer',
                             f'{acct.code}: {acct.detail}', run_id)
        team = QBACC.reconcile_team(
            qb['draws'], qb['rows'],
            team_rush_draws=fx.get('team_rush_draws'),
            team_rushes_realised=fx.get('team_rushes_realised'))
        _inv['qb_team_accounting'] = team
        fx['_qb_team_warnings'] = list(team.evidence.get('warnings') or [])
        if team.state is not State.PASS:
            return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', 'qb_layer',
                             f'{team.code}: {team.detail}', run_id)
        fx['_qb_accounting'] = {'per_draw': acct.value, 'team': team.value}
        return Outcome.ok(
            'QB_LAYER_OK', value=qb['draws'],
            model_configuration=_mode['mode'],
            candidate_components_applied=sorted(applied),
            candidate_components_not_reached=sorted(not_reached),
            n_qb_games=len(qb['rows']),
            qb_level_owner=(qb.get('r2') or {}).get('level_owner'))

    # MODEL CONFIGURATION, RESOLVED ONCE AND CARRIED. An unknown name is a
    # refusal, never a fall-back to the baseline -- falling back would run the
    # PROMOTED model while the operator believed they were running the
    # candidate, which fails in the dangerous direction.
    _mode_o = CAND.resolve(getattr(args, 'model_configuration', None))
    if _mode_o.state is not State.PASS:
        return {'run_id': run_id, 'status': 'REFUSED',
                'stages': [{'stage': 'capture_validation', 'state': 'FAIL',
                            'code': _mode_o.code, 'detail': _mode_o.detail}],
                'publication': {'code': 'NFL1_NOT_AUTHORIZED'},
                'model_configuration': getattr(
                    args, 'model_configuration', None)}
    _mode = _mode_o.value

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
    # The five layers that exist in nfl/production/nonqb and are gated on a
    # captured input rather than on being unwritten.
    NONQB_CHAIN = ('appearance', 'participation', 'targets_carries',
                   'conversion', 'td_layer')

    def _nonqb_stage(_st):
        """The real layer's own outcome, or None to fall through.

        Returns whatever the layer returns -- PASS when the input is usable,
        DEFERRED/BLOCKED with the named condition when it is not. It never
        converts a block into a pass, and it never invents a probability.
        """
        try:
            from nfl.production.nonqb import layers as LY
        except Exception as e:                                # noqa: BLE001
            return Outcome.blocked(
                # Cause.DEPENDENCY, not Cause.CODE -- there is no CODE
                # member, and naming one made this handler raise
                # AttributeError, destroying the named refusal it
                # exists to produce.
                'NONQB_LAYER_IMPORT_FAILED', f'{type(e).__name__}: {e}',
                cause=Cause.DEPENDENCY)
        if _st == 'appearance':
            o = LY.appearance(args.season, args.week,
                              fx.get('players', []), fixture=None,
                              seed=args.seed, m=fx.get('qb_draws', 200),
                              teams=fx.get('team_ids'),
                              kickoff_utc=fx.get('kickoff_utc'),
                              game_id=args.game_id)
            fx['_appearance'] = o
            return o
        ap = fx.get('_appearance')
        if ap is None:
            # Downstream layers are only meaningful given the appearance
            # outcome. Its absence is reported, not silently skipped.
            return Outcome.blocked(
                'BLOCKED_UPSTREAM_APPEARANCE',
                f'{_st} needs the appearance outcome and it was not produced',
                cause=Cause.DATA)
        if _st == 'participation':
            o = LY.participation(ap, {}, m=fx.get('qb_draws', 200))
            fx['_participation'] = o
            return o
        pa = fx.get('_participation')
        if pa is None:
            return Outcome.blocked(
                'BLOCKED_UPSTREAM_PARTICIPATION',
                f'{_st} needs the participation outcome', cause=Cause.DATA)
        if _st == 'targets_carries':
            o = LY.targets_carries(pa, 'targets', [], [], ([], []), [], {},
                                   game_id=args.game_id,
                                   ordinal=args.season * 100 + args.week)
            fx['_targets_carries'] = o
            return o
        tc = fx.get('_targets_carries')
        if tc is None:
            return Outcome.blocked(
                'BLOCKED_UPSTREAM_OPPORTUNITY',
                f'{_st} needs the targets/carries outcome', cause=Cause.DATA)
        _ord = args.season * 100 + args.week
        if _st == 'conversion':
            o = LY.receiving_conversion(tc, [], {}, [], [], _ord)
            fx['_conversion'] = o
            return o
        cv = fx.get('_conversion')
        if cv is None:
            return Outcome.blocked(
                'BLOCKED_UPSTREAM_TD_INPUT',
                f'{_st} needs the conversion outcome', cause=Cause.DATA)
        return LY.td_layer(cv, [], {}, [], [], _ord)

    for stage, key, spec in (
            ('feature_build', 'features', 'prior-only, ordinal prefix cut'),
            ('team_environment', 'team_env', TV.SPEC_VERSION),
            ('appearance', 'appearance', 'P3 appearance'),
            ('participation', 'participation',
             'Stage2 ewma_hl2; governance INFORMATION_CONSTRAINED'),
            ('targets_carries', 'targets_carries',
             'P4C system C; governance DATA_BLOCKED'),
            ('conversion', 'conversion',
             'RC1 baseline; SIGNAL_WEAK; governance HOLD_CHARACTERIZED '
             '+ CALIBRATION_DEFECT'),
            ('td_layer', 'td',
             'TD2 pooled positional control; governance HOLD_TENTATIVE'),
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
                #
                # DERIVED ARTIFACTS FIRST. `qb2_lib.load()` reads
                # panel_enriched.pkl through p4c_build, and that artifact is
                # deliberately NOT committed -- it is regenerated from the
                # leaves under nfl/research/inputs. In a fresh checkout it is
                # simply absent, and the loader raised FileNotFoundError, which
                # the pipeline recorded as STAGE_RAISED. The whole 2026 week 1
                # slate refused on a Python traceback rather than a named
                # cause, and a traceback is not a refusal reason.
                #
                # `football_engine.qb_slate` already gated on this; the
                # production entrypoint did not. Same call, same order, so the
                # QB layer cannot depend on a copy someone happened to leave in
                # the research tree either.
                da = DERIVED.artifacts()
                if da.state is not State.PASS:
                    return RF.refuse('MODEL_ARTIFACT_MISSING', _st,
                                     f'{da.code}: {da.detail}', run_id)
                if _mode['candidate']:
                    o = _candidate_qb()
                    if o.state is not State.PASS:
                        return o
                    return o
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
                # B14. THE VERDICT IS KEPT AS AN OUTCOME, NOT A STRING.
                # These three already refused here, which is right and stays.
                # What was missing is that the artifact carried no record of
                # them at all, so a sealed artifact could not be interrogated
                # about the invariants it claims to satisfy -- only about the
                # ones that happened to stop the run.
                _inv = fx.setdefault('_inv', {})
                ident = QBV1.identity_check(o.value)
                _inv['qb_dropback_identity'] = ident
                if ident.state is not State.PASS:
                    return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', _st,
                                     ident.detail, run_id)
                acct = QBACC.reconcile_draws(o.value)
                _inv['qb_per_draw_accounting'] = acct
                if acct.state is not State.PASS:
                    return RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', _st,
                                     f'{acct.code}: {acct.detail}', run_id)
                team = QBACC.reconcile_team(
                    o.value, fx['qb_rows'],
                    team_rush_draws=fx.get('team_rush_draws'),
                    team_rushes_realised=fx.get('team_rushes_realised'))
                _inv['qb_team_accounting'] = team
                fx['_qb_team_warnings'] = list(team.evidence.get('warnings')
                                               or [])
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
            if not _v and _st in NONQB_CHAIN:
                # THE NON-QB CHAIN IS IMPLEMENTED. Reporting it as
                # "no production implementation" was false and it cost the
                # artifact its true refusal reason: `slate_rehearsal` calls
                # these same layers and gets
                # DEFERRED[INJURIES_2026_PUBLISHED_BUT_INSUFFICIENT] with the
                # cascade named beneath it, while the production entrypoint
                # said "unimplemented" and recorded PASS. A stage blocked on an
                # unusable input is not a stage that was never built, and an
                # operator reading the artifact could not tell which it was.
                #
                # Calling the real layer here means the artifact carries the
                # actual cause today, and that the feed arriving is an input
                # unblock rather than a code change.
                o = _nonqb_stage(_st)
                if o is not None:
                    if o.state is State.PASS:
                        return o
                    # A NON-QB LAYER THAT CANNOT RUN DOES NOT REFUSE THE GAME.
                    # It is a completeness dimension, not a required input:
                    # the accepted design seals the QB forecast and declares
                    # what is missing (`completeness`, `absent_layers`). That
                    # policy is preserved here and only the REASON improves --
                    # wiring the real layer in first made a deferred injury
                    # feed refuse all 16 games, which threw away a valid QB
                    # forecast over a layer that had never been required.
                    #
                    # No probability is emitted either way, so nothing is
                    # fabricated. The layer's OWN code and detail are kept, so
                    # the artifact says INJURY_REPORT_NOT_YET_FILED rather than
                    # the false 'no production implementation'. Required
                    # stages -- capture, identity, team environment, QB,
                    # reconciliation, draws, sealing -- keep halting.
                    return Outcome.not_applicable(
                        o.code, f'{_st}: {o.detail}'[:400],
                        implemented=True, layer=_k, blocked_layer=True,
                        layer_state=o.state.value)

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
            fx.setdefault('_inv', {})['qb_cross_layer_reconciliation'] = x
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
        """Assemble every layer's draws into ONE joint, replayable draw set.

        Previously this returned fx['draws'] -- a fixture key nothing ever set
        -- so the stage passed with {} while the QB layer's real draws were
        computed and thrown away. The rehearsal sealed 16 artifacts containing
        zero forecasts and reported PASS on all of them.

        B13. It then reduced every metric to mean/p10/p50/p90 and threw the
        draws away a second time. Four quantiles cannot produce CRPS, a log
        score, a PIT value, coverage at an unstored level, a tail probability
        or ANY dependence diagnostic -- the last of those is not recoverable by
        storing more quantiles, because a per-metric marginal summary has
        already discarded which draw went with which.

        So the draws themselves are written to a sidecar container on a shared
        draw index and referenced from the artifact by hash, and the quantile
        view is KEPT alongside as the convenient view it always was. The two
        are then checked against each other, so they cannot describe different
        runs.
        """
        inv = fx.setdefault('_inv', {})

        def _fail(o):
            """Attribute a draw refusal to the invariant it is evidence about."""
            inv[DRAW_CODE_INVARIANT.get(o.code, DRAW_CODE_INVARIANT_DEFAULT)] = o
            return o

        import numpy as _np
        ds = DA.DrawSet(run_id=run_id, game_id=args.game_id, seed=args.seed,
                        seed_protocol=f'per-row seed {args.seed}')
        produced = {}
        D = fx.get('_qb_draws_out')
        rows = fx.get('qb_rows') or []
        if D is not None and rows:
            o = ds.add_layer(
                'qb', [r['gsis_id'] for r in rows],
                {f: _np.asarray(D[f]) for f in QBV1.FIELDS},
                QBV1.SPEC_VERSION,
                'numpy default_rng([seed, ord, gsis_id]) -- one stream per '
                'row; columns are aligned, rows are independent')
            if o.state is not State.PASS:
                return _fail(o)
            produced['qb'] = len(rows)
        tv = fx.get('_team_volume')
        if tv:
            teams = sorted({t for (_m, t) in tv})
            mats = {m: _np.stack([_np.asarray(tv[(m, t)], float)
                                  for t in teams])
                    for m in TV.METRICS if all((m, t) in tv for t in teams)}
            if mats:
                o = ds.add_layer(
                    'team_volume', teams, mats, TV.SPEC_VERSION,
                    'nfl.production.seeds declared streams, per metric',
                    row_axis='team')
                if o.state is not State.PASS:
                    return _fail(o)
                produced['team_volume'] = len(teams)

        if not ds.arrays:
            # ABSENCE IS NOT SUCCESS, AND IT IS NAMED.
            #
            # Two different situations, and collapsing them would be the same
            # class of error this whole stage exists to end:
            #
            #  * NOTHING AT ALL. No model layer ran and no fixture was
            #    supplied, so there is no forecast. This is the declared
            #    refusal EMPTY_FORECAST_ARTIFACT, raised HERE rather than three
            #    stages later, so no model runs on a run that has already lost
            #    its forecast.
            #  * A DECLARED FIXTURE RUN. `fx['distributions']` was supplied,
            #    the artifact is already stamped TEST_ONLY and
            #    DISTRIBUTIONS_FROM_FIXTURE, and `artifact.validate` does not
            #    apply the model gates to it. There is genuinely no model draw
            #    set to preserve, and saying so is NOT_APPLICABLE with a
            #    reason -- not PASS, and never a claim that draws were stored.
            inv['draw_set_non_empty'] = Outcome.fail(
                'DRAW_SET_EMPTY',
                'no layer produced a draw matrix, so this run has no '
                'distribution to preserve. Emitting a quantile summary here '
                'would be four numbers with nothing behind them.')
            if not fx.get('distributions'):
                return RF.refuse(
                    'EMPTY_FORECAST_ARTIFACT', 'player_draws',
                    'no model layer produced a draw matrix, so there is no '
                    'distribution to preserve and nothing to seal.', run_id)
            return Outcome.not_applicable(
                'DRAW_SET_NOT_MODEL_PRODUCED',
                'no model layer produced draws; this run carries fixture '
                'distributions and its artifact is stamped TEST_ONLY, so '
                'there is no model draw set to preserve. This is NOT a '
                'forecast and the model gates do not apply to it.',
                distributions_source='FIXTURE_TEST_ONLY')
        inv['draw_set_non_empty'] = Outcome.ok(
            'DRAW_SET_PRESENT', value=len(ds.arrays),
            detail=f'{len(ds.arrays)} matrix(es) from {sorted(produced)}',
            layers=sorted(produced))

        w = ds.write(out_dir)
        if w.state is not State.PASS:
            return _fail(w)
        man = w.value
        inv['draw_encoding_lossless'] = Outcome.ok(
            'DRAW_ENCODING_LOSSLESS', value=sorted(
                {e['dtype'] for e in man['arrays'].values()}),
            detail='every matrix round-tripped exactly through its stored '
                   'dtype; nothing was clipped, rounded or rescaled to fit',
            dtypes=sorted({e['dtype'] for e in man['arrays'].values()}))
        inv['draw_index_shared'] = Outcome.ok(
            'DRAW_INDEX_SHARED', value=man['n_draws'],
            detail=f'all {man["n_matrices"]} matrix(es) share one draw index '
                   f'of width {man["n_draws"]}')
        # RE-READ FROM DISK. The write already verified itself; this checks the
        # file the artifact will actually reference, by the hash it will
        # actually record.
        inv['draw_artifact_integrity'] = DA.verify(
            out_dir / DA.DRAW_FILE_NAME, man)
        if inv['draw_artifact_integrity'].state is not State.PASS:
            return inv['draw_artifact_integrity']

        # The quantile view, KEPT -- now with a reference to the draws it came
        # from, so no number in the artifact is unaccompanied by its
        # distribution.
        out, summaries = {}, {}
        for i, r in enumerate(rows if (D is not None and rows) else []):
            pid = r['gsis_id']
            out.setdefault(pid, {})['qb'] = {}
            for f in QBV1.FIELDS:
                q = DA.quantile_view(ds.vector('qb', f, i))
                out[pid]['qb'][f] = dict(
                    q, draws_ref={'key': f'qb/{f}', 'row': i,
                                  'n_draws': man['n_draws'],
                                  'content_digest': man['content_digest']})
                summaries[f'qb/{f}/{pid}'] = q
        cons = DA.assert_summary_consistent(summaries, ds)
        inv['draw_summary_consistency'] = cons
        if cons.state is not State.PASS:
            return cons

        fx['_draw_manifest'] = man
        for _k in ('receiving', 'rushing', 'td'):
            v = fx.get(f'{_k}_draws')
            if v:
                produced[_k] = len(v)
        return Outcome.ok(
            'DRAWS_BUILT', value=out,
            detail=f'{man["n_draw_cells"]} draw cell(s) preserved across '
                   f'{man["n_matrices"]} matrix(es) on one draw index of '
                   f'{man["n_draws"]}; {len(out)} player quantile view(s) kept',
            n_players_with_draws=len(out),
            layers_producing_draws=produced,
            draw_artifact_sha256=man['file']['sha256'],
            draw_content_digest=man['content_digest'],
            n_draw_cells=man['n_draw_cells'],
            draw_bytes=man['file']['bytes'],
            layers_absent=[k for k in
                           ('receiving', 'rushing', 'td', 'team_volume')
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
        # A FIXTURE MAY NOT MASQUERADE AS MODEL OUTPUT. This fell back to
        # `fx['distributions']` -- a dict lifted verbatim out of the
        # --fixtures JSON -- with no trace in the artifact, so a six-line
        # fixture sealed numbers no model computed, the
        # EMPTY_FORECAST_ARTIFACT guard saw a non-empty dict and passed, and
        # eligibility_verdict read 'PASS'. Demonstrated live.
        #
        # The fixture path survives, because the stage-11-to-14 tests need it,
        # but it can no longer be mistaken for a forecast: the artifact
        # records where its numbers came from and stamps itself TEST_ONLY, so
        # provenance travels WITH the numbers instead of being inferable only
        # from how the run was invoked.
        _dist = _dr.value if _dr is not None and _dr.value else {}
        _dist_source = 'MODEL'
        if not _dist and fx.get('distributions'):
            _dist = fx['distributions']
            _dist_source = 'FIXTURE_TEST_ONLY'
        # Which model layers declared themselves unimplemented. Written
        # plainly: an earlier one-liner mixed union and difference, where `-`
        # binds tighter than `|`, so a None survived into sorted() and the
        # sealing stage raised on all 16 games.
        _absent = sorted({r.stage for r in p.results
                          if r.code == 'STAGE_DECLARED_UNIMPLEMENTED'
                          or (r.state == 'NOT_APPLICABLE'
                              and r.stage in NONQB_CHAIN)})
        _completeness = 'COMPLETE' if not _absent else 'PARTIAL_PLAYER_COVERAGE'
        _produced = sorted({r.stage for r in p.results if r.state == 'PASS'
                            and r.stage in ('qb_layer',) + NONQB_CHAIN})
        _eligibility = ('PASS' if _completeness == 'COMPLETE'
                        else 'PARTIAL|PRODUCED:' + ','.join(_produced)
                        + '|ABSENT:' + ','.join(_absent))
        if _dist_source != 'MODEL':
            _eligibility = 'TEST_ONLY|DISTRIBUTIONS_FROM_FIXTURE'
        if _mode['candidate']:
            # A candidate run says so in the field a reader would use to judge
            # eligibility, not only in a field they might not look at.
            _eligibility = (f'{CAND.V1_CANDIDATE}|APPLIED:'
                            + ','.join(fx.get('_candidate_applied') or [])
                            + '|NOT_REACHED:'
                            + ','.join(fx.get('_candidate_not_reached') or [])
                            + '|' + _eligibility)
        if not _dist:
            return RF.refuse('EMPTY_FORECAST_ARTIFACT', 'artifact_sealing',
                             'no model layer produced a player distribution, '
                             'so there is nothing to seal. Sealing an empty '
                             'artifact would report success for a run that '
                             'forecast nothing.', run_id)
        if fx.get('sealing_fails'):
            return RF.refuse('ARTIFACT_SEALING_FAILURE', 'artifact_sealing',
                             'the artifact failed its own contract', run_id)

        # ============================================================
        # B14. ACCOUNTING VERDICTS, AND THE GATE THEY DRIVE
        # ============================================================
        # The defect: verdicts were recorded as display strings and the run
        # continued, so an artifact could represent itself as a valid forecast
        # while carrying FAIL on an invariant the layer rests on.
        #
        # The three-way split is the owner's and is implemented exactly:
        #   HARD invariant FAIL/BLOCKED -> refuse to seal
        #   diagnostic disagreement     -> recorded, not a gate
        #   partial player coverage     -> `completeness`, which already works
        #
        # The classification is NOT decided here. It is read from
        # `artifact.INVARIANTS`, and `artifact.verdict` refuses to accept a
        # class from a call site, so no line in this file can promote a
        # diagnostic or demote an invariant.
        #
        # Scope: verdicts are attached when the numbers came from the MODEL. A
        # fixture-sourced artifact is already stamped TEST_ONLY and is not a
        # forecast, so gating it would assert something about a thing that is
        # declared not to be one.
        _verdicts = None
        if _dist_source == 'MODEL':
            # The diagnostics land in the run's own verdict map too, so
            # run_status.json carries all of them and not only the ones
            # some earlier stage happened to record.
            _inv = fx.setdefault('_inv', {})
            # --- diagnostics: recorded on EVERY run, never gating ---------
            _lims = sorted(QBV1.KNOWN_LIMITATIONS)
            _inv['qb_known_limitations'] = (
                Outcome.fail(
                    'QB_LAYER_KNOWN_LIMITATIONS',
                    'characterised weaknesses present in every run of this '
                    'layer: ' + ', '.join(_lims) + '. Measured and reported, '
                    'never smoothed away. This is a statement about how good '
                    'the model is, not about whether its numbers are '
                    'self-consistent, so it does not gate.',
                    limitations=_lims)
                if _lims else
                Outcome.ok('QB_LAYER_NO_KNOWN_LIMITATIONS', value=[],
                           detail='the layer declares none'))
            _warn = fx.get('_qb_team_warnings') or []
            _inv['qb_allocation_residual'] = (
                Outcome.fail(
                    'QB_ALLOCATION_RESIDUAL_PRESENT',
                    '; '.join(_warn)[:380], warnings=_warn)
                if _warn else
                Outcome.ok('QB_ALLOCATION_RESIDUAL_NONE', value=0,
                           detail='the team reconciliation raised no residual '
                                  'warning'))
            _inv['nonqb_layer_availability'] = (
                Outcome.fail(
                    'NONQB_LAYERS_UNAVAILABLE',
                    f'{len(_absent)} completeness layer(s) produced nothing '
                    f'this run: {_absent}. Carried by `completeness` as '
                    f'partial coverage; named here so the artifact says WHICH.',
                    absent=_absent)
                if _absent else
                Outcome.ok('NONQB_LAYERS_ALL_PRODUCED', value=[],
                           detail='every completeness layer produced output'))
            try:
                _verdicts = [ART.verdict(k, o) for k, o in sorted(_inv.items())]
            except (KeyError, TypeError) as exc:
                return RF.refuse('ARTIFACT_SEALING_FAILURE',
                                 'artifact_sealing', str(exc)[:300], run_id)
            _gate = ART.assert_hard_invariants(_verdicts)
            if _gate.state is not State.PASS:
                # THE GATE. A hard invariant that did not hold means there is
                # no valid forecast to publish, whatever else in the run
                # succeeded.
                return RF.refuse('ARTIFACT_SEALING_FAILURE', 'artifact_sealing',
                                 f'{_gate.code}: {_gate.detail}', run_id)
            fx['_gate'] = _gate

        _man = fx.get('_draw_manifest') or {}
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
            # NOT A LITERAL. This read 'PASS' unconditionally, asserting
            # eligibility for every run that reached sealing regardless
            # of what the run actually contained.
            'eligibility_verdict': _eligibility,
            'player_ids': [q['gsis_id'] for q in fx.get('players', [])],
            'team_ids': fx.get('team_ids', []),
            'distributions': _dist,
            'distributions_source': _dist_source,
            # WHICH MODEL PRODUCED THIS NUMBER, answered by the artifact
            # rather than by reconstructing an invocation.
            'model_configuration': _mode['mode'],
            'candidate_components': _mode['components'],
            'candidate_components_applied': fx.get('_candidate_applied') or [],
            'candidate_components_not_reached':
                fx.get('_candidate_not_reached') or [],
            'promoted': False,
            'prospective_eligible': False,
            'TEST_ONLY': _dist_source != 'MODEL',
            'completeness': _completeness,
            'absent_layers': _absent,
            'excluded_unidentified': fx.get('_excluded_unidentified', []),
            'contract_version': ART.CONTRACT_VERSION,
            # B13. The distribution itself, by hash. The bytes stay in the
            # sidecar; the artifact carries the identity that changes if any
            # single draw changes, plus the manifest a reader needs to open it.
            'draw_artifact_sha256': (_man.get('file') or {}).get('sha256'),
            'draw_artifact': _man or None,
            # B14. Every declared invariant's verdict travels WITH the numbers.
            'accounting_verdicts': _verdicts,
        }
        # A CANDIDATE RUN MAY NOT LOOK LIKE THE PROMOTED MODEL. Checked at the
        # seal, on the assembled artifact, so it cannot be satisfied by an
        # invocation-time flag that a later edit forgets to carry.
        nm = CAND.assert_not_promoted(_mode['mode'], art)
        if nm.state is State.FAIL:
            return RF.refuse('ARTIFACT_SEALING_FAILURE', 'artifact_sealing',
                             f'{nm.code}: {nm.detail[:220]}', run_id)
        v = ART.validate(art)
        if v.state is not State.PASS:
            return RF.refuse('ARTIFACT_SEALING_FAILURE', 'artifact_sealing',
                             f'{v.code}: {v.detail[:200]}', run_id)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / 'forecast_artifact.json').write_text(
            json.dumps(art, indent=1, sort_keys=True) + '\n')
        return Outcome.ok(
            'ARTIFACT_SEALED', value=ART.artifact_id(art),
            detail=(f'{(_man.get("n_draw_cells") or 0)} draw cell(s) '
                    f'referenced by sha256'
                    + (f'; {fx["_gate"].detail}'
                       if fx.get('_gate') is not None else '')),
            draw_artifact_sha256=(_man.get('file') or {}).get('sha256'),
            n_hard_invariants=len(ART.HARD_INVARIANTS),
            n_diagnostic_invariants=len(ART.DIAGNOSTIC_INVARIANTS),
            hard_owed=(fx['_gate'].evidence.get('hard_owed')
                       if fx.get('_gate') is not None else None),
            diagnostics_not_clean=(
                fx['_gate'].evidence.get('diagnostics_not_clean')
                if fx.get('_gate') is not None else None))
    p.run_stage('artifact_sealing', _seal, declared_inputs=['draws'],
                spec_version=ART.CONTRACT_VERSION)

    summary = p.summary()
    # The run's own record of the draw set and of every invariant verdict, so
    # `run_status.json` answers both B13 and B14 questions without opening the
    # artifact.
    _m = fx.get('_draw_manifest') or {}
    summary['draw_artifact'] = ({'sha256': (_m.get('file') or {}).get('sha256'),
                                 'bytes': (_m.get('file') or {}).get('bytes'),
                                 'n_draws': _m.get('n_draws'),
                                 'n_matrices': _m.get('n_matrices'),
                                 'n_draw_cells': _m.get('n_draw_cells'),
                                 'content_digest': _m.get('content_digest')}
                                if _m else None)
    summary['accounting_verdicts'] = [
        {'invariant': k, 'class': ART.INVARIANTS[k]['class'],
         'state': o.state.value, 'code': o.code}
        for k, o in sorted(fx.get('_inv', {}).items())
        if k in ART.INVARIANTS]
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
    ap.add_argument('--model-configuration', dest='model_configuration',
                    default=CAND.PRODUCTION_BASELINE,
                    help='PRODUCTION_BASELINE (default) or V1_CANDIDATE. '
                         'The candidate configuration is explicit and '
                         'never the default; an unknown name is refused '
                         'rather than falling back to the baseline.')
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
