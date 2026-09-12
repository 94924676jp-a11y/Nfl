"""Seal a Q9 shadow forecast before kickoff, or refuse by name.

    python3.12 -m nfl.prospective.q9shadow.seal --season 2026        # live
    python3.12 -m nfl.prospective.q9shadow.seal --dry-run-season 2025

WHAT IS SEALED, ITEM BY ITEM, BECAUSE THE DIRECTIVE LISTS IT

    exact Q9 candidate hash        candidate.identity_sha256, compared field by
                                   field against the pre-season freeze
    all input hashes               one ConsumedPartition per selected source,
                                   INSIDE the execution identity so the
                                   fingerprint moves when an input is swapped
    feature-schema hash            candidate identity
    coefficient hash               candidate identity
    upstream appearance artifact   named, with its spec hash
    team-budget artifact           the frozen P4B point and residual pool,
                                   each hashed
    RNG seed / draw count          seed_protocol
    forecast written_at            the consumed clock; selection is bounded
                                   by it, so retrieved_at <= written_at holds
                                   by construction
    kickoff                        from the pregame projection of the schedule
    cutoff basis                   which clock the cutoff came from
    fallback counters              both named Q9 fallbacks plus the baseline's
                                   own degenerate case, so the counts compare
    production interface version   the layers module source hash

THE ORDER THAT MAKES ANY OF IT MEAN ANYTHING

    retrieved_at  <=  written_at  <  kickoff

enforced twice, on purpose, by two modules that were written for different
reasons: `nfl.identity.seal.seal_forecast` checks it against the execution
identity's partitions, and `nfl.prospective.artifact.validate` checks it
against the artifact's own source captures. Neither was written for this task
and neither is reimplemented here.

WHY THE SCHEDULE IS PROJECTED BEFORE IT IS READ. The schedules file carries
`home_score`, `away_score` and `result` in the same row as `gameday` and
`gametime`. Reading the row to find kickoff would put the final score one
dictionary lookup from the sealing path. Only the pregame columns are lifted
out, and the projection is the enforcement.

NO POST-KICKOFF MUTATION. `append_seal` refuses a second seal for the same
forecast_id with different content, and `artifact.assert_not_mutated` refuses
an artifact edited in place. A correction is a NEW artifact naming what it
supersedes.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import subprocess
import sys
import zoneinfo

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State   # noqa: E402
from sportsplatform.governance import provenance as PROV              # noqa: E402
from nfl.identity import seal as ISEAL                                # noqa: E402
from nfl.identity.execution_identity import ExecutionIdentity         # noqa: E402
from nfl.prospective import artifact as ART                           # noqa: E402
from nfl.prospective import registries as REG                         # noqa: E402
from nfl.prospective.q9shadow import candidate as CAND                # noqa: E402
from nfl.prospective.q9shadow import inputs as IN                     # noqa: E402
from nfl.prospective.q9shadow import shadow as SH                     # noqa: E402

SPEC_VERSION = 'q9-shadow-seal-1'

# nflverse publishes `gametime` in US/Eastern. Resolved by the tz database
# rather than by a hand-rolled date range; see `schedule_pregame`.
_EASTERN = zoneinfo.ZoneInfo('America/New_York')
HERE = _REPO / 'nfl' / 'prospective' / 'q9shadow'
SEALED = HERE / 'sealed'
SEAL_LEDGER = HERE / 'Q9_SHADOW_SEAL_LEDGER.jsonl'

# THE DRY-RUN ROOT IS A DIFFERENT ROOT, AND THAT IS THE POINT.
#
# A dry-run seal exercises this exact code path on frozen historical features
# so that determinism and the inability to read an outcome can be DEMONSTRATED
# rather than asserted. It is not a forecast, so:
#
#   * it writes under `dryrun/`, never under `sealed/`;
#   * it appends to its own ledger, so a dry-run seal can never be counted as
#     a prospective one by a reader who globbed the wrong file;
#   * its kickoff is SYNTHETIC and labelled synthetic -- the 2025 kickoffs are
#     in the past, and a seal claiming to precede one of them would be the
#     backfill the whole protocol exists to forbid;
#   * its candidate identity is NOT compared to the 2026 freeze, because a
#     dry run at season Y fits on seasons < Y and therefore holds different
#     coefficients by construction. Claiming freeze parity there would be
#     false; the comparison is recorded as NOT_APPLICABLE with the reason.
#
# `nfl.prospective.q9shadow.ledger` refuses a dry-run row as evidence by
# reading these same two flags, so the label is load-bearing rather than
# decorative.
DRYRUN = HERE / 'dryrun'
DRYRUN_SEAL_LEDGER = HERE / 'Q9_SHADOW_DRYRUN_SEAL_LEDGER.jsonl'
DRYRUN_KICKOFF_OFFSET_HOURS = 24
SCHEDULES = _REPO / 'nfl' / 'vintage'

# The ONLY schedule columns the sealing path may read. `home_score`,
# `away_score`, `result`, `total` and `overtime` are realised outcomes and
# `spread_line` / `total_line` / the moneylines are market quantities, which
# this project refuses everywhere.
SCHEDULE_PREGAME_COLUMNS = ('game_id', 'season', 'game_type', 'week',
                            'gameday', 'gametime', 'away_team', 'home_team',
                            'location', 'roof', 'surface', 'stadium_id')

# The arm this candidate is registered under in the artifact contract.
# B: frozen-spec prequential. The hurdle's stage-1 coefficients are fitted on
# seasons strictly earlier than the forecast season by a rule frozen before
# the season, which is exactly what arm B describes. It is NOT arm A: arm A
# consumes no 2026 outcome all season, and a week-8 forecast under this rule
# would have weeks 1-7 in its training window.
MODEL_ARM = 'B'

# Which accounting invariants this artifact can actually answer. The Q9 shadow
# forecast allocates receiving targets and nothing else, so the QB-layer
# invariants are NOT_APPLICABLE rather than DEFERRED: a debt implies the check
# is owed on this artifact, and it is not -- there is no QB layer in it.
DRAW_INVARIANTS = ('draw_set_non_empty', 'draw_index_shared',
                   'draw_encoding_lossless', 'draw_artifact_integrity',
                   'draw_summary_consistency')


def _parse(ts):
    d = dt.datetime.fromisoformat(str(ts).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(
        timespec='seconds').replace('+00:00', 'Z')


def _code_commit():
    try:
        out = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=str(_REPO),
                             capture_output=True, text=True, timeout=20)
        rev = out.stdout.strip() or 'UNKNOWN'
    except (OSError, subprocess.SubprocessError):
        return 'UNKNOWN'
    try:
        st = subprocess.run(['git', 'status', '--porcelain'], cwd=str(_REPO),
                            capture_output=True, text=True, timeout=20)
        n = len([x for x in st.stdout.splitlines() if x.strip()])
    except (OSError, subprocess.SubprocessError):
        n = -1
    return rev + (f'+dirty[{n}]' if n else '')


def schedule_pregame(season) -> Outcome:
    """The pregame projection of the schedule. Outcome columns never leave it."""
    hits = sorted(SCHEDULES.glob('schedules.*.csv.gz'))
    if not hits:
        return Outcome.blocked(
            'Q9_SHADOW_SCHEDULE_ABSENT',
            f'no schedules capture under {SCHEDULES}. A kickoff time cannot '
            f'be guessed and a forecast without one cannot assert it was '
            f'written before the game.', cause=Cause.DATA)
    path = hits[-1]
    out = []
    with gzip.open(path, 'rt', newline='') as fh:
        for r in csv.DictReader(fh):
            if str(r.get('season')) != str(season):
                continue
            if (r.get('game_type') or 'REG') != 'REG':
                continue
            # THE PROJECTION. Everything not named is dropped here, before any
            # other line of this module can see it.
            p = {k: r.get(k) for k in SCHEDULE_PREGAME_COLUMNS}
            day, tm = p.get('gameday'), p.get('gametime') or '00:00'
            if not day:
                continue
            # nflverse `gametime` is US/Eastern, so the UTC offset is +4h
            # under DST and +5h outside it and the regular season spans the
            # change (it ends on the first Sunday in November, which is a
            # game day).
            #
            # THE FIRST VERSION APPROXIMATED THE BOUNDARY as 14 March to 1
            # November and was wrong by an hour on exactly the Sunday the
            # clocks go back -- a week-8 or week-9 game day. An hour of slack
            # on `kickoff_utc` is an hour in which a forecast written AFTER
            # kickoff would pass `written_at < kickoff`, which is the one
            # clock this whole package rests on. `zoneinfo` knows the rule;
            # a hand-rolled range does not.
            try:
                naive = dt.datetime.fromisoformat(f'{day}T{tm}:00')
            except ValueError:
                continue
            eastern = naive.replace(tzinfo=_EASTERN)
            p['kickoff_utc'] = eastern.astimezone(
                dt.timezone.utc).isoformat().replace('+00:00', 'Z')
            p['kickoff_offset_hours_from_eastern'] = round(
                -eastern.utcoffset().total_seconds() / 3600.0, 2)
            p['kickoff_timezone'] = 'America/New_York'
            out.append(p)
    if not out:
        return Outcome.blocked(
            'Q9_SHADOW_SCHEDULE_EMPTY_FOR_SEASON',
            f'{path.name} carries no REG game for {season}. An empty read is '
            f'an error, not an empty slate.', cause=Cause.DATA, season=season)
    leaked = sorted(set(out[0]) - set(SCHEDULE_PREGAME_COLUMNS)
                    - {'kickoff_utc', 'kickoff_offset_hours_from_eastern',
                       'kickoff_timezone'})
    if leaked:
        return Outcome.fail(
            'Q9_SHADOW_SCHEDULE_PROJECTION_LEAKED',
            f'{leaked} survived the pregame projection.', leaked=leaked)
    return Outcome.ok('Q9_SHADOW_SCHEDULE_PREGAME', value=out,
                      detail=f'{len(out)} REG game(s) for {season} from '
                             f'{path.name}, {len(SCHEDULE_PREGAME_COLUMNS)} '
                             f'pregame column(s) only',
                      capture=path.name, n_games=len(out))


def eligible_games(season, now=None) -> Outcome:
    """Games whose kickoff is still ahead. Nothing already played is eligible.

    A game that has kicked off can never become eligible retroactively:
    protocol section 2 says a late forecast is not eligible at any margin, and
    section 1 says week 1 may not be backfilled.
    """
    sch = schedule_pregame(season)
    if sch.state is not State.PASS:
        return sch
    cut = _parse(now) if now else dt.datetime.now(dt.timezone.utc)
    ahead = [g for g in sch.value if _parse(g['kickoff_utc']) > cut]
    behind = len(sch.value) - len(ahead)
    if not ahead:
        return Outcome.not_applicable(
            'Q9_SHADOW_NO_GAME_AHEAD_OF_NOW',
            f'all {len(sch.value)} REG game(s) for {season} have kicked off '
            f'as of {cut.isoformat()}. There is nothing to seal, and a played '
            f'game may not be entered retroactively.',
            n_games=len(sch.value))
    return Outcome.ok(
        'Q9_SHADOW_ELIGIBLE_GAMES', value=sorted(
            ahead, key=lambda g: (g['kickoff_utc'], g['game_id'])),
        detail=f'{len(ahead)} game(s) ahead of {cut.isoformat()}; {behind} '
               f'already played and permanently ineligible',
        n_ahead=len(ahead), n_behind=behind)


def _verdicts(draws_path, n_draws, arms, summary_ok) -> list:
    """One verdict per declared invariant, classified from the table."""
    vs = []
    for name in ART.HARD_INVARIANTS + ART.DIAGNOSTIC_INVARIANTS:
        if name == 'draw_set_non_empty':
            o = (Outcome.ok('DRAW_SET_NON_EMPTY', value=len(arms))
                 if arms else Outcome.fail('DRAW_SET_EMPTY', 'no arm produced '
                                           'a draw matrix'))
        elif name == 'draw_index_shared':
            widths = {int(np.asarray(a['targets']).shape[0]) for a in
                      arms.values()}
            o = (Outcome.ok('DRAW_INDEX_SHARED', value=sorted(widths))
                 if widths == {n_draws} else
                 Outcome.fail('DRAW_INDEX_RAGGED',
                              f'draw widths {sorted(widths)} against '
                              f'{n_draws}'))
        elif name in ('draw_encoding_lossless', 'draw_artifact_integrity'):
            o = (Outcome.ok(f'{name.upper()}_OK', value=str(draws_path.name))
                 if draws_path.exists() else
                 Outcome.fail('DRAW_ARTIFACT_MISSING', str(draws_path)))
        elif name == 'draw_summary_consistency':
            o = (Outcome.ok('DRAW_SUMMARY_CONSISTENT', value=True)
                 if summary_ok else
                 Outcome.fail('DRAW_SUMMARY_INCONSISTENT',
                              'the stored zero probability does not '
                              'recompute from the stored draws'))
        elif ART.INVARIANTS[name]['class'] == ART.HARD:
            o = Outcome.not_applicable(
                'Q9_SHADOW_LAYER_NOT_IN_THIS_ARTIFACT',
                f'{name} is a quarterback-layer invariant. This artifact '
                f'allocates receiving targets only, so the check has nothing '
                f'to evaluate. NOT_APPLICABLE rather than DEFERRED: a debt '
                f'would claim the check is owed on this artifact, and it is '
                f'not owed -- there is no QB layer in it.')
        else:
            o = Outcome.ok(
                'Q9_SHADOW_DIAGNOSTIC_RECORDED',
                value='receiving-target allocation only',
                detail='the diagnostic is recorded; this artifact carries no '
                       'QB layer and no other non-QB layer')
        vs.append(ART.verdict(name, o))
    return vs


def seal_team_game(res, ident, bundle_out, written_at, kickoff_utc, game,
                   out_dir=None, season=None, dry_run=False,
                   freeze_comparison=None) -> Outcome:
    """Build, validate, seal and write one team-game shadow forecast."""
    ev = res.evidence
    team, gid = ev['team'], ev['game_id']
    iset = bundle_out.value
    game_date = game['gameday']

    # ---- leakage, per source, against the game date. Two questions, asked
    # separately, by the module that already separates them.
    parts = IN.partitions(iset, written_at, game_date)
    leaks = []
    for p in parts:
        u = PROV.assert_usable_for(p.provenance, game_date)
        if u.state is State.FAIL:
            leaks.append({'partition_id': p.partition_id, 'code': u.code})
    if leaks and not dry_run:
        return Outcome.fail(
            'Q9_SHADOW_INPUT_LEAKAGE',
            f'{gid}/{team}: {len(leaks)} consumed partition(s) carry '
            f'information from on or after the game date: {leaks}',
            leaks=leaks)

    identity = ExecutionIdentity(
        spec_id=f'{CAND.CANDIDATE_NAME}/{SPEC_VERSION}',
        spec_sha256=CAND.identity_sha256(ident),
        code_version=_code_commit(),
        interpreter=f'python{sys.version_info.major}.{sys.version_info.minor}',
        seed={'seed': ev['seed'], 'n_draws': ev['n_draws'],
              'policy': ev['rng_policy']},
        partitions=tuple(parts))

    out_dir = pathlib.Path(out_dir or (SEALED / gid / team))
    out_dir.mkdir(parents=True, exist_ok=True)
    draws_path = out_dir / 'shadow_target_draws.npz'
    payload = {f'{a}__targets': res.value['arms'][a]['targets']
               for a in CAND.ARMS}
    for a in CAND.ARMS:
        y = res.value['arms'][a]['yards']
        if y is not None:
            payload[f'{a}__receiving_yards'] = y
    payload['budget'] = res.value['budget']
    payload['appearance'] = res.value['appearance']
    payload['p_hurdle'] = res.value['p_hurdle']
    payload['base_share'] = res.value['base_share']
    np.savez_compressed(draws_path, **payload)
    draws_sha = hashlib.sha256(draws_path.read_bytes()).hexdigest()

    players = SH.summarise_players(res.value)
    # The stored summary must recompute from the stored draws, exactly. This
    # is the invariant a reader trusts on sight.
    re_read = np.load(draws_path)
    summary_ok = True
    for row in players:
        T = re_read[f'{row["arm"]}__targets']
        j = res.value['players'].index(row['player_id'])
        if round(float((T[:, j] == 0).mean()), 6) != row['zero_probability']:
            summary_ok = False
            break

    art = {
        'contract_version': ART.CONTRACT_VERSION,
        'game_id': gid,
        'kickoff_utc': kickoff_utc,
        'written_at': written_at,
        'model_arm': MODEL_ARM,
        'spec_hash': CAND.identity_sha256(ident),
        'code_commit': identity.code_version,
        'seed_protocol': identity.seed,
        'feature_set_hash': ident['feature_schema_sha16'],
        'eligibility_verdict': 'SHADOW_ONLY -- NOT PROMOTED, NOT PUBLISHED',
        'player_ids': list(res.value['players']),
        'team_ids': [team],
        'source_captures': [
            {'source': p.source, 'sha256': p.sha256,
             'retrieved_at': p.provenance.retrieved_at,
             'partition_id': p.partition_id, 'url': p.url}
            for p in parts],
        'distributions': {r['player_id']: {'receiving': {
            'targets': {k: r[k] for k in (
                'arm', 'zero_probability', 'mean_targets', 'p50_targets',
                'p90_targets', 'mean_targets_given_positive',
                'n_positive_draws')},
        }} for r in players if r['arm'] == CAND.ARM_CANDIDATE},
        'completeness': 'PARTIAL_PLAYER_COVERAGE',
        'distributions_source': 'MODEL',
        'draw_artifact': str(draws_path.relative_to(_REPO)),
        'draw_artifact_sha256': draws_sha,
        # THE ARRAY-LEVEL IDENTITY, BESIDE THE CONTAINER-LEVEL ONE.
        # `draw_artifact_sha256` hashes the .npz FILE, which is what the
        # contract's draw_artifact_integrity invariant re-reads and verifies.
        # `draw_content_sha256` hashes the draw VALUES, so the forecast's
        # identity does not depend on a container format. Both are carried
        # because they answer different questions and this project has paid
        # for conflating a file hash with a content hash before.
        'draw_content_sha256': SH.draws_sha256(res.value),
    }
    art['accounting_verdicts'] = _verdicts(
        draws_path, ev['n_draws'], res.value['arms'], summary_ok)

    # WHY completeness IS PARTIAL AND WHAT THAT COSTS. Protocol section 2
    # defines an eligible forecast as one with completeness == COMPLETE, and
    # this artifact covers RB/WR/TE receiving targets only. The truthful label
    # is therefore PARTIAL_PLAYER_COVERAGE, and the consequence -- that these
    # artifacts are scored but are not "eligible forecasts" in section 2's
    # sense -- is recorded rather than resolved by relabelling. Loosening a
    # gate to admit one's own candidate is the one move this project never
    # makes.
    if dry_run:
        # STAMPED BEFORE VALIDATION, so there is no window in which a dry-run
        # artifact exists without saying so.
        art['dry_run'] = True
        art['prospective_evidence'] = False
        art['eligibility_verdict'] = (
            'DRY_RUN -- NOT A PROSPECTIVE FORECAST, NOT EVIDENCE. Frozen '
            'historical features, synthetic kickoff, separate ledger.')
        art['dry_run_declarations'] = {
            'kickoff_is_synthetic': True,
            'synthetic_kickoff_rule': f'written_at + '
                                      f'{DRYRUN_KICKOFF_OFFSET_HOURS}h',
            'real_game_date': game_date,
            'feature_season': season,
            'freeze_comparison': freeze_comparison,
            'input_leakage_checks_failing': leaks,
            'why_leakage_is_recorded_not_refused': (
                'the committed historical panel contains the outcomes of the '
                'seasons in it -- that is what a panel IS. A dry run on '
                'historical features therefore cannot pass the pregame '
                'leakage check, and the honest handling is to record the '
                'failing check and mark the artifact as not evidence, rather '
                'than to suppress the check or to call the artifact a '
                'forecast.'),
        }
    else:
        art['dry_run'] = False
        art['prospective_evidence'] = True
    art['governance_notes'] = {
        'completeness_vs_protocol_section_2': (
            'section 2 requires completeness == COMPLETE for an eligible '
            'forecast; this artifact is a single-layer receiving-target '
            'forecast and is truthfully PARTIAL_PLAYER_COVERAGE. Whether a '
            'single-layer artifact can be an eligible forecast for a '
            'single-layer candidate is an owner ruling, not a label choice.'),
        'absent_layers': ['qb', 'rushing', 'td', 'other non-QB layers'],
        'declared_scope': 'RB/WR/TE receiving targets for one team-game',
    }

    v = ART.validate(art)
    if v.state is not State.PASS:
        return Outcome.fail(
            f'Q9_SHADOW_ARTIFACT_INVALID:{v.code}', v.detail,
            **{k: x for k, x in dict(v.evidence).items()})

    # WHAT THE SEALED BODY IS COMPUTED OVER, AND WHY IT IS NOT THE WHOLE DICT.
    #
    # The first version hashed `art` entire, and `art` carries
    # `draw_artifact` -- the path the draws happened to be written to. Two
    # seals of byte-identical inputs into two different directories therefore
    # produced two different forecast_ids, which the dry-run proof caught as
    # a determinism failure. It was not the forecast that differed; it was
    # the output location, which is a property of the machine that ran the
    # seal and not of the evidence. Same lesson as `sealed_index._rel`.
    #
    # So the location is excluded and the CONTENT hash of the same draws is
    # what the body carries. `draw_artifact` and `draw_artifact_sha256` stay
    # in the written artifact, where the integrity invariant reads them.
    SEAL_BODY_EXCLUDED = ('draw_artifact', 'draw_artifact_sha256')
    body = json.dumps({k: v for k, v in art.items()
                       if k not in SEAL_BODY_EXCLUDED},
                      sort_keys=True, default=str).encode()
    sealed = ISEAL.seal_forecast(
        forecast_id=f'Q9SH-{hashlib.sha256(body).hexdigest()[:16]}',
        game_id=gid, kickoff_utc=kickoff_utc, payload=body,
        identity=identity,
        consumed_partition_ids=[p.partition_id for p in parts],
        written_at=written_at)
    if sealed.state is not State.PASS:
        return sealed
    s = sealed.value
    art['forecast_id'] = s.forecast_id
    art['artifact_id'] = ART.artifact_id(art)
    art['seal'] = {'seal_sha256': s.seal_sha256(),
                   'payload_sha256': s.payload_sha256,
                   'payload_excludes': list(SEAL_BODY_EXCLUDED),
                   'payload_excludes_why': (
                       'the output location is a property of the machine that '
                       'ran the seal, not of the forecast. The draws are '
                       'identified by draw_content_sha256, which is inside '
                       'the payload.'),
                   'identity_fingerprint': s.identity_fingerprint,
                   'consumed_partition_ids': list(s.consumed_partition_ids)}
    art['candidate'] = {
        'name': CAND.CANDIDATE_NAME, 'promoted': False,
        'prospective_candidate': True, 'shadow_only': True,
        'identity_sha256': CAND.identity_sha256(ident),
        'freeze_artifact': REG.CANDIDATES[CAND.CANDIDATE_NAME][
            'freeze_artifact'],
        'coefficient_sha16': ident['coefficient_sha16'],
        'feature_schema_sha16': ident['feature_schema_sha16'],
        'one_target_floor': ident['one_target_floor'],
        'named_fallbacks': ident['named_fallbacks'],
        'production_interface_sha16': ident['production_interface_sha16'],
        'appearance_artifact': ident['appearance_artifact'],
        'appearance_spec_sha16': ident['appearance_spec_sha16'],
        'budget_point_sha16': ident['budget_point_sha16'],
        'budget_residual_pool_sha16': ident['budget_residual_pool_sha16'],
        'budget_estimator': ident['budget_estimator'],
    }
    art['cutoff'] = {'cutoff_utc': written_at,
                     'cutoff_basis': 'information_set.observed_before',
                     'cutoff_basis_note': 'the consumed clock: selection of '
                                          'every input was bounded by it',
                     'newest_input_observed_at': max(
                         (p.provenance.retrieved_at for p in parts),
                         default=None)}
    art['arms'] = {'production': CAND.ARM_PRODUCTION,
                   'candidate': CAND.ARM_CANDIDATE,
                   'shared_upstream': True,
                   'rng_policy': ev['rng_policy']}
    art['fallback_counters'] = ev['fallback_states']
    art['reconciliation'] = ev['max_absolute_reconciliation_error']
    art['input_bundle_sha256'] = IN.bundle_sha256(iset)
    art['absent_input_sources'] = sorted(iset.get('absent') or [])
    art['player_summary'] = players
    art['season'] = season
    art['team'] = team

    (out_dir / 'SEALED_FORECAST.json').write_text(
        json.dumps(art, indent=1, default=str) + '\n')
    app = ISEAL.append_seal(s, DRYRUN_SEAL_LEDGER if dry_run
                            else SEAL_LEDGER)
    return Outcome.ok(
        'Q9_SHADOW_FORECAST_SEALED', value=art,
        detail=f'{gid}/{team}: sealed {s.forecast_id} '
               f'{(_parse(kickoff_utc) - _parse(written_at)).total_seconds() / 3600:.2f}h '
               f'before kickoff; ledger {app.state.value}[{app.code}]',
        forecast_id=s.forecast_id, artifact_id=art['artifact_id'],
        seal_sha256=s.seal_sha256(), draw_artifact_sha256=draws_sha,
        identity_fingerprint=s.identity_fingerprint,
        ledger=f'{app.state.value}[{app.code}]',
        out_dir=str(out_dir.relative_to(_REPO)))


def seal_season(season, now=None, source=SH.HISTORICAL_FRAME, n_games=None,
                out_root=None, n_draws=None, written_at=None,
                dry_run=False) -> dict:
    """Attempt a seal for every eligible game. Refusals are the result too."""
    written_at = written_at or _now()
    if dry_run:
        # NOT COMPARED, AND THE REASON IS RECORDED. A dry run at season Y is
        # fitted on seasons < Y, so its coefficient hash differs from the 2026
        # freeze by construction. Asserting parity would be false; skipping
        # the comparison silently would be worse.
        gate_label = ('NOT_APPLICABLE[Q9_DRY_RUN_IDENTITY_NOT_COMPARED_TO_'
                      'FREEZE]')
    else:
        gate = CAND.assert_identical_to_freeze(season=season)
        gate_label = f'{gate.state.value}[{gate.code}]'
        if gate.state is not State.PASS:
            return {'status': gate_label, 'detail': gate.detail,
                    'season': season, 'sealed': [], 'feature_source': source,
                    'refusals': [], 'gate': dict(gate.evidence)}
    ident = CAND.identity(season)
    if dry_run:
        # THE SYNTHETIC, LABELLED KICKOFF. The real 2025 kickoffs are in the
        # past and a seal claiming to precede one would be a backfill.
        sch = schedule_pregame(season)
        if sch.state is not State.PASS:
            return {'status': f'{sch.state.value}[{sch.code}]',
                    'detail': sch.detail, 'season': season, 'sealed': [],
                    'feature_source': source, 'refusals': []}
        ko = (_parse(written_at)
              + dt.timedelta(hours=DRYRUN_KICKOFF_OFFSET_HOURS)
              ).isoformat().replace('+00:00', 'Z')
        games = [dict(g, kickoff_utc=ko) for g in sch.value]
        games.sort(key=lambda g: g['game_id'])
        el_label = 'NOT_APPLICABLE[Q9_DRY_RUN_SYNTHETIC_KICKOFF]'
    else:
        el = eligible_games(season, now)
        el_label = f'{el.state.value}[{el.code}]'
        if el.state is not State.PASS:
            return {'status': el_label, 'detail': el.detail,
                    'season': season, 'sealed': [], 'refusals': [],
                    'feature_source': source, 'candidate_gate': gate_label}
        games = el.value
    games = games[:n_games] if n_games else games

    fr = SH.feature_rows(source, season=season)
    if fr.state is not State.PASS:
        return {'status': f'{fr.state.value}[{fr.code}]', 'detail': fr.detail,
                'season': season, 'sealed': [],
                'n_eligible_games': len(games), 'feature_source': source,
                'candidate_gate': gate_label,
                'refusals': [{'game_id': g['game_id'],
                              'state': fr.state.value, 'code': fr.code}
                             for g in games],
                'feature_source_evidence': dict(fr.evidence)}

    # The historical dry-run path. A live season never reaches here, because
    # `feature_rows(LIVE_PREGAME)` refuses above.
    import collections
    from nfl.research.q7 import panel as Q7P
    from nfl.research.q8 import audit as AUD
    q7 = Q7P.load_recv()
    rows, _ = AUD.attach_receiving(fr.value, q7)
    fit = SH.fit_for(rows, season, q7)
    if fit.state is not State.PASS:
        return {'status': f'{fit.state.value}[{fit.code}]',
                'detail': fit.detail, 'season': season, 'sealed': [],
                'feature_source': source, 'refusals': []}
    p_r8 = AUD.load_p_r8()
    groups = collections.defaultdict(list)
    for r in rows:
        if r['s'] == season:
            groups[(r['s'], r['w'], r['t'])].append(r)

    bundles = {}
    sealed, refusals = [], []
    for g in games:
        ko = g['kickoff_utc']
        if ko not in bundles:
            bundles[ko] = IN.bundle(ko, written_at)
        b = bundles[ko]
        if b.state is not State.PASS:
            refusals.append({'game_id': g['game_id'], 'state': b.state.value,
                             'code': b.code, 'detail': b.detail[:200]})
            continue
        for team in (g['away_team'], g['home_team']):
            key = (season, int(g['week']), team)
            if key not in groups:
                refusals.append({'game_id': g['game_id'], 'team': team,
                                 'state': 'BLOCKED',
                                 'code': 'Q9_SHADOW_NO_FEATURE_ROWS_FOR_TEAM'})
                continue
            grp = groups[key]
            p_appear = {r['pid']: float(p_r8.get(
                (r['s'], r['w'], r['t'], r['pid']), 0.0)) for r in grp}
            res = SH.forecast_team_game(
                grp, fit.value, p_appear, g['game_id'], CAND.SEED,
                n_draws or CAND.N_DRAWS)
            if res.state is not State.PASS:
                refusals.append({'game_id': g['game_id'], 'team': team,
                                 'state': res.state.value, 'code': res.code})
                continue
            root = pathlib.Path(out_root) if out_root else (
                DRYRUN if dry_run else SEALED)
            out_dir = root / g['game_id'] / team
            sl = seal_team_game(res, ident, b, written_at, ko, g, out_dir,
                                season, dry_run=dry_run,
                                freeze_comparison=gate_label)
            if sl.state is not State.PASS:
                refusals.append({'game_id': g['game_id'], 'team': team,
                                 'state': sl.state.value, 'code': sl.code,
                                 'detail': (sl.detail or '')[:300]})
                continue
            sealed.append(sl)
    return {'status': 'OK' if sealed else 'NOTHING_SEALED', 'season': season,
            'written_at': written_at, 'feature_source': source,
            'dry_run': bool(dry_run), 'candidate_gate': gate_label,
            'eligibility': el_label,
            'candidate_identity_sha256': CAND.identity_sha256(ident),
            'n_eligible_games': len(games), 'sealed': sealed,
            'refusals': refusals}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--games', type=int, default=None)
    ap.add_argument('--draws', type=int, default=None)
    ap.add_argument('--source', default=None, choices=list(SH.FEATURE_SOURCES))
    ap.add_argument('--now', default=None)
    ap.add_argument('--dry-run', action='store_true',
                    help='seal frozen historical features under dryrun/ with '
                         'a labelled synthetic kickoff; not evidence')
    a = ap.parse_args(argv)
    src = a.source or (SH.LIVE_PREGAME if a.season >= 2026
                       else SH.HISTORICAL_FRAME)
    out = seal_season(a.season, a.now, src, a.games, n_draws=a.draws,
                      dry_run=a.dry_run)
    print(f"season          : {out['season']}")
    print(f"feature source  : {out.get('feature_source')}")
    print(f"candidate gate  : {out.get('candidate_gate')}")
    print(f"eligible games  : {out.get('n_eligible_games')}")
    print(f"sealed          : {len(out['sealed'])}")
    print(f"refusals        : {len(out.get('refusals') or [])}")
    print(f"status          : {out['status']}")
    if out.get('detail'):
        print(f"detail          : {out['detail'][:400]}")
    for r in (out.get('refusals') or [])[:4]:
        print(f"  {r.get('game_id')} {r.get('team', '')}: "
              f"{r['state']}[{r['code']}]")
    for s in out['sealed'][:3]:
        print(f"  {s.detail}")
    return 0 if out['status'] == 'OK' else 1


if __name__ == '__main__':
    sys.exit(main())
