#!/usr/bin/env python3.12
"""Semantic PRE -> POST football-state comparator. Not a row differ.

WHY NOT `baseline_diff.py`. That module exists and works, and it is the wrong tool for
this job. It keys on `dk_id` and compares four DraftKings fields -- salary, roster
position, team, display name -- and its one identity check raises `IDENTITY_REGRESSED`
as a FAIL. Point it at a post-inactives comparison and two bad things happen. A roster
churn fires IDENTITY_REGRESSED and reads as a defect in our own chain when nothing is
wrong. And a salary move gets reported in the same list as a player being ruled out, so
"this player changed" stops distinguishing "DraftKings repriced him" from "he is not
playing". The owner's instruction was explicit and it is correct: a generic row differ
must not accidentally imply that a salary or pool change equals a football-role change.

So this compares the things that are actually football:

    availability   a status transition, with the evidence tier on both sides
    role           starter / rotation / depth / package expectation
    opportunity    snaps, carries, targets, red-zone, goal-line, team volume
    redistribution which candidates gained probability from each absence, and where
                   the distribution is still unresolved
    newly relevant depth players who became meaningful
    environment    market and weather, only where it actually moved

and it puts DraftKings salary, pool membership and any external projection value in a
quarantined bucket that is reported for completeness and flagged `football_change:
false` on every row. They are never counted as football changes and never ranked
alongside them.

THREE LOAD-BEARING GUARDS. Each one refuses the whole report rather than annotating it,
because a comparison that reports a violation and still hands back its rows is a
comparison whose violation nobody acts on.

    assert_pre_artifact_unchanged   the PRE state is the before-image. If its bytes
                                    moved, every transition in this report is measured
                                    against something that no longer exists.
    assert_no_row_dropped           457 in, 457 out. A dropped row is a player who
                                    silently stopped existing.
    assert_no_unauthorised_promotion a transition INTO a confirmed status must land on
                                    the tier that status requires. This is the guard
                                    that stops a predicted lineup or a reported status
                                    from being laundered into a confirmation by the act
                                    of comparing two files.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import external_research as EX  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

SPEC_VERSION = 'state-compare-2026w3-1'

PRE = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE.json'
POST = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'

#: DraftKings and third-party fields. Changes here are NEVER football changes.
NON_FOOTBALL_FIELDS = ('salary', 'position', 'team', 'name', 'external_fc_context',
                       'dk_pool_membership')

#: Opportunity measures compared between states.
OPPORTUNITY = ('offense_snaps', 'carries', 'targets', 'rz_opportunities',
               'gl_opportunities', 'mean_offense_pct', 'target_share', 'rush_share')

TRANSITION_CLASSES = {
    ('UNKNOWN', 'INACTIVE'): 'UNRESOLVED_TO_REPORTED_INACTIVE',
    ('UNKNOWN', 'PRESENT'): 'UNRESOLVED_TO_REPORTED_ACTIVE',
    # both sides unresolved: the status STRING moved (UNKNOWN -> UNKNOWN_NOT_RELAYED)
    # and the football did not. Counting these among the transitions put 457 in the
    # headline when 20 players actually changed state, which is the sort of number that
    # gets quoted later without its qualifier.
    ('UNKNOWN', 'UNKNOWN'): 'RELABEL_STILL_UNRESOLVED_NO_FOOTBALL_CHANGE',
    ('INACTIVE', 'PRESENT'): 'ABSENCE_WITHDRAWN',
    ('PRESENT', 'INACTIVE'): 'LATE_ABSENCE',
}
RELABEL = 'RELABEL_STILL_UNRESOLVED_NO_FOOTBALL_CHANGE'


def _bucket(status):
    if status in AV.ABSENT_STATUSES:
        return 'INACTIVE'
    if status in AV.PRESENT_STATUSES:
        return 'PRESENT'
    return 'UNKNOWN'


def _digest(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# --- guards ------------------------------------------------------------------
def assert_pre_artifact_unchanged(post):
    """The POST artifact records the PRE digest it was built from. It must still hold."""
    rec = (post.get('upstream_artifacts') or {}).get('pre_inactives_state') or {}
    claimed = rec.get('sha256')
    if not claimed:
        return Outcome.fail(
            'PRE_DIGEST_NOT_RECORDED',
            'the POST artifact does not record which PRE bytes it was built from, so '
            'no transition in it can be attributed to a before-state')
    actual = _digest(PRE)
    if actual != claimed:
        return Outcome.fail(
            'PRE_ARTIFACT_MUTATED',
            f'the PRE artifact has changed since the POST state was built. Recorded '
            f'{claimed[:16]}, on disk {actual[:16]}. Every transition below was '
            f'measured against a before-image that no longer exists.',
            recorded=claimed, on_disk=actual)
    return Outcome.ok('PRE_ARTIFACT_INTACT', actual,
                      f'PRE bytes match the recorded digest {actual[:16]}')


def assert_no_row_dropped(pre_players, post_players):
    pre_ids, post_ids = set(pre_players), set(post_players)
    lost, gained = sorted(pre_ids - post_ids), sorted(post_ids - pre_ids)
    if lost:
        return Outcome.fail(
            'DK_ROWS_DROPPED',
            f'{len(lost)} DK rows present in PRE are absent from POST. A player who '
            f'stops appearing has not been ruled out, he has been lost.',
            lost=lost[:40], n_lost=len(lost), n_gained=len(gained))
    return Outcome.ok('DK_ROWS_PRESERVED', len(post_ids),
                      f'{len(pre_ids)} PRE rows, {len(post_ids)} POST rows, none lost',
                      n_pre=len(pre_ids), n_post=len(post_ids), n_gained=len(gained))


def assert_no_unauthorised_promotion(transitions):
    """A move into a confirmed status must land on the tier that status requires."""
    bad = []
    for t in transitions:
        to = t['to_status']
        need = AV.STATUS_REQUIRES_TIER.get(to)
        if need and t['to_tier'] not in need:
            bad.append({'player': t['player'], 'club': t['club'],
                        'from': t['from_status'], 'to': to, 'to_tier': t['to_tier'],
                        'required_tier_in': list(need)})
    if bad:
        return Outcome.fail(
            'PREDICTED_PROMOTED_TO_CONFIRMED',
            f'{len(bad)} transition(s) land on a confirmed status without the evidence '
            f'tier that status requires. Comparing two files is not a source of '
            f'authority and must not become one.',
            violations=bad[:40], n_violations=len(bad))
    return Outcome.ok('NO_UNAUTHORISED_PROMOTION', len(transitions),
                      f'{len(transitions)} transitions, none promoted beyond its tier',
                      n_transitions=len(transitions))


# --- the comparison ----------------------------------------------------------
def compare(pre, post):
    pre_p, post_p = pre['players'], post['players']

    g = assert_no_row_dropped(pre_p, post_p)
    if g.state is not State.PASS:
        return g
    g2 = assert_pre_artifact_unchanged(post)
    if g2.state is not State.PASS:
        return g2

    availability, roles, opportunity, non_football = [], [], [], []
    for dk_id, post_row in post_p.items():
        pre_row = pre_p.get(dk_id)
        if pre_row is None:
            continue
        pre_av = pre_row.get('current_availability')
        pre_status = pre_av if isinstance(pre_av, str) else (pre_av or {}).get('status')
        pre_tier = (pre_av or {}).get('evidence_tier') if isinstance(pre_av, dict) \
            else AV.TIER_NONE
        post_av = post_row.get('current_availability') or {}
        post_status, post_tier = post_av.get('status'), post_av.get('evidence_tier')

        if pre_status != post_status:
            fb, tb = _bucket(pre_status), _bucket(post_status)
            availability.append({
                'dk_id': dk_id, 'player': post_row['name'], 'club': post_row['team'],
                'position': post_row['position'], 'salary': post_row['salary'],
                'from_status': pre_status, 'from_tier': pre_tier,
                'to_status': post_status, 'to_tier': post_tier,
                'transition_class': TRANSITION_CLASSES.get(
                    (fb, tb), f'{fb}_TO_{tb}'),
                'source': post_av.get('source'),
                'source_quote': post_av.get('source_quote'),
                'document_held': post_av.get('document_held', False),
                'workload_note': post_av.get('workload_note'),
            })

        pre_role = pre_row.get('today_expected_role')
        post_role = post_row.get('today_expected_role')
        if pre_role != post_role:
            roles.append({
                'dk_id': dk_id, 'player': post_row['name'], 'club': post_row['team'],
                'from_role': pre_role, 'to_role': post_role,
                'from_confidence': pre_row.get('role_confidence'),
                'to_confidence': post_row.get('role_confidence'),
                'basis': post_row.get('today_role_evidence'),
            })

        # opportunity: observed weeks 1-2 must NOT move between passes -- it is history
        pre_o = ((pre_row.get('observed_2026') or {}).get('combined') or {})
        post_o = ((post_row.get('observed_2026') or {}).get('combined') or {})
        moved = {k: (pre_o.get(k), post_o.get(k)) for k in OPPORTUNITY
                 if pre_o.get(k) != post_o.get(k)}
        if moved:
            opportunity.append({
                'dk_id': dk_id, 'player': post_row['name'], 'club': post_row['team'],
                'moved': moved,
                'WHY_THIS_IS_A_DEFECT': (
                    'observed weeks 1-2 usage is history. It cannot change between a '
                    'pre-inactives and a post-inactives pass, so a difference here is '
                    'a bug in one of the two builders, not a football change.')})

        for f in NON_FOOTBALL_FIELDS:
            a, b = pre_row.get(f), post_row.get(f)
            if a != b:
                non_football.append({
                    'dk_id': dk_id, 'player': post_row['name'], 'field': f,
                    'from': a, 'to': b, 'football_change': False,
                    'note': ('a DraftKings or third-party field. It is reported for '
                             'completeness and is not a football-role change.')})

    football = [a for a in availability if a['transition_class'] != RELABEL]
    relabels = [a for a in availability if a['transition_class'] == RELABEL]
    promo = assert_no_unauthorised_promotion(availability)
    if promo.state is not State.PASS:
        return promo

    by_class = {}
    for a in availability:
        by_class.setdefault(a['transition_class'], []).append(
            f'{a["club"]} {a["player"]}')

    trees = post.get('redistribution') or {}
    env = _env_changes(pre, post)

    return Outcome.ok('SEMANTIC_COMPARE', {  # noqa: C901
        'spec_version': SPEC_VERSION,
        'pre_sha256': _digest(PRE), 'post_sha256': _digest(POST),
        'guards': {'rows_preserved': g.as_dict(), 'pre_intact': g2.as_dict(),
                   'no_unauthorised_promotion': promo.as_dict()},
        'availability_changes': sorted(football,
                                       key=lambda r: (-r['salary'], r['player'])),
        'availability_changes_by_class': by_class,
        'n_football_availability_changes': len(football),
        'n_status_relabels_no_football_change': len(relabels),
        'AVAILABILITY_COUNT_SEMANTICS': (
            f'{len(football)} players changed availability state. A further '
            f'{len(relabels)} had only their status STRING change, from UNKNOWN to the '
            f'more specific UNKNOWN_NOT_RELAYED, which is a naming improvement and not '
            f'a football event. Quote the first number, never the sum.'),
        'role_changes': roles,
        'opportunity_changes': opportunity,
        'OPPORTUNITY_CHANGES_SHOULD_BE_EMPTY': (
            'observed weeks 1-2 is history and identical in both passes. A non-empty '
            'list here is a builder defect, not football.'),
        'redistribution': {
            'n_trees': len(trees),
            'absences_with_a_tree': sorted(trees),
            'unresolved_inheritance': sorted(
                k for k, t in trees.items()
                if t.get('inheritance') == 'UNRESOLVED_DISTRIBUTION'),
        },
        'newly_relevant_players': post.get('newly_relevant_players') or [],
        'environment_changes': env,
        'NON_FOOTBALL_CHANGES_QUARANTINED': {
            'n': len(non_football), 'rows': non_football[:60],
            'note': ('DraftKings salary, roster position, club label, display name and '
                     'any external projection context. Never counted as football '
                     'change and never ranked beside one.')},
    }, f'{len(football)} football availability changes '
       f'(+{len(relabels)} relabels), {len(roles)} role, {len(trees)} trees',
        n_football=len(football), n_relabels=len(relabels), n_roles=len(roles),
        n_trees=len(trees), n_non_football=len(non_football))


def _env_baseline(pre):
    """The before-image for environment.

    The PRE artifact carries no market or weather block -- it was built before the
    first-pass research was in the tree. But the first pass DOES carry spread, total and
    implied totals for all nine games at 11:32 ET, so the honest baseline is that file
    rather than "nothing held". Reporting nine NO_BASELINE rows would hide a real market
    move on five games.
    """
    env = (pre.get('slate') or {}).get('environment') or pre.get('environment')
    if isinstance(env, dict) and env.get('games'):
        return env['games'], 'PRE_ARTIFACT'
    r = EX.environment()
    if r.state is not State.PASS:
        return {}, f'UNAVAILABLE[{r.code}]'
    out = {}
    for row in r.value:
        key = (row['game'] or '').replace(' ', '')
        key = {'NE@JAC': 'NE@JAX'}.get(key, key)
        # The first pass writes Jacksonville as JAC and the second as JAX, so a raw
        # string compare reported "spread JAC -3 -> JAX -3" as a market move. It is a
        # club-code alias and nothing about the game changed. Normalised here rather
        # than explained in the output, because a report of football changes that
        # contains a non-change trains the reader to skim it.
        out[key] = {'spread': (row['spread'] or '').replace('JAC', 'JAX'),
                    'total': float(row['total']),
                    'away_implied': float(row['away_implied']),
                    'home_implied': float(row['home_implied'])}
    return out, 'FIRST_PASS_RESEARCH_11_32_ET'


def _env_changes(pre, post):
    base, basis = _env_baseline(pre)
    b = post.get('environment') or {}
    out = []
    for game, bb in (b.get('games') or {}).items():
        aa = base.get(game)
        if aa is None:
            out.append({'game': game, 'change': 'NO_BASELINE_HELD', 'post': bb,
                        'baseline_basis': basis})
            continue
        moved = {k: {'from': aa.get(k), 'to': bb.get(k)} for k in bb
                 if k in aa and aa.get(k) != bb.get(k)}
        firsts = {k: bb[k] for k in bb if k not in aa}
        out.append({
            'game': game,
            'change': 'MOVED' if moved else 'UNCHANGED',
            'baseline_basis': basis,
            'moved': moved,
            'first_observation_no_baseline': firsts or None,
            'MARKET_IS_NOT_OUR_NUMBER': (
                'the market moved. That is information about the market, not a '
                'correction to any projection of ours, and there is no projection here '
                'for it to correct.') if moved else None,
        })
    return out


def run():
    if not POST.exists():
        return Outcome.fail('POST_STATE_ABSENT',
                            f'{POST.name} has not been built yet')
    return compare(json.loads(PRE.read_text()), json.loads(POST.read_text()))


def main() -> int:
    r = run()
    print(r)
    if r.state is not State.PASS:
        return 1
    v = r.value
    print('\n--- availability transitions by class ---')
    for cls, who in sorted(v['availability_changes_by_class'].items()):
        print(f'  {cls:38s} {len(who):3d}')
    print('\n--- the transitions that matter ---')
    for a in v['availability_changes']:
        if a['transition_class'] != 'STILL_UNRESOLVED':
            print(f'  {a["club"]:4s} {a["player"]:24s} ${a["salary"]:5d} '
                  f'{a["from_status"]} -> {a["to_status"]}  [{a["to_tier"]}]')
    print(f'\n{v["AVAILABILITY_COUNT_SEMANTICS"]}')
    print(f'\nrole changes {len(v["role_changes"])} | '
          f'opportunity drift {len(v["opportunity_changes"])} (must be 0) | '
          f'trees {v["redistribution"]["n_trees"]} | '
          f'non-football quarantined {v["NON_FOOTBALL_CHANGES_QUARANTINED"]["n"]}')
    print('\n--- environment ---')
    for e in v['environment_changes']:
        bits = ', '.join(f'{k} {m["from"]}->{m["to"]}'
                         for k, m in (e.get('moved') or {}).items())
        print(f'  {e["game"]:10s} {e["change"]:9s} {bits}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
