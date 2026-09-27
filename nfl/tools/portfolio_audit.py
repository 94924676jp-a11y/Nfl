#!/usr/bin/env python3.12
"""Audit the owner's 48 FC-based placeholder lineups against the POST_INACTIVES state.

READ-ONLY. The 48 lineups are not modified, not re-optimised and not uploaded. This
module reports what they contain, whether they are legal, and where their implied
football story disagrees with our observed role evidence.

WHAT "DISAGREES" MEANS HERE, PRECISELY. We have no Week-3 projection, so nothing below
is a projection disagreement. Every comparison is `ROLE_EVIDENCE_DIAGNOSTIC`: a
statement that FantasyCruncher's number sits high or low relative to what a player
measurably DID in weeks 1-2 plus what today's absences vacated. That can mean FC is
wrong, or that FC knows something about role that two games of usage does not show. The
diagnostic names the tension; it does not settle it.

THE ONE NUMBER NOBODY SHOULD READ FROM THE FC EXPORT. It carries `My` and `My Proj`
columns and a `Diff`. In all 273 rows `My` equals `FC` exactly and `Diff` is 0.0, so
`My Proj` is FantasyCruncher echoed, not a proprietary number.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import itertools
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import fc_context as FC  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

SPEC_VERSION = 'portfolio-audit-2026w3-1'

PLACEHOLDERS = (_REPO / 'nfl/dfs/salaries/raw/OWNER_PLACEHOLDERS_FC_48_2026W3.csv')
OWNER_AUDIT = (_REPO / 'nfl/dfs/salaries/raw'
               / 'OWNER_PLACEHOLDERS_FC_48_AUDIT_2026W3.csv')
POST = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
OUT = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PLACEHOLDER_PORTFOLIO_AUDIT.json'

SALARY_CAP = 50_000
SLOTS = ('QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX', 'DST')
FLEX_OK = ('RB', 'WR', 'TE')
ID_RE = re.compile(r'\((\d+)\)\s*$')

EXPECTED_CONTESTS = {
    '195955835': 2, '196110787': 20, '196117165': 6, '196122720': 20,
}

READ_ONLY = ('this audit does not modify, re-optimise, re-assign or upload the 48 '
             'lineups. They are the owner placeholders and they stay exactly as given.')


def _digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def parse_placeholders():
    rows = list(csv.reader(PLACEHOLDERS.open(newline='', encoding='utf-8-sig')))
    hdr = [c.strip() for c in rows[0]]
    need = ('Entry ID', 'Contest Name', 'Contest ID', 'Entry Fee')
    if any(c not in hdr for c in need):
        return Outcome.fail('PLACEHOLDER_SCHEMA', f'header is {hdr}')
    slot_idx = [i for i, c in enumerate(hdr) if c in ('QB', 'RB', 'WR', 'TE', 'FLEX',
                                                      'DST')]
    if len(slot_idx) != 9:
        return Outcome.fail('PLACEHOLDER_SCHEMA',
                            f'{len(slot_idx)} roster columns, expected 9')
    ei, cn, ci, ef = (hdr.index(c) for c in need)
    out = []
    for r in rows[1:]:
        if len(r) <= ei or not r[ei].strip():
            continue
        cells = []
        for n, i in enumerate(slot_idx):
            raw = (r[i] if len(r) > i else '').strip()
            m = ID_RE.search(raw)
            cells.append({'slot': hdr[i], 'slot_ordinal': n, 'raw': raw,
                          'dk_id': m.group(1) if m else None,
                          'name_in_file': ID_RE.sub('', raw).strip() or None})
        out.append({'entry_id': r[ei].strip(), 'contest_name': r[cn].strip(),
                    'contest_id': r[ci].strip(), 'entry_fee': r[ef].strip(),
                    'cells': cells})
    if len(out) != 48:
        return Outcome.fail('PLACEHOLDER_COUNT',
                            f'{len(out)} entry rows, expected 48')
    return Outcome.ok('PLACEHOLDERS_PARSED', out, f'{len(out)} lineups',
                      n=len(out), sha256=_digest(PLACEHOLDERS))


def owner_audit_rows():
    if not OWNER_AUDIT.exists():
        return {}
    rows = list(csv.DictReader(OWNER_AUDIT.open(newline='', encoding='utf-8-sig')))
    return {r['Entry ID'].strip(): r for r in rows if (r.get('Entry ID') or '').strip()}


def _obs(v, key):
    o = ((v.get('observed_2026') or {}).get('combined') or {})
    x = o.get(key)
    return x if isinstance(x, (int, float)) else None


def legality(lineups, players):
    """DraftKings legality plus availability legality. Separate failure classes."""
    fails, per = [], {}
    for lu in lineups:
        eid = lu['entry_id']
        issues = []
        ids = [c['dk_id'] for c in lu['cells']]
        if any(i is None for i in ids):
            issues.append({'code': 'BLANK_OR_UNPARSEABLE_SLOT',
                           'detail': [c['raw'] for c in lu['cells']
                                      if c['dk_id'] is None]})
        known = [i for i in ids if i in players]
        unknown = [i for i in ids if i is not None and i not in players]
        if unknown:
            issues.append({'code': 'DK_ID_NOT_IN_EARLY_ONLY_457', 'detail': unknown})
        dupes = [i for i, n in collections.Counter(known).items() if n > 1]
        if dupes:
            issues.append({'code': 'PLAYER_DUPLICATED_IN_LINEUP',
                           'detail': [players[i]['name'] for i in dupes]})
        salary = sum(players[i]['salary'] for i in known)
        if salary > SALARY_CAP:
            issues.append({'code': 'SALARY_OVER_CAP',
                           'detail': f'{salary} > {SALARY_CAP}'})
        # slot eligibility
        for c in lu['cells']:
            i = c['dk_id']
            if i not in players:
                continue
            pos = players[i]['position']
            want = c['slot']
            ok = (pos == want) if want != 'FLEX' else (pos in FLEX_OK)
            if not ok:
                issues.append({'code': 'SLOT_POSITION_ILLEGAL',
                               'detail': f'{players[i]["name"]} ({pos}) in {want}'})
        # name/ID agreement
        for c in lu['cells']:
            i = c['dk_id']
            if i in players and c['name_in_file']:
                a = c['name_in_file'].replace('  ', ' ').strip()
                b = players[i]['name']
                if a != b and a.rstrip('.') != b.rstrip('.'):
                    issues.append({'code': 'NAME_AND_ID_DISAGREE',
                                   'detail': f'file says {a!r}, DK says {b!r}'})
        # availability legality -- the one that matters most today
        inactive = [players[i]['name'] for i in known
                    if players[i]['current_availability']['status']
                    in AV.ABSENT_STATUSES]
        if inactive:
            issues.append({'code': 'REPORTED_INACTIVE_PLAYER_IN_LINEUP',
                           'detail': inactive})
        unresolved = [players[i]['name'] for i in known
                      if players[i]['current_availability']['status']
                      == AV.UNKNOWN_NOT_RELAYED]
        per[eid] = {
            'salary': salary,
            'salary_headroom': SALARY_CAP - salary,
            'issues': issues,
            'legal_dk': not [x for x in issues if x['code'] != 'NAME_AND_ID_DISAGREE'],
            'n_unresolved_availability': len(unresolved),
            'unresolved_availability': unresolved,
            'AVAILABILITY_UNCERTAINTY_IS_NOT_ILLEGALITY': (
                'a player whose availability is UNKNOWN_NOT_RELAYED is not an illegal '
                'roster entry. He is a roster entry we cannot certify. The complete '
                'inactive lists would settle it; see OUT-035.'),
        }
        if issues:
            fails.append({'entry_id': eid, 'issues': issues})
    return per, fails


def _stack(lu, players):
    """QB stack, bring-back and same-game structure derived from OUR state."""
    ids = [c['dk_id'] for c in lu['cells'] if c['dk_id'] in players]
    rows = [players[i] for i in ids]
    qb = next((r for r in rows if r['position'] == 'QB'), None)
    if qb is None:
        return {'qb': None, 'error': 'NO_QB_IN_LINEUP'}
    club, opp = qb['team'], qb['opponent']
    catchers = [r['name'] for r in rows
                if r['team'] == club and r['position'] in ('WR', 'TE')]
    own_rb = [r['name'] for r in rows if r['team'] == club and r['position'] == 'RB']
    bring = [f'{r["name"]} ({r["position"]})' for r in rows
             if r['team'] == opp and r['position'] != 'DST']
    dsts = [r for r in rows if r['position'] == 'DST']
    dst = dsts[0]['team'] if dsts else None
    games = collections.Counter()
    for r in rows:
        a, b = sorted((r['team'], r['opponent']))
        games[f'{a}/{b}'] += 1
    return {
        'qb': qb['name'], 'qb_club': club, 'qb_opponent': opp,
        'stack_pass_catchers': catchers, 'stack_size': len(catchers),
        'stack_type': ('NO_PASS_CATCHER' if not catchers else
                       'SINGLE' if len(catchers) == 1 else
                       f'MULTI_{len(catchers)}'),
        'same_team_rb': own_rb,
        'bring_back': bring or None,
        'bring_back_present': bool(bring),
        'dst': dst,
        'dst_opposes_own_qb': (dst == opp) if dst else None,
        'dst_same_team_as_qb': (dst == club) if dst else None,
        'distinct_games_represented': len(games),
        'players_per_game': dict(games),
    }


def coherence(lu, st, players):
    """Is the lineup's football story coherent? Named concerns, not a score."""
    ids = [c['dk_id'] for c in lu['cells'] if c['dk_id'] in players]
    rows = [players[i] for i in ids]
    c = []
    if st.get('stack_type') == 'NO_PASS_CATCHER':
        c.append({'code': 'QB_WITH_NO_PASS_CATCHER',
                  'detail': f'{st["qb"]} is stacked with nobody he throws to, so the '
                            f'lineup has no mechanism linking his ceiling to a '
                            f'teammate. That is defensible for a rushing quarterback '
                            f'and weak for a pocket passer.'})
    if st.get('dst_opposes_own_qb'):
        c.append({'code': 'OWN_DST_OPPOSES_OWN_QB',
                  'detail': f'the {st["dst"]} defence needs {st["qb"]} to fail while the '
                            f'lineup needs him to succeed. Directly contradictory '
                            f'scoring stories.'})
    if st.get('dst_same_team_as_qb'):
        c.append({'code': 'DST_AND_QB_SAME_TEAM',
                  'detail': f'the {st["dst"]} defence and {st["qb"]} are the same club. '
                            f'Not contradictory, but the defence scores best when the '
                            f'offence is on the field least.'})
    if st.get('distinct_games_represented', 0) >= 7:
        c.append({'code': 'MAXIMALLY_DIFFUSE',
                  'detail': f'{st["distinct_games_represented"]} different games in nine '
                            f'roster slots. Almost no shared football outcome links '
                            f'these players, which is the signature of a lineup built by '
                            f'sorting projections rather than by a scenario.'})
    # a player whose observed role does not support a starting-calibre expectation
    thin = []
    for r in rows:
        if r['position'] == 'DST':
            continue
        snap = _obs(r, 'mean_offense_pct')
        if snap is not None and snap < 0.25 and r['salary'] >= 3000:
            thin.append(f'{r["name"]} ({snap:.0%} observed snaps)')
        if snap is None:
            thin.append(f'{r["name"]} (no observed 2026 row)')
    if thin:
        c.append({'code': 'ROSTERED_ON_THIN_OBSERVED_ROLE', 'detail': thin})
    return c


def exposure(lineups, players):
    pl = collections.Counter()
    qb = collections.Counter()
    dst = collections.Counter()
    team = collections.Counter()
    game = collections.Counter()
    pairs = collections.Counter()
    trios = collections.Counter()
    stack_pairs = collections.Counter()
    cores = collections.Counter()
    for lu in lineups:
        ids = sorted({c['dk_id'] for c in lu['cells'] if c['dk_id'] in players})
        names = sorted(players[i]['name'] for i in ids)
        for i in ids:
            v = players[i]
            pl[v['name']] += 1
            team[v['team']] += 1
            a, b = sorted((v['team'], v['opponent']))
            if v['position'] == 'QB':
                qb[v['name']] += 1
            if v['position'] == 'DST':
                dst[v['team']] += 1
        for g in {f'{min(players[i]["team"], players[i]["opponent"])}/'
                  f'{max(players[i]["team"], players[i]["opponent"])}' for i in ids}:
            game[g] += 1
        for p in itertools.combinations(names, 2):
            pairs[p] += 1
        for t in itertools.combinations(names, 3):
            trios[t] += 1
        st = _stack(lu, players)
        for pc in st.get('stack_pass_catchers') or ():
            stack_pairs[(st['qb'], pc)] += 1
        cores[tuple(names[:5])] += 1
    # pairwise overlap
    sets = [{c['dk_id'] for c in lu['cells'] if c['dk_id'] in players}
            for lu in lineups]
    ov = []
    for i, j in itertools.combinations(range(len(sets)), 2):
        ov.append((len(sets[i] & sets[j]), lineups[i]['entry_id'],
                   lineups[j]['entry_id']))
    ov.sort(reverse=True)
    dist = collections.Counter(o[0] for o in ov)
    n = len(lineups)
    return {
        'n_lineups': n,
        'player_exposure': {k: {'n': v, 'pct': round(100 * v / n, 1)}
                            for k, v in pl.most_common()},
        'qb_exposure': {k: {'n': v, 'pct': round(100 * v / n, 1)}
                        for k, v in qb.most_common()},
        'dst_exposure': {k: {'n': v, 'pct': round(100 * v / n, 1)}
                         for k, v in dst.most_common()},
        'team_exposure': {k: v for k, v in team.most_common()},
        'game_exposure': {k: {'n': v, 'pct': round(100 * v / n, 1)}
                          for k, v in game.most_common()},
        'qb_stack_pair_exposure': {f'{a} + {b}': v
                                   for (a, b), v in stack_pairs.most_common(20)},
        'top_pairs': [{'pair': list(p), 'n': v, 'pct': round(100 * v / n, 1)}
                      for p, v in pairs.most_common(15)],
        'top_trios': [{'trio': list(t), 'n': v, 'pct': round(100 * v / n, 1)}
                      for t, v in trios.most_common(15)],
        'repeated_5_player_cores': [{'core': list(k), 'n': v}
                                    for k, v in cores.most_common(5) if v > 1],
        'pairwise_overlap_distribution': {str(k): v for k, v in sorted(dist.items())},
        'max_overlap_examples': [{'shared': s, 'a': a, 'b': b} for s, a, b in ov[:8]],
        'mean_pairwise_overlap': round(sum(o[0] for o in ov) / len(ov), 2) if ov else None,
        'EXPOSURE_IS_NOT_A_VERDICT': (
            'a high percentage is not automatically wrong and a low one is not '
            'automatically right. Concentration is defensible when evidence supports it '
            'and accidental when it is a by-product of one optimiser core. Those are '
            'separated below.'),
    }


def concentration_verdicts(exp, players, fc_by_id, post):
    """Separate defensible concentration from accidental concentration."""
    out = []
    by_name = {v['name']: v for v in players.values()}
    for name, e in exp['player_exposure'].items():
        if e['pct'] < 40:
            continue
        v = by_name.get(name)
        if v is None:
            continue
        dk_id = v['dk_id']
        fc = (fc_by_id.get(dk_id) or {}).get(FC.CONTEXT_KEY) or {}
        proj, sal = fc.get('FC Proj'), v['salary']
        val = round(proj / (sal / 1000), 2) if proj and sal else None
        snap = _obs(v, 'mean_offense_pct')
        tgt = _obs(v, 'targets')
        car = _obs(v, 'carries')
        avail = v['current_availability']['status']
        gains = v.get('conditional_opportunity_redistribution') or []
        support = []
        if snap is not None and snap >= 0.6:
            support.append(f'observed {snap:.0%} snap share over weeks 1-2')
        if tgt and tgt >= 12:
            support.append(f'{tgt:.0f} observed targets')
        if car and car >= 18:
            support.append(f'{car:.0f} observed carries')
        if gains:
            support.append(f'gains probability from {len(gains)} of today\'s absences')
        if avail in AV.PRESENT_STATUSES:
            support.append('reported available on a populated inactive list')
        out.append({
            'player': name, 'dk_id': dk_id, 'position': v['position'],
            'team': v['team'], 'salary': sal,
            'exposure_pct': e['pct'], 'exposure_n': e['n'],
            'availability': avail,
            'fc_projection_external_only': proj,
            'fc_points_per_1k_salary': val,
            'observed_snap_share': snap,
            'observed_targets': tgt, 'observed_carries': car,
            'independent_football_support': support,
            'verdict': ('DEFENSIBLE_CONCENTRATION' if len(support) >= 2 else
                        'SALARY_VALUE_ARTEFACT' if val and val >= 4.0 else
                        'ACCIDENTAL_CONCENTRATION'),
            'why': (
                'FC value per $1k is the highest on the slate and the football support '
                'is thin, so the exposure is most simply explained by the optimiser '
                'finding the cheapest point source rather than by a role finding.'
                if val and val >= 4.0 and len(support) < 2 else
                'observed usage and today\'s redistribution independently support a '
                'large role, so the concentration is not merely a price artefact.'
                if len(support) >= 2 else
                'neither strong observed usage nor an unusual price explains it, which '
                'usually means a repeated optimiser core.'),
        })
    return sorted(out, key=lambda r: -r['exposure_pct'])


def role_evidence_diagnostic(players, fc_by_id):
    """Where FC sits high or low against observed role evidence. Not a projection diff."""
    rows = []
    for dk_id, v in players.items():
        if v['position'] == 'DST':
            continue
        fc = (fc_by_id.get(dk_id) or {}).get(FC.CONTEXT_KEY) or {}
        proj = fc.get('FC Proj')
        if proj is None:
            continue
        snap = _obs(v, 'mean_offense_pct')
        tgt = _obs(v, 'targets')
        car = _obs(v, 'carries')
        rz = _obs(v, 'rz_opportunities')
        gains = v.get('conditional_opportunity_redistribution') or []
        avail = v['current_availability']['status']
        flags = []
        if proj >= 9.0 and (snap is None or snap < 0.30):
            flags.append('FC_HIGH_ON_THIN_OBSERVED_ROLE')
        if proj >= 9.0 and snap is None:
            flags.append('FC_HIGH_WITH_NO_OBSERVED_ROW')
        if proj <= 7.0 and snap is not None and snap >= 0.65:
            flags.append('FC_LOW_DESPITE_HEAVY_OBSERVED_SNAPS')
        if proj <= 7.0 and gains:
            flags.append('FC_LOW_DESPITE_POST_INACTIVES_CONCENTRATION')
        if avail in AV.ABSENT_STATUSES:
            flags.append('FC_CARRIES_A_REPORTED_INACTIVE')
        if not flags:
            continue
        rows.append({
            'player': v['name'], 'dk_id': dk_id, 'position': v['position'],
            'team': v['team'], 'opponent': v['opponent'], 'salary': v['salary'],
            'availability': avail,
            'fc_projection_external_only': proj,
            'fc_ceiling_external_only': fc.get('Ceiling'),
            'fc_floor_external_only': fc.get('Floor'),
            'observed_snap_share': snap if snap is not None else 'UNKNOWN_NO_OBSERVED_ROW',
            'observed_targets': tgt if tgt is not None else 'UNKNOWN_NO_OBSERVED_ROW',
            'observed_carries': car if car is not None else 'UNKNOWN_NO_OBSERVED_ROW',
            'observed_rz': rz if rz is not None else 'UNKNOWN_NO_OBSERVED_ROW',
            'gains_from_absences': [g['vacancy'] for g in gains],
            'historical_role_valid': v.get(
                'historical_role_class_valid_for_current_role'),
            'flags': flags,
            'LABEL': 'ROLE_EVIDENCE_DIAGNOSTIC',
            'NOT_A_PROJECTION_DISAGREEMENT': (
                'we hold no Week-3 projection, so this is not our number against FC. It '
                'is FC against what this player measurably did and what today vacated. '
                'FC may be reading a role change that two games of usage cannot show.'),
        })
    return sorted(rows, key=lambda r: -(r['fc_projection_external_only'] or 0))


def run():
    post = json.loads(POST.read_text())
    players = post['players']
    p = parse_placeholders()
    if p.state is not State.PASS:
        return p
    lineups = p.value
    fcr = FC.load()
    if fcr.state is not State.PASS:
        return fcr
    fc_by_id, fc_only, dk_only = FC.join_to_dk(fcr.value, players)

    per, fails = legality(lineups, players)
    owner = owner_audit_rows()
    detail = {}
    for lu in lineups:
        eid = lu['entry_id']
        st = _stack(lu, players)
        oa = owner.get(eid, {})
        ids = [c['dk_id'] for c in lu['cells'] if c['dk_id'] in players]
        fc_sum = sum((fc_by_id.get(i, {}).get(FC.CONTEXT_KEY, {}).get('FC Proj') or 0)
                     for i in ids)
        fc_ceil = sum((fc_by_id.get(i, {}).get(FC.CONTEXT_KEY, {}).get('Ceiling') or 0)
                      for i in ids)
        detail[eid] = {
            'entry_id': eid, 'contest_name': lu['contest_name'],
            'contest_id': lu['contest_id'], 'entry_fee': lu['entry_fee'],
            'roster': [{'slot': c['slot'], 'dk_id': c['dk_id'],
                        'name': players[c['dk_id']]['name']
                        if c['dk_id'] in players else c['name_in_file'],
                        'position': players[c['dk_id']]['position']
                        if c['dk_id'] in players else None,
                        'team': players[c['dk_id']]['team']
                        if c['dk_id'] in players else None,
                        'salary': players[c['dk_id']]['salary']
                        if c['dk_id'] in players else None,
                        'availability': players[c['dk_id']]['current_availability'
                                                            ]['status']
                        if c['dk_id'] in players else None}
                       for c in lu['cells']],
            'salary': per[eid]['salary'],
            'salary_headroom': per[eid]['salary_headroom'],
            'legality': per[eid],
            'structure': st,
            'owner_audit_row': {
                'fc_placeholder_projection': oa.get('FC Placeholder Projection'),
                'qb_stack_as_owner_recorded': oa.get('QB Stack'),
                'bring_back_as_owner_recorded': oa.get('Bring-back'),
                'salary_as_owner_recorded': oa.get('Salary'),
            } if oa else None,
            'fc_sum_recomputed_external_only': round(fc_sum, 2),
            'fc_ceiling_sum_external_only': round(fc_ceil, 2),
            'coherence_concerns': coherence(lu, st, players),
            'n_unresolved_availability': per[eid]['n_unresolved_availability'],
        }

    exp = exposure(lineups, players)
    conc = concentration_verdicts(exp, players, fc_by_id, post)
    diag = role_evidence_diagnostic(players, fc_by_id)

    contest_counts = collections.Counter(lu['contest_id'] for lu in lineups)
    contest_ok = dict(contest_counts) == EXPECTED_CONTESTS

    art = {
        'artifact': 'DK_WEEK3_PLACEHOLDER_PORTFOLIO_AUDIT',
        'spec_version': SPEC_VERSION,
        'READ_ONLY': READ_ONLY,
        'built_against_post_state': {
            'path': str(POST.relative_to(_REPO)), 'sha256': _digest(POST),
            'state_label': post['state_label']},
        'source_files': {
            'placeholders': {'path': str(PLACEHOLDERS.relative_to(_REPO)),
                             'sha256': _digest(PLACEHOLDERS)},
            'owner_audit': {'path': str(OWNER_AUDIT.relative_to(_REPO)),
                            'sha256': _digest(OWNER_AUDIT)},
            'fc_export': {'path': str(FC.SRC.relative_to(_REPO)),
                          'sha256': fcr.evidence['sha256']},
        },
        'FC_STATUS': FC.NOT_A_MODEL_INPUT,
        'MY_PROJ_IS_FC': FC.MY_PROJ_IS_FC,
        'fc_coverage': {
            'fc_rows': len(fcr.value), 'joined_to_dk': len(fc_by_id),
            'fc_only': fc_only,
            'dk_rows_with_no_fc_row': len(dk_only),
            'note': (f'{len(dk_only)} of 457 DK-eligible players have no FC row at all. '
                     f'A missing FC row is not a zero and not an absence; it is FC not '
                     f'covering the player.')},
        'contest_allocation': {
            'counts': dict(contest_counts), 'expected': EXPECTED_CONTESTS,
            'matches': contest_ok},
        'legality_summary': {
            'n_lineups': len(lineups),
            'n_with_any_issue': len(fails),
            'issue_codes': dict(collections.Counter(
                i['code'] for f in fails for i in f['issues'])),
            'n_reported_inactive_in_any_lineup': sum(
                1 for f in fails for i in f['issues']
                if i['code'] == 'REPORTED_INACTIVE_PLAYER_IN_LINEUP'),
            'failures': fails,
        },
        'lineups': detail,
        'exposure': exp,
        'concentration_verdicts': conc,
        'role_evidence_diagnostic': diag,
        'WHAT_IS_STILL_MISSING': post['proprietary_projection_board'],
    }
    OUT.write_text(json.dumps(art, indent=2) + '\n')
    return Outcome.ok('PORTFOLIO_AUDIT_BUILT', art,
                      f'{len(lineups)} lineups, {len(fails)} with issues',
                      n_lineups=len(lineups), n_fails=len(fails))


def main() -> int:
    r = run()
    print(r)
    if r.state is not State.PASS:
        return 1
    v = r.value
    print('\ncontest allocation:', v['contest_allocation'])
    print('legality:', v['legality_summary']['issue_codes'])
    print('\ntop player exposure:')
    for k, e in list(v['exposure']['player_exposure'].items())[:12]:
        print(f'  {k:26s} {e["n"]:3d}  {e["pct"]:5.1f}%')
    print('\nQB exposure:')
    for k, e in v['exposure']['qb_exposure'].items():
        print(f'  {k:26s} {e["n"]:3d}  {e["pct"]:5.1f}%')
    print('\nDST exposure:')
    for k, e in v['exposure']['dst_exposure'].items():
        print(f'  {k:14s} {e["n"]:3d}  {e["pct"]:5.1f}%')
    print(f'\nmean pairwise overlap: {v["exposure"]["mean_pairwise_overlap"]}/9')
    print('overlap distribution:', v['exposure']['pairwise_overlap_distribution'])
    print('\nconcentration verdicts:')
    for c in v['concentration_verdicts']:
        print(f'  {c["player"]:26s} {c["exposure_pct"]:5.1f}%  {c["verdict"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
