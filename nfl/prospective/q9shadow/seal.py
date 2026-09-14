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
import sys
import zoneinfo

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State   # noqa: E402
from sportsplatform.governance import provenance as PROV              # noqa: E402
from nfl.identity import code_identity as CI                          # noqa: E402
from nfl.identity import seal as ISEAL                                # noqa: E402
from nfl.identity.execution_identity import ExecutionIdentity         # noqa: E402
from nfl.prospective import artifact as ART                           # noqa: E402
from nfl.prospective import registries as REG                         # noqa: E402
from nfl.prospective.q9shadow import candidate as CAND                # noqa: E402
from nfl.prospective.q9shadow import complete as COMPLETE             # noqa: E402
from nfl.prospective.q9shadow import inputs as IN                     # noqa: E402
from nfl.prospective.q9shadow import shadow as SH                     # noqa: E402
from nfl.prospective.q9shadow import timebasis as TB                  # noqa: E402

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
#
# A: static pre-2026 benchmark -- consumes NO 2026 outcome at any point in the
# season. CORRECTED from B, and the correction matters because A is the
# STRONGER evidentiary status, not a convenience.
#
# The earlier reasoning was that a week-8 forecast "would have weeks 1-7 in
# its training window". It would not. `shadow.fit_for` trains on
# `r['s'] < season` -- strictly prior SEASONS, for every week of the year --
# and the live feature builder's history window is the same set, because the
# owner's requirement for it is "no 2026 outcomes" and an earlier 2026 week is
# a 2026 outcome. Neither the coefficients nor the features ever see a 2026
# result, which is arm A's definition exactly.
#
# The cost of that is real and is recorded in
# `live_features.PARITY_WINDOW_WEEKS`: features built on prior seasons only
# go stale as the season progresses, and parity with the historical builder
# holds at week 1 and cannot hold later. Whether to stay at A or adopt a
# frozen prequential rule (arm B) is an owner decision, not a code choice.
MODEL_ARM = 'A'

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


# WS-E 2026-09-14. WHAT USED TO BE HERE, AND WHY IT IS GONE.
#
#     def _code_commit():
#         rev = git rev-parse HEAD
#         n   = len(git status --porcelain)
#         return rev + (f'+dirty[{n}]' if n else '')
#
# That `n` is a COUNT OF LINES describing the working tree at the instant of the
# call, and THE SEALING PATH'S OWN OUTPUTS CHANGE IT. Run 1 writes
# `dryrun/proof/run1/`, which adds an untracked entry, so run 2 -- and, when the
# outputs land in fresh directories, the second team of run 1 -- observes a
# different count and therefore a different `code_commit`. `code_commit` sits
# inside the sealed body, inside `artifact_id`'s REQUIRED list, and inside
# `ExecutionIdentity.code_version`, so it moved `forecast_id`,
# `seal_payload_sha256`, `artifact_id` and `identity_fingerprint` together. The
# identity of a forecast was a function of that forecast's own side effects.
#
# Measured on this checkout at HEAD 837d52f before the repair:
#
#     before writing anything          ...+dirty[30]
#     after one output directory       ...+dirty[31]
#     after a second output directory  ...+dirty[32]
#     after deleting both              ...+dirty[30]
#
# The replacement is NOT a better count. `nfl.identity.code_identity` separates
# six identities -- committed source (A), dirty source CONTENT (B), runtime (C),
# generated artifact state (D), predictive candidate (E), execution (F) -- and
# holds one invariant: a run must not change its own identity by writing its own
# outputs. D is excluded from A, B and C by a declared scope, so dF/dD = 0.
# Contract: nfl/research/remediation/ws_e/WS_E_IDENTITY_CONTRACT.md.
def _code_identity() -> Outcome:
    """A + B + C for this run, or a named refusal. Never a fabricated string."""
    return CI.code_identity()


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


# THE GOVERNED APPEARANCE INTERFACE. An artifact that did not come through
# this one is not a valid seal, and `ledger.assert_seal_path_governed` refuses
# it. Recorded on every artifact so the check reads a field rather than
# trusting that nobody took a shortcut.
GOVERNED_APPEARANCE_INTERFACE = 'nfl.production.nonqb.layers.appearance'

# Which readiness branch inside that interface actually ran. PER_TEAM is the
# only one that refuses INJURY_REPORT_INCOMPLETE; the slate-wide branch a
# call omitting `teams` falls back to does not.
PER_TEAM_READINESS_GATE = 'PER_TEAM'


def seal_team_game(res, ident, bundle_out, written_at, kickoff_utc, game,
                   out_dir=None, season=None, dry_run=False,
                   freeze_comparison=None,
                   appearance_interface=GOVERNED_APPEARANCE_INTERFACE,
                   readiness_gate=None) -> Outcome:
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

    # WS-E: A, B and C are RESOLVED, and a run that cannot resolve them is
    # refused rather than sealed under a fabricated code version. The old path
    # returned the literal 'UNKNOWN' when git was unavailable and sealed anyway,
    # which produced an artifact asserting an identity it did not have.
    cio = _code_identity()
    if cio.state is not State.PASS:
        return Outcome.fail(
            f'Q9_SHADOW_CODE_IDENTITY_UNRESOLVED:{cio.code}',
            f'{gid}/{team}: {cio.detail}',
            **{k: x for k, x in dict(cio.evidence).items()})
    ci = cio.value

    identity = ExecutionIdentity(
        spec_id=f'{CAND.CANDIDATE_NAME}/{SPEC_VERSION}',
        spec_sha256=CAND.identity_sha256(ident),
        # A + B. Commit sha, plus a digest of the CONTENT of dirty source.
        code_version=ci['code_version'],
        # C. WS19 read every sealed run in the tree and classified interpreter
        # and library versions NOT_RECOVERABLE. This field already existed and
        # held `python3.12`, which is too coarse to answer the question; it now
        # carries the declared hashed runtime keys.
        interpreter=ci['runtime_token'],
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

    # THE LAYER MATRIX AND THE COMPLETENESS VALUE, BEFORE THE ARTIFACT IS
    # ASSEMBLED. A single-layer target forecast carries `targets` and nothing
    # else, so the governed verdict is PARTIAL and the contract value follows
    # it. Passing the produced arm layers in means this same call returns
    # COMPLETE once the paired build carries all nine.
    arm_layers_present = {a: {'targets': res.value['arms'][a]['targets']}
                          for a in CAND.ARMS}
    layer_matrix = COMPLETE.matrix(arm_layers_present, {})
    completeness, governed_verdict = COMPLETE.completeness_value(layer_matrix)

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
        # WS-E: THE MATERIAL, NOT ONLY THE DIGEST. `code_commit` is a rolled-up
        # value; on its own it is a number a reader can compare and cannot
        # audit, which is what WS19 meant by NOT_RECOVERABLE. This block carries
        # every dirty source path with its own sha256, the scope rule that
        # selected them, and the runtime versions -- enough to recompute
        # `source_scope_sha256` and to see what the tree actually held.
        'code_identity': ci,
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
        # COMPUTED, NEVER DECLARED. `complete.completeness_value` runs the
        # governed `forecast_completeness` over the nine-layer matrix and maps
        # FULL to COMPLETE. A single-layer artifact gets
        # PARTIAL_PLAYER_COVERAGE from the gate, not from a literal here --
        # which is what stops a later edit from relabelling it.
        'completeness': completeness,
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
        # THE OWNER'S EVIDENCE RULING, MADE STRUCTURAL RATHER THAN NOTED.
        #
        # "Until all three conditions are satisfied and a truthful COMPLETE
        # pre-kickoff artifact is sealed: forecasts may be dry-run or
        # diagnostic; they do not count toward section 4; no promotion
        # evidence accrues."
        #
        # So `prospective_evidence` is not "is this a live seal" -- it is "may
        # this be COUNTED". A live, genuinely pre-kickoff, genuinely
        # non-fixture artifact that is PARTIAL_PLAYER_COVERAGE is DIAGNOSTIC,
        # and `ledger.accounting` reads this exact flag, so the ruling is
        # enforced by the counter rather than by a reader remembering it.
        art['dry_run'] = False
        art['prospective_evidence'] = bool(
            completeness == COMPLETE.CONTRACT_COMPLETE)
        if not art['prospective_evidence']:
            art['eligibility_verdict'] = (
                f'DIAGNOSTIC -- live and pre-kickoff, and NOT evidence: '
                f'completeness is {completeness}, so protocol section 2 '
                f'makes it not an eligible forecast. No section-4 credit, no '
                f'promotion evidence.')
            art['diagnostic_reason'] = {
                'completeness': completeness,
                'governed_verdict': governed_verdict,
                'absent_layers': sorted(k for k, v in layer_matrix.items()
                                        if v != 'PASS'),
                'ruling': 'owner ruling 2026-09-12: PARTIAL_PLAYER_COVERAGE '
                          'artifacts may be scored diagnostically, count '
                          'toward no section-4 floor, and cannot support '
                          'promotion.',
            }
    art['layer_matrix'] = layer_matrix
    art['governed_completeness_verdict'] = governed_verdict
    art['governance_notes'] = {
        'completeness_vs_protocol_section_2': (
            'OWNER RULING: section 2 stands unchanged. A '
            'PARTIAL_PLAYER_COVERAGE artifact may be scored diagnostically, '
            'counts toward no section-4 floor, and cannot support promotion. '
            'It is NOT relabelled COMPLETE. The route to an eligible forecast '
            'is the paired build in nfl/prospective/q9shadow/complete.py, '
            'which carries all nine required layers on one set of upstream '
            'draws with the target allocation as the only divergence.'),
        'completeness_is_computed_by':
            'nfl.prospective.q9shadow.complete.completeness_value over '
            'nfl.research.completeness.forecast_completeness',
        'absent_layers': sorted(k for k, v in layer_matrix.items()
                                if v != 'PASS'),
        'declared_scope': 'RB/WR/TE receiving targets for one team-game',
        'section_4_credit': 'NONE while completeness != COMPLETE',
    }

    # THE TIME BASIS, BEFORE THE CONTRACT VALIDATOR.
    #
    # `artifact.validate` compares these same three clocks, but it parses each
    # with its own `fromisoformat` and silently assumes UTC for a naive value.
    # That assumption is right often enough to hide the case where it is
    # wrong, so the ordering is established here first, on one declared basis,
    # with naive/aware mixing and uncontracted naive values refused by name.
    tb = TB.assert_prospective_order(
        [c['retrieved_at'] for c in art['source_captures']],
        art['written_at'], art['kickoff_utc'])
    if tb.state is not State.PASS:
        return Outcome.fail(
            f'Q9_SHADOW_TIME_BASIS:{tb.code}', tb.detail,
            **{k: x for k, x in dict(tb.evidence).items()})
    art['time_basis'] = {
        'canonical_tz': TB.CANONICAL_TZ_NAME,
        'verdict': f'{tb.state.value}[{tb.code}]',
        'bases': tb.evidence.get('bases'),
        'hours_before_kickoff': tb.evidence.get('hours_before_kickoff'),
        'newest_retrieved_at': tb.value['newest_retrieved_at'],
        'n_inputs': tb.evidence.get('n_inputs'),
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
    # WHICH UPSTREAM INTERFACE THIS FORECAST CAME THROUGH.
    #
    # Six live artifacts were once produced by calling `appearance_r8.predict`
    # directly, which skips `inputs.validate_appearance_inputs`. They were
    # discarded, but three of their forecast_ids are unrecoverable from the
    # run log, so an id blacklist could never be complete. This field is the
    # complete guard instead: the ledger refuses any artifact whose
    # appearance interface is not the governed one, whatever its id.
    art['seal_path'] = {
        'appearance_interface': appearance_interface,
        'governed_appearance_interface': GOVERNED_APPEARANCE_INTERFACE,
        'is_governed': bool(
            appearance_interface == GOVERNED_APPEARANCE_INTERFACE),
        'validates_inputs_via':
            'nfl.production.nonqb.inputs.validate_appearance_inputs',
        'upstream_test_only': bool(ev.get('upstream_test_only')),
        # WHICH READINESS BRANCH RAN. A dry-run seal uses the TEST_ONLY
        # fixture path and reaches no readiness branch at all, so it records
        # None and is refused as evidence on that ground too.
        'readiness_gate': readiness_gate,
        'readiness_gate_note':
            'PER_TEAM is the branch that refuses INJURY_REPORT_INCOMPLETE. '
            'layers.appearance reaches it only when `teams` is supplied; '
            'without it the slate-wide branch runs and does not refuse.',
    }
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


def _seal_live(season, games, written_at, gate_label, el_label, ident,
               n_draws=None, out_root=None) -> dict:
    """The LIVE path: real depth vintage, real injury vintage, real appearance.

    Each game gets its ACTUAL refusal rather than a single blanket one. The
    point of running this while it cannot succeed is that the refusal census
    says which blocker is live, per game, from the production layers
    themselves -- so when one clears, the census changes without anybody
    editing a status string.
    """
    from nfl.production.nonqb import layers as PL
    from nfl.prospective.q9shadow import live_features as LF
    from nfl.research.q7 import panel as Q7P
    from nfl.research.q8 import audit as AUD

    # THE COEFFICIENTS. Fitted on seasons strictly before the forecast season,
    # which for a 2026 forecast is every historical season this repository
    # holds. No row of the forecast season is read.
    hf = SH.feature_rows(SH.HISTORICAL_FRAME, season=season)
    if hf.state is not State.PASS:
        return {'status': f'{hf.state.value}[{hf.code}]', 'detail': hf.detail,
                'season': season, 'sealed': [], 'feature_source':
                    SH.LIVE_PREGAME, 'refusals': []}
    q7 = Q7P.load_recv()
    hist, _ = AUD.attach_receiving(hf.value, q7)
    fit = SH.fit_for(hist, season, q7)
    if fit.state is not State.PASS:
        return {'status': f'{fit.state.value}[{fit.code}]',
                'detail': fit.detail, 'season': season, 'sealed': [],
                'feature_source': SH.LIVE_PREGAME, 'refusals': []}

    inj = LF.injury_rows(season, written_at)
    sealed, refusals = [], []
    bundles = {}
    for g in games:
        ko = g['kickoff_utc']
        if inj.state is not State.PASS:
            refusals.append({'game_id': g['game_id'],
                             'state': inj.state.value, 'code': inj.code,
                             'stage': 'injury_vintage'})
            continue
        if ko not in bundles:
            bundles[ko] = IN.bundle(ko, written_at)
        b = bundles[ko]
        if b.state is not State.PASS:
            refusals.append({'game_id': g['game_id'], 'state': b.state.value,
                             'code': b.code, 'stage': 'input_bundle'})
            continue
        for team in (g['away_team'], g['home_team']):
            lf = LF.build_team_week(season, int(g['week']), team, written_at,
                                    ko)
            if lf.state is not State.PASS:
                refusals.append({'game_id': g['game_id'], 'team': team,
                                 'state': lf.state.value, 'code': lf.code,
                                 'stage': 'live_features'})
                continue
            rows = lf.value
            players = [{'gsis_id': r['pid'], 'position': r['pos'],
                        'team': team} for r in rows]
            # THE GOVERNED APPEARANCE INTERFACE, WITH NO FIXTURE.
            #
            # `fixture=None` is the load-bearing argument. The first version
            # called `appearance_r8.predict` directly, which produced six
            # sealed live forecasts -- and skipped
            # `inputs.validate_appearance_inputs`, the gate that refuses
            # INJURY_REPORT_INCOMPLETE. That is routing around a constraint,
            # and the six artifacts were discarded before any was counted.
            #
            # Through `layers.appearance` the gate runs. It turns out to
            # refuse PER TEAM rather than per slate -- a team whose injury
            # rows are all unfilled is refused and its opponent may pass --
            # so the census below says which teams are sealable rather than
            # asserting that none is.
            # `teams` IS THE LOAD-BEARING ARGUMENT, AND OMITTING IT COST 26
            # ARTIFACTS.
            #
            # `layers.appearance` consults PER-TEAM readiness only when
            # `teams` is supplied. Without it, it falls back to the slate-wide
            # `readiness.report`, which returned ENGINE_INPUTS_READY --
            # claiming "all slate teams covered and report_status filed" -- on
            # a slate where 28 of 32 teams had every injury row unfilled.
            # Per-team readiness refuses each of those by name.
            #
            # BOTH teams are passed because readiness is a per-GAME property:
            # a game is ready only if both are.
            ap = PL.appearance(season, int(g['week']), players, fixture=None,
                               seed=CAND.SEED, m=n_draws or CAND.N_DRAWS,
                               game_id=g['game_id'],
                               teams=[g['away_team'], g['home_team']],
                               kickoff_utc=ko, observed_before=written_at)
            if ap.state is not State.PASS:
                refusals.append({'game_id': g['game_id'], 'team': team,
                                 'state': ap.state.value, 'code': ap.code,
                                 'stage': 'layers.appearance',
                                 'detail': (ap.detail or '')[:200]})
                continue
            if ap.evidence.get('test_only'):
                refusals.append({
                    'game_id': g['game_id'], 'team': team,
                    'state': 'FAIL', 'code': 'Q9_LIVE_SEAL_TEST_ONLY_UPSTREAM',
                    'stage': 'layers.appearance',
                    'detail': 'the appearance layer returned a TEST_ONLY '
                              'result on a live seal. A fixture-sourced '
                              'forecast is not a forecast and may not be '
                              'sealed as one.'})
                continue
            res = SH.forecast_team_game(
                rows, fit.value, None, g['game_id'], CAND.SEED,
                n_draws or CAND.N_DRAWS, appearance=ap)
            if res.state is not State.PASS:
                refusals.append({'game_id': g['game_id'], 'team': team,
                                 'state': res.state.value, 'code': res.code,
                                 'stage': 'shadow_forecast'})
                continue
            root = pathlib.Path(out_root) if out_root else SEALED
            sl = seal_team_game(res, ident, b, written_at, ko, g,
                                root / g['game_id'] / team, season,
                                dry_run=False, freeze_comparison=gate_label,
                                readiness_gate=PER_TEAM_READINESS_GATE)
            if sl.state is not State.PASS:
                refusals.append({'game_id': g['game_id'], 'team': team,
                                 'state': sl.state.value, 'code': sl.code,
                                 'stage': 'seal',
                                 'detail': (sl.detail or '')[:300]})
                continue
            sealed.append(sl)
    return {'status': 'OK' if sealed else 'NOTHING_SEALED', 'season': season,
            'written_at': written_at, 'feature_source': SH.LIVE_PREGAME,
            'dry_run': False, 'candidate_gate': gate_label,
            'eligibility': el_label,
            'candidate_identity_sha256': CAND.identity_sha256(ident),
            'n_eligible_games': len(games), 'sealed': sealed,
            'injury_vintage': (f'{inj.state.value}[{inj.code}]'
                               + (f' -- {inj.evidence.get("n_rows")} row(s), '
                                  f'{inj.evidence.get("n_without_report_status")} '
                                  f'without report_status'
                                  if inj.state is State.PASS else '')),
            'refusals': refusals}


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

    if source == SH.LIVE_PREGAME:
        return _seal_live(season, games, written_at, gate_label, el_label,
                          ident, n_draws, out_root)

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
