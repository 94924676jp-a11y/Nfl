"""Join the DK universe to our canonical player identities. Nothing is dropped.

THE RULE THAT SHAPES THIS FILE

    A DK-eligible player our football system cannot project is a COVERAGE
    DEFECT. It is not permission to take the projection sitting in the
    next column of the same row.

So every DK row leaves here classified, and the classes are kept apart because
they need different actions:

    MATCHED_CANONICAL   joined to a gsis_id
    AMBIGUOUS           more than one canonical player answers to the name
    UNMATCHED           no canonical row answers to it at all
    DST                 a team defence. We have no team-defence model, so it
                        is its own class rather than an UNMATCHED person.

MATCHING IS DETERMINISTIC AND REFUSES TO BE CLEVER. Three passes, each stated:
exact (name, team); normalised (name, team); normalised name where the team
disagrees. No edit distance, no token-set ratio, no scoring. Two names either
normalise to the same string or they do not. A fuzzy matcher would quietly
join Josh Allen the quarterback to Josh Allen the edge rusher, and it would
never say that it had.

The third pass exists because a club code can differ or a player can have been
traded between the roster capture and the salary file. It is MATCHED with the
disagreement recorded in the row, never silently corrected.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import io
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402
from nfl.dfs.salaries import dk_universe as DK                # noqa: E402

SPEC_VERSION = 'dk-identity-reconciliation-1'

#: Positions our football engine emits a distribution for. DST is absent on
#: purpose: `statline.NOT_SIMULATED` records "the engine produces no
#: team-defence outputs at all".
MODELLED_POSITIONS = ('QB', 'RB', 'WR', 'TE')


def canonical_roster(season=2026, week=2) -> Outcome:
    """The canonical player universe for one week, from the roster capture."""
    blobs = sorted(glob.glob(str(
        _REPO / 'nfl/vintage/weekly_rosters.*raw.csv.gz')))
    if not blobs:
        return Outcome.blocked(
            'CANONICAL_ROSTER_ABSENT',
            'no raw weekly_rosters vintage carries names, so no join is '
            'possible. A join against a name-less frame would match nothing '
            'and report every DK player unmatched, which is a false finding.',
            cause=Cause.DATA)
    rows, per_blob = [], {}
    for b in blobs:
        txt = gzip.decompress(pathlib.Path(b).read_bytes()).decode(
            errors='replace')
        got = [r for r in csv.DictReader(io.StringIO(txt))
               if str(r.get('season')) == str(season)
               and str(r.get('week')) == str(week)]
        per_blob[pathlib.Path(b).name] = len(got)
        rows.extend(got)
    # One row per player, from whichever vintage carries him. Vintages repeat
    # the same week, so the same gsis_id appears once per blob; that is a
    # duplicate of the CAPTURE, not two players.
    by_id = {}
    for r in rows:
        gid = (r.get('gsis_id') or '').strip()
        if gid:
            by_id[gid] = r
    if not by_id:
        return Outcome.blocked(
            'CANONICAL_ROSTER_EMPTY_FOR_WEEK',
            f'{len(blobs)} roster vintage(s) hold no {season} week {week} '
            f'row. Zero is an error, not an empty league.',
            cause=Cause.DATA, blobs=per_blob)
    return Outcome.ok(
        'CANONICAL_ROSTER_LOADED', value=list(by_id.values()),
        detail=f'{len(by_id)} distinct player(s) across {len(blobs)} vintage(s)',
        spec_version=SPEC_VERSION, n_players=len(by_id),
        n_vintages=len(blobs), rows_per_vintage=per_blob,
        n_raw_rows=len(rows))


def reconcile(dk_rows, roster_rows) -> dict:
    """Every DK row, classified. Same length in as out."""
    by_exact = collections.defaultdict(list)
    by_norm = collections.defaultdict(list)
    by_norm_name = collections.defaultdict(list)
    for r in roster_rows:
        nm = (r.get('full_name') or '').strip()
        tm = (r.get('team') or '').strip()
        if not nm:
            continue
        by_exact[(nm, tm)].append(r)
        by_norm[(DK._norm_name(nm), tm)].append(r)
        by_norm_name[DK._norm_name(nm)].append(r)

    out = []
    for d in dk_rows:
        rec = {
            'dk_name': d['dk_name'], 'dk_pos': d['dk_pos'],
            'dk_team': d['dk_team'], 'team': d['team'],
            'opponent': d['opponent'], 'is_home': d['is_home'],
            'salary': d['salary'], 'inj_flag': d['inj_flag'],
            'dk_depth': d['dk_depth'],
            'canonical_name': None, 'gsis_id': None,
            'canonical_team': None, 'canonical_position': None,
            'roster_status': None,
            'match_method': None, 'status': None, 'note': None,
        }
        if d['dk_pos'] == 'DST':
            rec['status'] = DK.STATUS_DST
            rec['match_method'] = 'NOT_A_PERSON'
            rec['note'] = ('a team defence. The engine produces no '
                           'team-defence outputs at all, so this is its own '
                           'class and not an unmatched player.')
            out.append(rec)
            continue
        hits = by_exact.get((d['dk_name'], d['team']))
        method = DK.MATCH_EXACT
        alias = DK.NAME_ALIASES.get((d['dk_name'], d['team']))
        if not hits and alias:
            # An alias resolves against the SAME CLUB only, and only when the
            # answer is unique. A stale alias therefore becomes a refusal.
            cand = by_exact.get((alias['canonical'], d['team'])) or []
            if len(cand) == 1:
                hits, method = cand, DK.MATCH_ALIAS
                rec['note'] = f"declared alias: {alias['evidence']}"
            else:
                rec['note'] = (
                    f"declared alias {alias['canonical']!r} resolves to "
                    f"{len(cand)} roster row(s) on {d['team']}, not one. "
                    f"The alias is not applied.")
        if not hits:
            hits = by_norm.get((DK._norm_name(d['dk_name']), d['team']))
            method = DK.MATCH_NORMALIZED
        if not hits:
            hits = by_norm_name.get(DK._norm_name(d['dk_name']))
            method = DK.MATCH_NAME_ONLY
        if not hits:
            rec['status'] = DK.STATUS_UNMATCHED
            rec['note'] = ('no canonical roster row answers to this name in '
                           'any club. Recorded, never dropped.')
        elif len(hits) > 1:
            rec['status'] = DK.STATUS_AMBIGUOUS
            rec['match_method'] = method
            rec['note'] = (f'{len(hits)} canonical players normalise to this '
                           f'name: '
                           f'{[h.get("gsis_id") for h in hits]}. Refused '
                           f'rather than picked.')
        else:
            h = hits[0]
            rec.update({
                'canonical_name': (h.get('full_name') or '').strip(),
                'gsis_id': (h.get('gsis_id') or '').strip(),
                'canonical_team': (h.get('team') or '').strip(),
                'canonical_position': (h.get('position') or '').strip(),
                'roster_status': (h.get('status') or '').strip(),
                'match_method': method, 'status': DK.STATUS_MATCHED,
            })
            if method == DK.MATCH_NAME_ONLY:
                rec['note'] = (f'matched on name alone: DK says '
                               f'{d["team"]}, the roster says '
                               f'{rec["canonical_team"]}. Recorded, not '
                               f'corrected.')
            if (rec['canonical_position'] != d['dk_pos']
                    and rec['canonical_position']):
                rec['note'] = ((rec['note'] or '') +
                               f' position disagrees: DK {d["dk_pos"]}, '
                               f'roster {rec["canonical_position"]}.').strip()
        out.append(rec)
    assert len(out) == len(dk_rows), 'RECONCILIATION_LOST_A_ROW'
    return {'spec_version': SPEC_VERSION, 'n_in': len(dk_rows),
            'n_out': len(out), 'rows': out}


def summarise(rec) -> dict:
    rows = rec['rows']
    by_status = collections.Counter(r['status'] for r in rows)
    by_method = collections.Counter(
        r['match_method'] for r in rows if r['status'] == DK.STATUS_MATCHED)
    team_mismatch = [r for r in rows
                     if r['status'] == DK.STATUS_MATCHED
                     and r['match_method'] == DK.MATCH_NAME_ONLY]
    pos_mismatch = [r for r in rows
                    if r['canonical_position']
                    and r['canonical_position'] != r['dk_pos']]
    ids = collections.Counter(r['gsis_id'] for r in rows if r['gsis_id'])
    return {
        'by_status': dict(by_status),
        'by_match_method': dict(by_method),
        'n_team_disagreements': len(team_mismatch),
        'team_disagreements': [
            {'dk_name': r['dk_name'], 'dk_team': r['dk_team'],
             'canonical_team': r['canonical_team']} for r in team_mismatch],
        'n_position_disagreements': len(pos_mismatch),
        'position_disagreements': [
            {'dk_name': r['dk_name'], 'dk_pos': r['dk_pos'],
             'canonical_position': r['canonical_position']}
            for r in pos_mismatch],
        'duplicate_gsis_ids': {k: v for k, v in ids.items() if v > 1},
        'unmatched': [
            {'dk_name': r['dk_name'], 'dk_team': r['dk_team'],
             'dk_pos': r['dk_pos'], 'salary': r['salary']}
            for r in rows if r['status'] == DK.STATUS_UNMATCHED],
        'ambiguous': [
            {'dk_name': r['dk_name'], 'dk_team': r['dk_team'],
             'note': r['note']}
            for r in rows if r['status'] == DK.STATUS_AMBIGUOUS],
    }
