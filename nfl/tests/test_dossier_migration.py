"""The dossier explains canonical football truth; it no longer makes its own.

`review/dossier_reference.py` is a frozen copy of the builder at f43c30e, the
accepted pre-migration behaviour. This suite runs it and the migrated builder
over the same fixture and compares every field of every dossier.

The comparison is field-by-field and then whole-dossier by hash, because a
count of dossiers proves nothing: two builders agreeing on how many players
exist while disagreeing about one of them is the failure this is here to
catch.
"""
from __future__ import annotations

import ast
import collections
import hashlib
import json
import pathlib
import random
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import dossier as D                        # noqa: E402
from nfl.production.review import dossier_reference as R              # noqa: E402
from nfl.production.review import evidence as EV                      # noqa: E402
from nfl.production.state import slate_state as SS                    # noqa: E402
from nfl.production.universe import player_universe as PU             # noqa: E402

PASSED = FAILED = 0
SEASON, WEEK, GAME = 2026, 2, '2026_02_CAR_ATL'
CUT = '2026-09-22T23:00:00Z'


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def fixture():
    """The real universe plus synthetic role, snap, usage, inactive, vacated,
    attribution and projection inputs, seeded, chosen to exercise EVERY
    branch: supported and unsupported roles, players with snap rows whose
    offensive percentage is null, players with special-teams snaps only,
    players with no usage at all, and players the model never emitted."""
    u = PU.build(SEASON, WEEK, GAME, CUT).value
    ids = [r['gsis_id'] for r in u if r['gsis_id']]
    rnd = random.Random(4)
    role_rows, snap_rows, usage_rows = [], [], []
    for i, r in enumerate(u):
        pid = r['gsis_id']
        if not pid:
            continue
        if i % 3 == 0:
            role_rows.append({
                'gsis_id': pid,
                'room': 'carries' if i % 2 else 'targets',
                'role': 'LEAD' if i % 5 else 'ROLE_UNCERTAIN',
                'role_support': ('ROLE_SUPPORTED' if i % 4
                                 else 'ROLE_UNSUPPORTED'),
                'role_why': f'why{i}',
                'role_unsupported_why': [f'u{i}'] if i % 4 == 0 else [],
                'evidence': {'current_season_usage': {
                    'carries': float(i % 9), 'targets': float(i % 7),
                    'carry_share': round((i % 9) / 20, 4),
                    'target_share': round((i % 7) / 25, 4),
                    'club_of_record': r['team']}}})
        if i % 4 == 0 and r.get('pfr_id'):
            for w in (1, 2):
                snap_rows.append({
                    'pfr_player_id': r['pfr_id'], 'week': w,
                    'offense_pct': (None if i % 8 == 0
                                    else round(rnd.uniform(.1, .95), 3)),
                    'st_pct': (round(rnd.uniform(0, .6), 3) if i % 3
                               else None)})
        if i % 5 == 0:
            usage_rows.append({'gsis_id': pid, 'carries': float(i % 6),
                               'targets': float(i % 4)})
    proj_summ = {'mean': 9.5, 'sd': 3.0, 'p05': 4.0, 'p25': 7.0, 'p50': 9.0,
                 'p75': 12.0, 'p95': 16.0, 'p_zero': 0.02, 'n_draws': 1000}
    return dict(
        universe_rows=u, role_rows=role_rows, snap_rows=snap_rows,
        usage_rows=usage_rows, inactive_ids=set(ids[:6]),
        vacated={ids[7]: {'from': ids[0], 'carries': 2.5}},
        opportunity_attribution={
            ids[9]: {'tiers': [{'tier': 'PRIOR_SEASON', 'w': 0.4}]}},
        projection={'per_player': {pid: {'dk_points': proj_summ,
                                         'carries': dict(proj_summ, mean=4.2)}
                                   for pid in ids[::2]},
                    'run_id': 'RUN-X', 'digests': {'a': 'b'},
                    'n_draws': 1000, 'metrics_absent': ['qb/int']},
        information_cut=CUT)


def _ref_hash(d, exclude_axes=()):
    """The reference dossier's football body, hashed the same way the
    migrated one hashes its own. spec_version is excluded because the frozen
    copy was deliberately renamed so an artifact can never be confused about
    which builder wrote it. `exclude_axes` names any axis under a declared
    semantic change."""
    body = dict(d.as_dict(), spec_version='COMPARED_WITHOUT_SPEC_VERSION')
    body['axes'] = {k: v for k, v in body['axes'].items()
                    if k not in exclude_axes}
    return hashlib.sha256(json.dumps(
        body, sort_keys=True, separators=(',', ':'),
        default=str).encode()).hexdigest()[:16]


# -- 1. equivalence ---------------------------------------------------------
def test_equivalence_field_by_field():
    kw = fixture()
    a = R.build_dossiers(**kw)
    b = D.build_dossiers(**kw)
    ok(a.state.name == 'PASS' and b.state.name == 'PASS',
       f'both builders succeed: {a.code} / {b.code}')
    A = {d.gsis_id: d for d in a.value['dossiers']}
    B = {d.gsis_id: d for d in b.value['dossiers']}
    ok(set(A) == set(B), f'identical player set: {len(A)} vs {len(B)}')
    ok(a.value['n'] == b.value['n'] == len(A),
       f'identical dossier count: {a.value["n"]}')
    ok(a.value['by_uncertainty_state'] == b.value['by_uncertainty_state'],
       f'identical uncertainty classification: '
       f'{b.value["by_uncertainty_state"]}')
    ok(a.value['n_with_projection'] == b.value['n_with_projection'],
       f'identical projection coverage: {b.value["n_with_projection"]}')

    diffs = collections.Counter()
    example = {}
    for pid in A:
        da, db = A[pid].as_dict(), B[pid].as_dict()
        for k in ('evidence_provenance', 'state_identity'):
            db.pop(k, None)
        for k in sorted(set(da) | set(db)):
            if k == 'axes':
                for ax in sorted(set(da['axes']) | set(db['axes'])):
                    if da['axes'].get(ax) != db['axes'].get(ax):
                        diffs[f'axes.{ax}'] += 1
                        example.setdefault(f'axes.{ax}',
                                           (pid, da['axes'].get(ax),
                                            db['axes'].get(ax)))
            elif da.get(k) != db.get(k):
                diffs[k] += 1
                example.setdefault(k, (pid, da.get(k), db.get(k)))

    # Two DECLARED differences, and nothing else may differ.
    #   spec_version          -- the frozen copy was renamed on purpose.
    #   axes.official_availability -- the availability semantics slice. The
    #     old builder called every unlisted player ACTIVE once a non-empty
    #     inactive set had been passed. That was a documented defect, it was
    #     corrected deliberately, and every changed player is enumerated in
    #     nfl/research/state/AVAILABILITY_SEMANTICS_CHANGE.json and asserted
    #     in test_availability_semantics.py. It is NOT a regression of this
    #     migration and it is not compared here.
    declared = {'spec_version', 'axes.official_availability'}
    real = {k: v for k, v in diffs.items() if k not in declared}
    ok(not real, f'no behavioural difference in any field of any dossier: '
                 f'{dict(real) or "none"}')
    for k, (pid, x, y) in list(example.items()):
        if k in real:
            print(f'      {k} on {pid}')
            print(f'        ref {json.dumps(x, default=str)[:300]}')
            print(f'        new {json.dumps(y, default=str)[:300]}')
    ok(diffs.get('spec_version') == len(A),
       f'spec_version differs on all {len(A)} dossiers, because the frozen '
       f'reference was deliberately renamed')
    ok(diffs.get('axes.official_availability', 0) > 0,
       f'and availability differs on '
       f'{diffs.get("axes.official_availability", 0)} of {len(A)} -- the '
       f'declared semantic correction, proved separately')
    n_axes = len(R.AXIS_ORDER)
    print(f'  ---- {len(A)} dossiers x {n_axes} axes compared, '
          f'{sum(real.values())} behavioural difference(s) ----')


def test_whole_dossier_hashes_match():
    kw = fixture()
    a = R.build_dossiers(**kw)
    b = D.build_dossiers(**kw)
    A = {d.gsis_id: d for d in a.value['dossiers']}
    B = {d.gsis_id: d for d in b.value['dossiers']}
    X = ('official_availability',)
    same = sum(1 for pid in A
               if _ref_hash(A[pid], X) == B[pid].football_hash(X))
    ok(same == len(A),
       f'football-body hash identical for {same}/{len(A)} dossiers, with '
       f'the availability axis excluded by name and proved separately')
    bad = [pid for pid in A
           if _ref_hash(A[pid], X) != B[pid].football_hash(X)]
    if bad:
        print(f'      first mismatch: {bad[0]}')


def test_the_two_entry_points_agree():
    """The shim and the canonical entry point are the SAME implementation
    reached by different doors, so they must not be able to disagree."""
    kw = fixture()
    via_shim = D.build_dossiers(**kw)
    st = SS.state_from_legacy_rows(
        kw['universe_rows'], role_rows=kw['role_rows'],
        snap_rows=kw['snap_rows'], usage_rows=kw['usage_rows'],
        inactive_ids=kw['inactive_ids'], information_cut=CUT)
    direct = D.build_from_state(
        st.value, projection=kw['projection'], vacated=kw['vacated'],
        opportunity_attribution=kw['opportunity_attribution'],
        information_cut=CUT,
        legacy_rows_by_id={r['gsis_id']: r for r in kw['universe_rows']})
    A = {d.gsis_id: d.football_hash() for d in via_shim.value['dossiers']}
    B = {d.gsis_id: d.football_hash() for d in direct.value['dossiers']}
    ok(A == B, f'shim and build_from_state produce identical dossiers: '
               f'{sum(1 for k in A if A[k] == B.get(k))}/{len(A)}')


def test_the_canonical_state_path_also_builds():
    """The whole point of the migration: a dossier from a state built out of
    the vintage store, with no legacy rows anywhere in the call."""
    s = SS.build_one_game(SEASON, WEEK, GAME, CUT)
    ok(s.state.name == 'PASS', f'the governed state builds: {s.code}')
    d = D.build_from_state(s.value, information_cut=CUT)
    ok(d.state.name == 'PASS', f'and dossiers build from it: {d.code}')
    ok(d.value['n'] == len(s.value.players),
       f'one dossier per player in the state: {d.value["n"]}')
    one = d.value['dossiers'][0]
    ok(one.state_identity['registry_identity'] == s.value.registry_identity,
       f'each dossier records the registry that defined its evidence: '
       f'{one.state_identity["registry_identity"]}')
    ok(one.state_identity['source_hashes'].get('weekly_rosters'),
       'and the content hash of the roster capture behind it')
    ok(one.state_identity['freshness_verdict'] == 'SOURCES_PRESENT',
       f'and the freshness verdict: '
       f'{one.state_identity["freshness_verdict"]}')


# -- 2. no parallel football truth -----------------------------------------
def test_the_dossier_reads_no_raw_football_source():
    """Football evidence must arrive through PregameSlateState. Projection
    and simulation artifacts are the dossier's own to read."""
    src = (_REPO / 'nfl/production/review/dossier.py').read_text()
    tree = ast.parse(src)
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            for a in n.names:
                imported.add(a.name)
            if n.module:
                imported.add(n.module.split('.')[-1])
        elif isinstance(n, ast.Import):
            for a in n.names:
                imported.add(a.name.split('.')[-1])
    forbidden = {'vintage_selector', 'player_universe', 'depth_role',
                 'role_state', 'usage_vintage', 'depth_vintage',
                 'inactives', 'current_season_evidence',
                 'current_season_team_volume', 'csv', 'gzip'}
    hit = sorted(imported & forbidden)
    ok(not hit, f'the dossier imports no football-source module or table '
                f'reader: {hit}')
    for token in ('.csv', '.gz', 'vintage/', 'vintage_manifest',
                  'weekly_rosters', 'depth_charts', 'schedules'):
        ok(token not in src.replace('depth_charts vintage', 'DESCRIPTIVE')
           .replace('weekly_rosters vintage', 'DESCRIPTIVE'),
           f'and names no raw source path or file: {token!r}')
    ok('player_draws.npz' in src and 'player_draws_manifest.json' in src,
       'while it still reads the projection artifact, which is its own job')
    ok('slate_state' in imported or 'SS' in src,
       'and it does read PregameSlateState, so the boundary is real')


def test_no_room_derivation_remains_in_the_dossier():
    """A substring test would have been wrong here and was: the axis SOURCE
    LABEL still reads 'roster_position -> POSITION_ROOM', because that is
    still a true description of where the value ultimately comes from, and
    the label is what keeps two dossiers from different weeks comparable.
    What must be gone is the LOOKUP -- the dossier doing the derivation
    itself. So this reads the syntax tree rather than the text."""
    src = (_REPO / 'nfl/production/review/dossier.py').read_text()
    tree = ast.parse(src)
    lookups, roster_reads = [], []
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and n.id == 'POSITION_ROOM':
            lookups.append('POSITION_ROOM')
        if isinstance(n, ast.Attribute) and n.attr == 'POSITION_ROOM':
            lookups.append('*.POSITION_ROOM')
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == 'get' and n.args \
                and isinstance(n.args[0], ast.Constant) \
                and n.args[0].value in ('roster_position', 'roster_status',
                                        'officially_inactive',
                                        'special_teams_role',
                                        'offensive_depth_rank'):
            roster_reads.append(n.args[0].value)
    ok(not lookups,
       f'no POSITION_ROOM lookup executes in the dossier: {lookups}')
    ok(not roster_reads,
       f'and it reads no raw universe field by name: {sorted(set(roster_reads))}')
    ok("'roster_position -> POSITION_ROOM'" in src,
       'the descriptive source label is deliberately kept, so the axis reads '
       'the same as it did before the migration')
    st = SS.build_one_game(SEASON, WEEK, GAME, CUT).value
    withroom = [p for p in st.players if p.room.value]
    ok(withroom, f'the state supplies room instead: {len(withroom)} of '
                 f'{len(st.players)} players are in a modelled room')
    ok(all(p.room.grade == EV.UNAVAILABLE
           for p in st.players if not p.room.value),
       'and a player in no modelled room reads UNAVAILABLE, not a blank')


# -- 3. provenance ----------------------------------------------------------
def test_provenance_is_preserved_not_flattened():
    s = SS.build_one_game(SEASON, WEEK, GAME, CUT)
    d = D.build_from_state(s.value, information_cut=CUT)
    one = d.value['dossiers'][0]
    prov = one.evidence_provenance
    ok(set(prov) == set(D.STATE_AXIS_SOURCE),
       f'every football axis names the state axis behind it: {len(prov)}')
    graded = {k: v.get('grade') for k, v in prov.items() if 'grade' in v}
    ok(set(graded.values()) <= set(EV.GRADES),
       f'and every one carries a declared grade, not a generic value: '
       f'{sorted(set(graded.values()))}')
    ok(prov['roster_status'].get('source', '').endswith('.csv.gz')
       or '#' in str(prov['roster_status'].get('source')),
       f'provenance keeps the blob and hash the value came from: '
       f'{str(prov["roster_status"].get("source"))[-60:]}')
    ok(prov['roster_status'].get('observed_at'),
       f'and when it was retrieved: {prov["roster_status"]["observed_at"]}')
    grades_seen = collections.Counter(
        v.get('grade') for pd in d.value['dossiers']
        for v in pd.evidence_provenance.values() if v.get('grade'))
    ok(len(grades_seen) >= 2,
       f'more than one grade survives across the slate, so nothing was '
       f'collapsed: {dict(grades_seen)}')


# -- 4. UNAVAILABLE semantics ----------------------------------------------
def test_unavailable_is_not_zero():
    s = SS.build_one_game(SEASON, WEEK, GAME, CUT)
    d = D.build_from_state(s.value, information_cut=CUT)
    bad = []
    for pd in d.value['dossiers']:
        for name in ('carries', 'targets', 'carry_share', 'target_share',
                     'current_season_snap_share'):
            ax = pd.axis(name)
            if ax.grade in (EV.UNAVAILABLE, EV.COLD_START) and ax.value == 0:
                bad.append((pd.gsis_id, name))
    ok(not bad, f'no unmeasured axis carries a zero: {len(bad)}')
    one = d.value['dossiers'][0]
    ok(one.axis('carries').value is None,
       'an unmeasured carry count is None, not 0.0')
    ok(one.axis('routes').grade == EV.UNAVAILABLE
       and one.axis('routes').value is None,
       'routes stay UNAVAILABLE on every dossier, with no value')


def test_unknown_starter_is_not_false():
    s = SS.build_one_game(SEASON, WEEK, GAME, CUT).value
    unknown = [p for p in s.players if p.offensive_depth.value is None]
    ok(unknown, f'{len(unknown)} player(s) have no offensive depth listing')
    ok(all(p.declared_starter.value is None
           and p.declared_starter.grade == EV.UNAVAILABLE for p in unknown),
       'every one of them reads UNKNOWN on declared_starter, never False')
    listed = [p for p in s.players if p.offensive_depth.value is not None]
    ok(all(isinstance(p.declared_starter.value, bool) for p in listed),
       f'and the {len(listed)} who ARE listed carry a real boolean')


def test_not_on_inactive_list_is_not_active_anywhere():
    """When this test was written the dossier still translated
    NOT_ON_INACTIVE_LIST to ACTIVE, and it asserted that, calling it an open
    question. The question has since been answered: absence from a negative
    list is not affirmative evidence, and ACTIVE is now unreachable in the
    dossier too."""
    ids = [r['gsis_id'] for r in PU.build(SEASON, WEEK, GAME, CUT).value
           if r['gsis_id']]
    s = SS.build_one_game(SEASON, WEEK, GAME, CUT,
                          inactive_ids=set(ids[:3])).value
    others = [p for p in s.players if p.gsis_id not in set(ids[:3])]
    ok(not any(p.availability.value == 'ACTIVE' for p in others),
       f'canonical state calls none of {len(others)} unlisted players ACTIVE')
    d = D.build_from_state(s, information_cut=CUT)
    tr = {pd.axis('official_availability').value
          for pd in d.value['dossiers'] if pd.gsis_id not in set(ids[:3])}
    ok('ACTIVE' not in tr,
       f'and neither does the dossier: {sorted(tr)}')


def test_missing_optional_evidence_reduces_confidence_without_inventing():
    s = SS.build_one_game(SEASON, WEEK, GAME, CUT)
    d = D.build_from_state(s.value, information_cut=CUT)
    states = collections.Counter(x.uncertainty_state
                                 for x in d.value['dossiers'])
    ok(EV.CURRENT_ROLE_COLD_START in states,
       f'with no role or snap evidence supplied the slate reads cold-start '
       f'rather than confident: {dict(states)}')
    ok(all(x.axis('role').value is None for x in d.value['dossiers']),
       'and no role was invented for anyone')
    ok(all(x.axis('role').grade == EV.UNAVAILABLE
           for x in d.value['dossiers']),
       'the role axis is UNAVAILABLE, not a default')


def main():
    for t in (test_equivalence_field_by_field,
              test_whole_dossier_hashes_match,
              test_the_two_entry_points_agree,
              test_the_canonical_state_path_also_builds,
              test_the_dossier_reads_no_raw_football_source,
              test_no_room_derivation_remains_in_the_dossier,
              test_provenance_is_preserved_not_flattened,
              test_unavailable_is_not_zero,
              test_unknown_starter_is_not_false,
              test_not_on_inactive_list_is_not_active_anywhere,
              test_missing_optional_evidence_reduces_confidence_without_inventing):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
