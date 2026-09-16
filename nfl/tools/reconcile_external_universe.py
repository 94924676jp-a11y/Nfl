"""Reconcile an external contest player list against our own participant set.

WHAT THIS IS FOR AND WHAT IT IS NOT. A DFS operator's upload template is an
independently compiled list of who is expected to be available for a game. It
is useful for exactly one thing: catching a player WE omitted by accident --
a WR5, a second tight end, a third running back that never entered our
universe because a depth chart or a roster slice was thin.

IT IS NOT AN ELIGIBILITY AUTHORITY AND IT IS NOT A PREDICTIVE INPUT. Salary
and FPPG are read from the file and DISCARDED here, deliberately and in code,
so that no later reader can pick them up from an artifact this tool wrote.
The operator's own injury indicator is carried as INFORMATION, attributed to
the file, and never as an official declaration -- our roster and injury
evidence continue to govern.

AND BEING ON THE LIST IS NOT OPPORTUNITY. A contest lists a player so he can
be rostered; it says nothing about whether he will take a snap. Every row
here therefore carries TWO separate columns -- whether we know who he is, and
whether he is in the opportunity pool -- because collapsing them is the exact
"a data label is football reality" error this project keeps paying for.
"""
from __future__ import annotations

import argparse
import csv
import glob
import gzip
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import participant_class as PC        # noqa: E402

SPEC_VERSION = 'external-universe-reconciliation-1'

#: READ AND THROWN AWAY. Named so the discard is visible rather than implied.
DISCARDED_COLUMNS = ('FPPG', 'Salary', 'MVP 1.5x Salary', 'Tier')

#: FanDuel writes a defence/special-teams unit as a team abbreviation at
#: position D. We model no defensive unit at all, so these are accounted for
#: and excluded by a reason that is about our scope, not about the player.
TEAM_UNIT_POSITIONS = ('D', 'DST', 'DEF')


def _norm(s):
    """Fold a display name for matching only. Never stored as identity.

    SUFFIXES ARE STRIPPED AS WHOLE TRAILING TOKENS, LONGEST FIRST. The first
    version used ordered substring replacement with `' ii'` before `' iii'`,
    so "James Cook III" folded to "james cooki" and the reconciliation
    reported the Buffalo starting running back as MISSING INTERNALLY. A
    substring replace on a name is how a suffix eats a letter.
    """
    s = (s or '').strip().lower()
    for a, b in (('.', ''), ("'", ''), ('-', ' ')):
        s = s.replace(a, b)
    parts = s.split()
    while parts and parts[-1] in ('jr', 'sr', 'i', 'ii', 'iii', 'iv', 'v'):
        parts.pop()
    return ' '.join(parts)


def _last_key(name, team, position):
    """A (surname, club, position) key, for a FORMAL-vs-FAMILIAR first name.

    "Joshua Palmer" and "Josh Palmer" are one player, and no amount of
    folding the full string makes them equal. Falling back on the surname
    alone would be reckless -- two Allens quarterback in this very game -- so
    the club and the position have to agree too, and a key that matches more
    than one internal player is REFUSED rather than resolved.
    """
    n = _norm(name).split()
    if not n:
        return None
    return (n[-1], (team or '').upper(), (position or '').upper())


def read_external(path):
    """The operator's rows, with the predictive columns dropped."""
    rows = list(csv.reader(open(path)))
    hdr_i = next((i for i, r in enumerate(rows)
                  if 'Player ID + Player Name' in r), None)
    if hdr_i is None:
        raise SystemExit('EXTERNAL_FILE_HAS_NO_PLAYER_HEADER: the file '
                         'carries no "Player ID + Player Name" column, so it '
                         'is not the upload template this tool reads.')
    off = rows[hdr_i].index('Player ID + Player Name')
    cols = rows[hdr_i][off:]
    out = []
    for r in rows[hdr_i + 1:]:
        if len(r) <= off or not r[off]:
            continue
        d = dict(zip(cols, r[off:]))
        for k in DISCARDED_COLUMNS:
            d.pop(k, None)
        out.append({
            'external_id': d.get('Id', ''),
            'name': (d.get('Nickname') or
                     f"{d.get('First Name','')} {d.get('Last Name','')}"
                     ).strip(),
            'position': (d.get('Position') or '').strip().upper(),
            'team': (d.get('Team') or '').strip().upper(),
            'opponent': (d.get('Opponent') or '').strip().upper(),
            'injury_indicator': (d.get('Injury Indicator') or '').strip(),
            'injury_details': (d.get('Injury Details') or '').strip(),
        })
    return out


def roster_rows(season, week, teams):
    """Every position-player roster row for these clubs at or before `week`."""
    by_week = {}
    for f in sorted(glob.glob(str(
            _REPO / 'nfl/vintage/weekly_rosters.*raw.csv*'))):
        op = gzip.open if f.endswith('.gz') else open
        for r in csv.DictReader(op(f, 'rt')):
            if (r.get('team') or '').strip().upper() not in teams:
                continue
            try:
                if int(r.get('season') or 0) != int(season):
                    continue
                w = int(r.get('week') or 0)
            except ValueError:
                continue
            if w <= int(week):
                by_week.setdefault(w, []).append(r)
    if not by_week:
        return [], None
    src = max(by_week)
    return by_week[src], src


def internal_universe(run_dir):
    """Who the sealed run actually modelled, and in which layers."""
    man = json.load(open(pathlib.Path(run_dir) / 'player_draws_manifest.json'))
    art = json.load(open(pathlib.Path(run_dir) / 'forecast_artifact.json'))
    board = json.load(open(pathlib.Path(run_dir) / 'board.json'))
    layers = man.get('layers') or {}
    in_layer = {}
    for lay, spec in layers.items():
        if spec.get('row_axis') != 'gsis_id':
            continue
        teams = spec.get('row_teams') or [None] * len(spec['row_ids'])
        for g, t in zip(spec['row_ids'], teams):
            e = in_layer.setdefault(g, {'layers': [], 'team': t})
            e['layers'].append(lay)
            if t and not e['team']:
                e['team'] = t
    names = {}
    for g, v in ((art.get('gadget_rush') or {}).get('rows') or {}).items():
        names[g] = {'name': v.get('name'), 'position': v.get('position'),
                    'team': v.get('team')}
    for g, v in ((art.get('kicking') or {}).get('resolved') or {}).items():
        names[g] = {'name': v.get('name'), 'position': 'K',
                    'team': v.get('team')}
    display = set()
    for p in board.get('players') or []:
        display.add(p['gsis_id'])
        names[p['gsis_id']] = {'name': p.get('name'),
                               'position': p.get('position'),
                               'team': p.get('team')}
    return {'in_layer': in_layer, 'names': names, 'display': display,
            'declared_player_ids': set(art.get('player_ids') or []),
            'run_id': man.get('run_id')}


def reconcile(external, uni, roster, season, week):
    """One row per external player, plus every internal row they miss."""
    cls = {}
    ros_by_norm, ros_by_gsis = {}, {}
    for r in roster:
        g = (r.get('gsis_id') or '').strip()
        nm = _norm(r.get('full_name'))
        c = PC.from_roster_status((r.get('status') or '').strip().upper())
        rec = {'gsis_id': g, 'name': (r.get('full_name') or '').strip(),
               'team': (r.get('team') or '').strip().upper(),
               'position': (r.get('position') or '').strip().upper(),
               'status': (r.get('status') or '').strip().upper(),
               'participant_class': c}
        if g:
            ros_by_gsis[g] = rec
            cls[g] = c
        if nm:
            ros_by_norm.setdefault(nm, rec)

    int_by_norm = {}
    for g, v in uni['names'].items():
        nm = _norm(v.get('name'))
        if nm:
            int_by_norm.setdefault(nm, g)
    # THE SURNAME FALLBACK, built to REFUSE an ambiguous key rather than pick.
    last_int, last_ros = {}, {}
    for g, v in uni['names'].items():
        k = _last_key(v.get('name'), v.get('team'), v.get('position'))
        if k:
            last_int.setdefault(k, set()).add(g)
    for r in roster:
        k = _last_key(r.get('full_name'), r.get('team'), r.get('position'))
        g = (r.get('gsis_id') or '').strip()
        if k and g:
            last_ros.setdefault(k, set()).add(g)

    rows, flags = [], []
    matched = set()
    ambiguous = []
    for e in external:
        nm = _norm(e['name'])
        g = int_by_norm.get(nm)
        ros = ros_by_norm.get(nm) or (ros_by_gsis.get(g) if g else None)
        if g is None and ros:
            g = ros['gsis_id'] or None
        match_basis = 'FULL_NAME' if g else None
        if g is None:
            k = _last_key(e['name'], e['team'], e['position'])
            cand = (last_int.get(k) or set()) | (last_ros.get(k) or set())
            if len(cand) == 1:
                g = next(iter(cand))
                ros = ros_by_gsis.get(g) or ros
                match_basis = 'SURNAME_CLUB_POSITION'
            elif len(cand) > 1:
                ambiguous.append((e['name'], sorted(cand)))
                match_basis = 'AMBIGUOUS_REFUSED'
        if g:
            matched.add(g)
        lay = (uni['in_layer'].get(g) or {}) if g else {}
        rc = cls.get(g) if g else None
        if e['position'] in TEAM_UNIT_POSITIONS:
            state, elig, reason = ('TEAM_UNIT', 'NOT_MODELLED',
                                   'a defence/special-teams unit is not a '
                                   'player and this engine models no '
                                   'defensive scoring at all')
            role = 'OUT_OF_SCOPE'
        elif not g:
            state, elig, reason = ('NOT_FOUND_INTERNALLY', 'ABSENT',
                                   'no internal identity resolves this name '
                                   'in the roster capture or the sealed run')
            role = 'UNKNOWN'
        else:
            state = rc or 'UNKNOWN'
            if lay.get('layers'):
                elig = 'IN_OPPORTUNITY_POOL'
                reason = ''
            elif PC.eligibility_state(rc) == 'ELIGIBLE':
                elig = 'ELIGIBLE_BUT_NOT_MODELLED'
                reason = ('on the game roster and carries no modelled '
                          'opportunity on this board -- an omission, not an '
                          'exclusion')
            else:
                elig = 'EXCLUDED'
                reason = (f'participation class {rc}; '
                          f'{PC.eligibility_state(rc)}')
            role = ('DISPLAYED' if g in uni['display']
                    else 'SECONDARY_UNIVERSE' if lay.get('layers')
                    else 'NOT_IN_UNIVERSE')
        row = {
            'external_name': e['name'], 'external_id': e['external_id'],
            'external_team': e['team'], 'external_position': e['position'],
            'internal_identity': g or None,
            'identity_match_basis': match_basis,
            'internal_name': (uni['names'].get(g, {}).get('name')
                              if g else None) or (ros or {}).get('name'),
            'internal_team': (lay.get('team')
                              or (ros or {}).get('team')),
            'internal_position': (uni['names'].get(g, {}).get('position')
                                  if g else None) or (ros or {}).get('position'),
            'internal_roster_state': state,
            'simulation_eligibility': elig,
            'expected_role_state': role,
            'layers': lay.get('layers') or [],
            'external_injury_indicator': e['injury_indicator'] or None,
            'external_injury_details': e['injury_details'] or None,
            'reason_if_excluded': reason or None,
        }
        rows.append(row)
        if row['internal_identity'] is None \
                and e['position'] not in TEAM_UNIT_POSITIONS:
            flags.append(('FD_PLAYER_MISSING_INTERNALLY', e['name'], ''))
        else:
            it, ip = row['internal_team'], row['internal_position']
            if it and it != e['team']:
                flags.append(('TEAM_MISMATCH', e['name'], f'{e["team"]}/{it}'))
            if ip and ip != e['position'] \
                    and e['position'] not in TEAM_UNIT_POSITIONS:
                flags.append(('POSITION_MISMATCH', e['name'],
                              f'{e["position"]}/{ip}'))
            if e['injury_indicator'] and elig == 'IN_OPPORTUNITY_POOL':
                flags.append(('STATUS_DISAGREEMENT', e['name'],
                              f'external says {e["injury_indicator"]!r}; we '
                              f'carry {state} and give him opportunity'))
            if elig == 'ELIGIBLE_BUT_NOT_MODELLED':
                flags.append(('ON_GAME_ROSTER_BUT_NO_MODELLED_OPPORTUNITY',
                              e['name'], str(state)))
    # INTERNAL ROWS THE EXTERNAL LIST DOES NOT CARRY.
    ext_norm = {_norm(e['name']) for e in external}
    for g, v in sorted(uni['names'].items()):
        if g in matched or not (uni['in_layer'].get(g) or {}).get('layers'):
            continue
        if _norm(v.get('name')) in ext_norm:
            continue
        flags.append(('INTERNAL_PLAYER_ABSENT_FROM_EXTERNAL',
                      v.get('name') or g,
                      f"{v.get('team')}/{v.get('position')} in layers "
                      f"{(uni['in_layer'].get(g) or {}).get('layers')}"))
    return rows, flags, ambiguous


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--external', required=True)
    ap.add_argument('--run-dir', required=True)
    ap.add_argument('--season', type=int, required=True)
    ap.add_argument('--week', type=int, required=True)
    ap.add_argument('--out', default=None)
    a = ap.parse_args(argv)

    ext = read_external(a.external)
    uni = internal_universe(a.run_dir)
    teams = sorted({e['team'] for e in ext if e['team']})
    ros, ros_week = roster_rows(a.season, a.week, set(teams))
    rows, flags, doc_ambiguous = reconcile(ext, uni, ros, a.season, a.week)

    doc = {
        'spec_version': SPEC_VERSION,
        'external_file': pathlib.Path(a.external).name,
        'external_is': 'CANDIDATE_UNIVERSE_AND_IDENTITY_REFERENCE_ONLY',
        'external_is_not': ['a predictive input', 'an eligibility authority',
                            'an official injury declaration'],
        'discarded_columns': list(DISCARDED_COLUMNS),
        'run_id': uni['run_id'], 'run_dir': a.run_dir,
        'season': a.season, 'week': a.week, 'teams': teams,
        'roster_capture_week_used': ros_week,
        'roster_basis': ('ROSTER_CAPTURE_THIS_WEEK' if ros_week == a.week
                         else f'CARRIED_FORWARD_FROM_WEEK_{ros_week}'),
        'n_external_rows': len(rows),
        'counts': {
            'in_opportunity_pool': sum(
                1 for r in rows
                if r['simulation_eligibility'] == 'IN_OPPORTUNITY_POOL'),
            'eligible_but_not_modelled': sum(
                1 for r in rows
                if r['simulation_eligibility'] == 'ELIGIBLE_BUT_NOT_MODELLED'),
            'excluded': sum(1 for r in rows
                            if r['simulation_eligibility'] == 'EXCLUDED'),
            'not_found_internally': sum(
                1 for r in rows
                if r['simulation_eligibility'] == 'ABSENT'),
            'team_units_out_of_scope': sum(
                1 for r in rows
                if r['simulation_eligibility'] == 'NOT_MODELLED'),
        },
        'flags': [{'flag': f, 'player': p, 'detail': d} for f, p, d in flags],
        'ambiguous_surname_keys_refused': [
            {'external_name': n, 'candidates': c} for n, c in
            (doc_ambiguous or [])],
        'rows': rows,
    }
    assert doc['n_external_rows'] == sum(doc['counts'].values()), (
        'every external row must land in exactly one bucket')
    out = json.dumps(doc, indent=1)
    if a.out:
        pathlib.Path(a.out).write_text(out)
    print(out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
