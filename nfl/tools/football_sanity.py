"""Football contradictions are refused BEFORE the optimizer sees a number. Named, never warned.

WHY THIS STAGE EXISTS. On 2026 week 4 the showdown pipeline reported PASS six times and handed over
a legal, validated portfolio in which both starting quarterbacks had been charged a backup's
appearance rate. Every mechanical gate was green; nothing in the system could tell that the number
was football-wrong. A green pipeline is not enough. This stage reads the projection artifact the
selector is about to consume and refuses, by name, the contradictions a football reader would catch.

Each refusal is a statement about the artifact, not about the model. The gate does not know whether
a projection is accurate; it knows when a projection cannot be what it claims to be.

TOLERANCES ARE MEASURED, NOT INVENTED. On the 2026 W4 PIT@CLE artifact, carries and targets
reconciled to the club total at 0.0000 for both clubs; quarterback pass attempts carried a residual
of -0.0118 (PIT, club 35.6866) and -0.0055 (CLE, club 33.2599) -- an unallocated ghost of 0.03% of
club volume. RECONCILE_TOL is declared at 0.1% of the club total with those figures as its basis.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'football-sanity-1'

#: Fraction of the club total within which player allocations must reconcile. Basis: measured
#: residuals of 0.03% (pass attempts) and 0.0000 (carries, targets) on 2026_04_PIT_CLE.
RECONCILE_TOL = 0.001
BANDS = ('FRINGE', 'ROTATIONAL', 'SECONDARY', 'PRIMARY', 'ALPHA')
PROJECTED_STATES = ('PROJECTED', 'PROJECTED_COLD_START', 'PROJECTED_KICKER', 'PROJECTED_DST')
SKILL = ('QB', 'RB', 'WR', 'TE')

# The named refusals, each with the contradiction it catches.
STARTER_PENALISED = 'STARTER_CARRIES_APPEARANCE_PENALTY'
RANK1_NOT_STARTER = 'RANK1_QB_NOT_PREDICTED_STARTER'
PASS_ATT_UNRECONCILED = 'CLUB_PASS_ATTEMPTS_NOT_RECONCILED'
CARRIES_UNRECONCILED = 'CLUB_CARRIES_NOT_RECONCILED'
TARGETS_UNRECONCILED = 'CLUB_TARGETS_NOT_RECONCILED'
INACTIVE_OPPORTUNITY = 'INACTIVE_PLAYER_HAS_OPPORTUNITY'
ABOVE_CEILING = 'ROLE_ABOVE_CEILING_WITHOUT_REASON'
#: A quarterback is not a receiving target. Measured over the panel the quarterback group takes
#: 0.05 per cent of club targets (each row carries that number as
#: allocation.targets.position_group_share_measured), about 0.02 targets a game. One full target
#: a game is the football ceiling this gate refuses above unless the row says why
#: (allocation.targets.explicit_reason). Found 2026-10-02: 5.04 on Deshaun Watson, because the
#: allocator used his pass-attempt depth share as his target prior.
QB_TARGETS_CEILING_PER_GAME = 1.0
QB_RECEIVER_VOLUME = 'QB_TARGETS_ABOVE_CEILING_WITHOUT_REASON'
#: The mirror image: a club's pass attempts belong to its quarterbacks. The allocator keeps one pool
#: per field, so when a quarterback's claim is capped the attempts flow to receivers' trick-play
#: claims -- which is how the pre-repair W4 artifact reconciled to its club total while its
#: starters were short. One attempt a game across a club's non-quarterbacks is the football ceiling.
NON_QB_PASS_ATT_CEILING_PER_GAME = 1.0
NON_QB_PASS_ATTEMPTS = 'NON_QB_PASS_ATTEMPTS_ABOVE_CEILING'
ZERO_UNNAMED = 'ZERO_WITHOUT_NAMED_STATE'
MISSING_AS_ZERO = 'MISSING_INPUT_READ_AS_ZERO'
UNIT_MISSING = 'KICKER_OR_DST_MISSING'
PASS_CODE = 'FOOTBALL_SANITY_PASS'
FAIL_CODE = 'FOOTBALL_CONTRADICTION'


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def assess(artifact: dict, absent=(), clubs=None, units=('K', 'DST')) -> Outcome:
    """Refuse the artifact on the first class of contradiction found; report every instance.

    `artifact` is the projection artifact (`rows`, `team_volume`). `absent` are the people ruled
    out of tonight's game (official inactives + declared not playing), by name. `clubs` names the
    two clubs on the slate; when omitted they are read from the rows.
    """
    rows = (artifact or {}).get('rows') or {}
    tv = (artifact or {}).get('team_volume') or {}
    if not rows:
        return Outcome.fail('FOOTBALL_SANITY_NO_ROWS', 'no projection rows to examine',
                            cause=Cause.DATA)
    absent = {str(a) for a in (absent or ())}
    clubs = sorted(clubs or {v.get('team') for v in rows.values() if v.get('team')})
    problems: dict[str, list] = {}

    def flag(code, msg):
        problems.setdefault(code, []).append(msg)

    for v in rows.values():
        nm, pos, club = v.get('name'), v.get('position'), v.get('team')
        aa = v.get('appearance_adjustment') or {}
        projected = v.get('projection_state') in PROJECTED_STATES and _num(v.get('dk_points'))

        # 1-2. a starter is never charged a backup's appearance probability.
        if aa.get('applied') is True:
            if v.get('is_predicted_starter') is True or aa.get('depth_rank') == 1:
                flag(STARTER_PENALISED, f'{nm} ({club} {pos}): starter, yet '
                                        f'appearance penalty applied ({aa.get("reason")})')
        # The evidence of starting must come from the ROW, not from the adjustment block's own
        # self-report: the pre-repair W4 artifact recorded no depth_rank inside the block, so a gate
        # reading only the block could not see the contradiction it was built to catch. ALPHA role
        # on a quarterback is the independent statement.
        starter_evidence = (aa.get('depth_rank') == 1 or v.get('is_predicted_starter') is True
                            or (pos == 'QB' and v.get('role_band') == 'ALPHA'))
        if pos == 'QB' and starter_evidence and aa.get('applied') is True \
                and 'NOT_PREDICTED_STARTER' in str(aa.get('reason')):
            flag(RANK1_NOT_STARTER, f'{nm} ({club}): role {v.get("role_band")}, '
                                    f'depth_rank {aa.get("depth_rank")}, yet reason '
                                    f'{aa.get("reason")} with appearance_rate '
                                    f'{aa.get("appearance_rate")}')
        if aa.get('applied') is True and starter_evidence and pos == 'QB' \
                and 'NOT_PREDICTED_STARTER' not in str(aa.get('reason')) \
                and v.get('role_band') == 'ALPHA' and aa.get('depth_rank') not in (1, None):
            flag(STARTER_PENALISED, f'{nm} ({club} {pos}): ALPHA quarterback charged '
                                    f'{aa.get("reason")}')

        # 4. a player ruled out of the game cannot carry opportunity or points.
        if nm in absent:
            opp = {k: v.get(k) for k in ('pass_attempts', 'carries', 'targets', 'dk_points')
                   if _num(v.get(k)) and v.get(k) > 0}
            if opp:
                flag(INACTIVE_OPPORTUNITY, f'{nm} ({club} {pos}) is absent yet carries {opp}')

        # 5. a role above its declared ceiling needs a recorded reason.
        band, ceil = v.get('role_band'), v.get('askable_ceiling')
        if band in BANDS and ceil in BANDS and BANDS.index(band) > BANDS.index(ceil) \
                and not v.get('cap_reason') and not v.get('role_evidence_conflict'):
            flag(ABOVE_CEILING, f'{nm} ({club} {pos}): band {band} above ceiling {ceil}, '
                                f'no cap_reason or recorded conflict')

        # 5b. a quarterback carrying receiver volume is a share above a football ceiling.
        if pos == 'QB' and _num(v.get('targets')) and v['targets'] > QB_TARGETS_CEILING_PER_GAME \
                and not ((v.get('allocation') or {}).get('targets') or {}).get('explicit_reason'):
            flag(QB_RECEIVER_VOLUME, f'{nm} ({club} QB): {v["targets"]:.2f} projected targets '
                                     f'above the {QB_TARGETS_CEILING_PER_GAME} ceiling, no reason')

        # 6. a zero is a number only when its state says so; a missing input is not a zero.
        if projected and v.get('dk_points') == 0.0:
            flag(ZERO_UNNAMED, f'{nm} ({club} {pos}): dk_points exactly 0.0 under '
                               f'state {v.get("projection_state")}')
        if projected and pos in SKILL:
            need = {'QB': ('pass_attempts',), 'RB': ('carries',),
                    'WR': ('targets',), 'TE': ('targets',)}[pos]
            for k in need:
                if v.get(k) is None:
                    flag(MISSING_AS_ZERO, f'{nm} ({club} {pos}): {k} is None on a projected row')

    # 3. club totals reconcile with the players they were allocated to.
    for club in clubs:
        t = tv.get(club) or {}
        here = [v for v in rows.values() if v.get('team') == club]
        for code, field, total_key, positions in (
                # ONE POOL PER FIELD, as the allocator builds it: a receiver's measured trick-play
                # attempt is part of the club's pass attempts. Summing quarterbacks only flagged
                # eight clubs on the week-3 slate for residuals of 0.03-0.33 that were sitting on
                # receivers' rows -- a gate reading a different identity from the one allocated.
                (PASS_ATT_UNRECONCILED, 'pass_attempts', 'proj_pass_attempts', SKILL),
                (CARRIES_UNRECONCILED, 'carries', 'proj_rush_attempts', SKILL),
                (TARGETS_UNRECONCILED, 'targets', 'proj_targets', SKILL)):
            total = t.get(total_key)
            if not _num(total):
                continue
            got = sum(v.get(field) or 0.0 for v in here if v.get('position') in positions)
            if abs(got - total) > RECONCILE_TOL * max(abs(total), 1.0):
                flag(code, f'{club}: players sum to {got:.4f}, club total {total:.4f}, '
                           f'residual {got - total:+.4f} exceeds {RECONCILE_TOL:.1%}')
        non_qb = sum(v.get('pass_attempts') or 0.0 for v in here
                     if v.get('position') in SKILL and v.get('position') != 'QB')
        if non_qb > NON_QB_PASS_ATT_CEILING_PER_GAME:
            flag(NON_QB_PASS_ATTEMPTS, f'{club}: {non_qb:.3f} pass attempts sit on non-quarterbacks, '
                                       f'above the {NON_QB_PASS_ATT_CEILING_PER_GAME} ceiling')

    # 7. every club carries each unit this artifact is declared to project. A showdown artifact
    # carries kicker and defence; the main-slate projection carries the defence and leaves kickers
    # to the kicking layer, which the output contract checks as its own sheet. The caller declares
    # which, and the declaration is recorded, so a narrower check is visible rather than silent.
    for club in clubs:
        for pos in units:
            ok = [v for v in rows.values() if v.get('team') == club and v.get('position') == pos
                  and _num(v.get('dk_points')) and v['dk_points'] > 0]
            if not ok:
                flag(UNIT_MISSING, f'{club}: no projected {pos}')

    n = sum(len(x) for x in problems.values())
    if problems:
        return Outcome.fail(
            FAIL_CODE, f'{n} contradiction(s) in {len(problems)} class(es): '
                       f'{sorted(problems)}',
            cause=Cause.DATA, spec_version=SPEC_VERSION, problems=problems, n_rows=len(rows), units_required=list(units),
            clubs=clubs, n_absent=len(absent))
    return Outcome.ok(PASS_CODE, {'checked': len(rows), 'clubs': clubs},
                      f'{len(rows)} rows, {len(clubs)} clubs, no football contradiction',
                      spec_version=SPEC_VERSION, n_rows=len(rows), units_required=list(units), clubs=clubs,
                      n_absent=len(absent), reconcile_tol=RECONCILE_TOL)

# ----------------------------------------------------------- draws-level consistency (MEASURED)
#
# The gate above validates the PROJECTION against its own club totals. The optimizer does not
# consume the projection; it consumes the DRAWS. Retaining per-world stat lines showed the joint
# simulator draws its own club volume from its market-response model, not the projection's
# team_volume: on 2026 W4, PIT carries +9.8% and targets +11.7% above the projection's club totals,
# CLE pass attempts +7.1%. So the numbers the optimizer ranks on do not reconcile to the numbers
# the gate just passed. Which club volume is authoritative is a design decision (escalated); until
# it is ruled, this is MEASURED AND REPORTED on every run, never silently absent -- and never a
# refusal that would block the pipeline on a question nobody has answered yet.
DRAWS_SIDECAR_ABSENT = 'DRAWS_SIDECAR_ABSENT'
DRAWS_MEASURED = 'DRAWS_CLUB_VOLUME_MEASURED'
#: Owner ruling 2026-10-02, requirement 7: once the simulator is centred on the projection, a
#: material divergence is a REFUSAL, not a measurement. Armed only when the draws artifact
#: declares the centred arm; the incumbent arm is still measured and reported.
DRAWS_NOT_RECONCILED = 'DRAWS_NOT_RECONCILED_TO_PROJECTION'
DRAWS_DOC_NOT_SUPPLIED = 'DRAWS_DOC_NOT_SUPPLIED_TO_GATE'
DRAWS_FIELDS = {'pass_attempts': ('pass_att', 'proj_pass_attempts'),
                'carries': ('carries', 'proj_rush_attempts'),
                'targets': ('targets', 'proj_targets')}


def measure_draws(artifact: dict, draws_doc: dict, repo_root=None) -> dict:
    """Mean simulated club volume per club vs the projection's team_volume, from the sidecar.

    Returns a plain evidence dict with a `state` of DRAWS_SIDECAR_ABSENT or
    DRAWS_CLUB_VOLUME_MEASURED. Absence is named, not read as agreement.
    """
    import numpy as np
    if (draws_doc or {}).get('DRAWS_DOC_NOT_SUPPLIED'):
        return {'state': DRAWS_DOC_NOT_SUPPLIED, 'WHY': draws_doc['DRAWS_DOC_NOT_SUPPLIED']}
    sc = (draws_doc or {}).get('stat_draws_sidecar') or {}
    root = pathlib.Path(repo_root or _REPO)
    path = root / sc['path'] if sc.get('path') else None
    if not path or not path.exists():
        return {'state': DRAWS_SIDECAR_ABSENT,
                'WHY': 'the draws artifact names no per-stat sidecar (or it is missing), so the '
                       'simulated club volume cannot be compared with the projection. Absent, '
                       'not agreeing.'}
    fields = list(sc.get('STAT_FIELDS') or ())
    idx = {f: fields.index(f) for f, _ in DRAWS_FIELDS.values() if f in fields}
    z = np.load(path)
    tv = (artifact or {}).get('team_volume') or {}
    rows = (artifact or {}).get('rows') or {}
    club_of = {f"{v.get('name')}|{v.get('team')}": v.get('team') for v in rows.values()}
    out = {}
    for key in z.files:
        club = club_of.get(key) or key.rsplit('|', 1)[-1]
        a = z[key]
        d = out.setdefault(club, {k: 0.0 for k in DRAWS_FIELDS})
        for name, (f, _) in DRAWS_FIELDS.items():
            if f in idx:
                d[name] += float(a[:, idx[f]].mean())
    per_club = {}
    for club, sim in out.items():
        t = tv.get(club) or {}
        per_club[club] = {}
        for name, (_, tkey) in DRAWS_FIELDS.items():
            proj = t.get(tkey)
            per_club[club][name] = {
                'simulated_mean': round(sim[name], 3),
                'projection_club_total': (round(proj, 3) if _num(proj) else None),
                'ratio_minus_one': (round(sim[name] / proj - 1.0, 4)
                                    if _num(proj) and proj else None)}
    worst = max((abs(v['ratio_minus_one']) for c in per_club.values() for v in c.values()
                 if v['ratio_minus_one'] is not None), default=None)
    vc = (draws_doc or {}).get('volume_centre') or {}
    if vc.get('mode') == 'PROJECTION':
        # The arm declared a centre; the solver's own reconciliation is re-read, and the means
        # recomputed here from the sidecar must also sit within the solver's declared tolerance.
        recon = vc.get('reconciliation') or {}
        bad = {}
        for club, fields in recon.items():
            for name, v in fields.items():
                here = (per_club.get(club) or {}).get(name) or {}
                sim_here = here.get('simulated_mean')
                if v.get('within_tol') is False or (
                        sim_here is not None and v.get('target') is not None
                        and abs(sim_here - v['target']) > (v.get('tolerance') or 0) + 1e-9):
                    bad.setdefault(club, []).append(name)
        if bad or not vc.get('all_within_tol', False):
            return {'state': DRAWS_NOT_RECONCILED, 'per_club': per_club,
                    'declared_tolerance_rule': vc.get('tolerance_rule'),
                    'outside_tolerance': bad or 'solver reported all_within_tol False',
                    'WHY': ('the draws artifact declares the projection-centred arm, so a '
                            'simulated club mean outside the declared Monte Carlo tolerance of the '
                            'projection centre is a contradiction between the number the gate '
                            'validated and the number the optimizer ranks on. Refused.')}
    return {'state': DRAWS_MEASURED, 'per_club': per_club, 'worst_abs_ratio_minus_one': worst,
            'volume_centre_mode': vc.get('mode') or 'SIMULATOR_OWN_REGRESSION',
            'sidecar': sc.get('path'),
            'n_draws_per_player': int(z[z.files[0]].shape[0]) if z.files else None,
            'MEANING': ('the optimizer consumes draws, the gate validated the projection; a non-zero '
                        'ratio means the two carry different club volumes. Reported for the '
                        'authoritative-volume decision; not a refusal.')}
