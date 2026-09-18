"""P6: the P7 dependency DAG, Phase 1, as implemented in production/pipeline.py.

WHAT THIS FILE IS FOR

`nfl/research/v4/p7/P7_DEPENDENCY_DAG_SPEC.md` s.1 states the defect the DAG
exists to catch: "a consumer reaches a source directly, by globbing a
directory, with no declaration that it consumes that source at all. Nothing in
the repository can answer 'who reads depth_charts?' except a grep, and a grep
found board.py after the leak had been running for the life of the corpus."

The spec named four glob-shaped findings -- `board.depth_rank`,
`qb_allocation.captured_depth_chart`, `team_volume_v1.coaches` and
`coverage.load_week_plan` -- and said a single AST test would have caught all
four. Three of the four still glob today and are now declared; the fourth was
repaired before this work and no longer reads the store, which this file
asserts rather than assumes.

THE TEST THAT MATTERS MOST IS NOT "THE AUDIT PASSES"

An audit that passes because its detector sees nothing is worse than no audit.
So `test_the_detector_catches_an_undeclared_read` builds a synthetic tree
containing a read nobody declared and requires the audit to FAIL on it, and
`test_the_detector_is_not_satisfied_by_a_neighbouring_declaration` requires
that a runtime-keyed declaration for one function does not excuse the function
beside it. Those two are what make the passing run mean anything.

WHAT IS NOT CLAIMED HERE

Spec Phase 2 -- a `read(node, cut)` accessor that returns bytes only for
declared edges -- is NOT implemented and no test below implies it is. Every
read in `EDGES` still happens by globbing a directory. What has changed is
that the read is declared, so an undeclared one fails. That is a bound on who
reads what, not a capability gate.
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State              # noqa: E402
from nfl.production import pipeline as PL                        # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _tmp_repo(files: dict):
    """A synthetic tree carrying only the modules a test needs."""
    d = tempfile.mkdtemp(prefix='p7dag_')
    for rel, src in files.items():
        p = pathlib.Path(d) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src)
    return d


# ===================================================== the declared edges

def test_every_edge_declares_enumerated_pregame_fields():
    o = PL.assert_edges_declarable()
    check('every declared edge is declarable', o.state is State.PASS,
          f'{o.code}: {o.detail}')
    cols = [e for e in PL.EDGES if e.kind == 'COLUMNS']
    check('every COLUMNS edge enumerates at least one field',
          all(e.fields for e in cols), str([e.consumer for e in cols
                                            if not e.fields]))
    check('every edge carries a reason',
          all((e.why or '').strip() for e in PL.EDGES))
    check('there is at least one BLOB_SELECTION edge, and it declares no field',
          any(e.kind == 'BLOB_SELECTION' and not e.fields for e in PL.EDGES))


def test_an_edge_may_not_declare_a_postgame_or_market_column():
    """The schedules blob carries 46 columns. The declaration is the bound."""
    bad = PL.Edge('nfl/production/team_volume_v1.py', 'schedules',
                  ('season', 'week', 'result'), 'why not')
    o = PL.assert_edge_fields_are_pregame(bad)
    check('a declared postgame column is refused',
          o.state is State.FAIL and o.code == 'EDGE_DECLARES_POSTGAME_FIELD',
          f'{o.code}')
    mkt = PL.Edge('nfl/production/team_volume_v1.py', 'schedules',
                  ('season', 'total_line'), 'why not')
    o2 = PL.assert_edge_fields_are_pregame(mkt)
    check('a declared market column is refused under its OWN code',
          o2.state is State.FAIL and o2.code == 'EDGE_DECLARES_MARKET_FIELD',
          f'{o2.code}')
    check('and the two codes are different, because they are different rules',
          o.code != o2.code)
    vague = PL.Edge('nfl/production/team_volume_v1.py', 'schedules', (),
                    '"reads schedules"')
    o3 = PL.assert_edge_fields_are_pregame(vague)
    check('"reads schedules" with no column list is refused',
          o3.state is State.FAIL and o3.code == 'EDGE_FIELDS_NOT_ENUMERATED',
          f'{o3.code}')
    silent = PL.Edge('nfl/production/team_volume_v1.py', 'schedules',
                     ('season',), '  ')
    check('an edge with no stated reason is refused',
          PL.assert_edge_fields_are_pregame(silent).code == 'EDGE_WHY_MISSING')


def test_the_spec_findings_are_declared_or_gone():
    idx = PL.edge_index()
    check('qb_allocation.captured_depth_chart declares depth_charts',
          'depth_charts' in idx.get('nfl/production/nonqb/qb_allocation.py',
                                    set()))
    check('team_volume_v1.coaches declares schedules',
          'schedules' in idx.get('nfl/production/team_volume_v1.py', set()))
    check('coverage.load_week_plan declares schedules',
          'schedules' in idx.get('nfl/capture/coverage.py', set()))
    # The fourth finding: board.depth_rank was repaired before this work, so
    # the honest assertion is that it no longer reads the store at all.
    sites = PL.scan_vintage_reads()
    check('board.py performs no direct vintage read (it was repaired)',
          not [s for s in sites if s['module'] == 'nfl/product/board.py'],
          str([s['line'] for s in sites
               if s['module'] == 'nfl/product/board.py']))
    # coaches reads home_coach/away_coach through an f-string, which a literal
    # scan cannot see. Declaring them is the only reason the bound is real.
    e = [x for x in PL.EDGES
         if x.consumer == 'nfl/production/team_volume_v1.py'
         and x.kind == 'COLUMNS'][0]
    check('the f-string-reached coach columns are in the declaration',
          {'home_coach', 'away_coach'} <= set(e.fields), str(e.fields))


# ===================================================== the AST read audit

def test_every_vintage_read_in_the_tree_is_declared():
    o = PL.audit_declared_reads()
    check('audit_declared_reads passes on the tree as it stands',
          o.state is State.PASS,
          f'{o.code}: {str(o.evidence)[:400]}')
    if o.state is State.PASS:
        v = o.value
        check('the audit found reads at all (a silent detector proves nothing)',
              v['n_reads'] > 20, str(v['n_reads']))
        check('every declared edge is exercised by a real read',
              not v['edges_not_exercised'], str(v['edges_not_exercised']))
        check('the three runtime-keyed reads are accounted for, not hidden',
              v['n_runtime_keyed'] == len(PL.RUNTIME_KEYED_READS),
              str(v['n_runtime_keyed']))


def test_the_detector_catches_an_undeclared_read():
    """The load-bearing test. Without it, a passing audit means nothing."""
    d = _tmp_repo({'nfl/production/sneaky.py': (
        "import glob, pathlib\n"
        "_REPO = pathlib.Path(__file__).resolve().parents[2]\n"
        "def rows():\n"
        "    return sorted(glob.glob(str(_REPO / 'nfl' / 'vintage'\n"
        "                                / 'depth_charts.*.csv.gz')))\n")})
    o = PL.audit_declared_reads(repo=d)
    check('an undeclared glob of the vintage store fails the audit',
          o.state is State.FAIL and o.code == 'UNDECLARED_VINTAGE_READ',
          f'{o.code}: {o.detail[:120]}')
    off = o.evidence.get('undeclared', [])
    check('and the offender is named by module, line and producer',
          off and off[0]['module'] == 'nfl/production/sneaky.py'
          and off[0]['producer'] == 'depth_charts' and off[0]['line'] > 0,
          str(off[:1]))


def test_the_detector_sees_through_a_constant_and_a_path_join():
    """Two shapes that a grep and a naive AST reader both miss."""
    d = _tmp_repo({
        'nfl/production/via_const.py': (
            "import pathlib\n"
            "_REPO = pathlib.Path(__file__).resolve().parents[2]\n"
            "VINTAGE = _REPO / 'nfl' / 'vintage'\n"
            "def rows():\n"
            "    return sorted(VINTAGE.glob('weekly_rosters.*raw.csv*'))\n"),
        'nfl/production/via_join.py': (
            "import glob, os\n"
            "_R = os.path.dirname(__file__)\n"
            "def rows():\n"
            "    return glob.glob(os.path.join(_R, 'nfl', 'vintage',\n"
            "                                  'schedules.*.csv.gz'))\n")})
    o = PL.audit_declared_reads(repo=d)
    mods = {x['module'] for x in o.evidence.get('undeclared', [])}
    check('a read through a module constant receiver is seen',
          'nfl/production/via_const.py' in mods, str(mods))
    check('a read built with os.path.join is seen',
          'nfl/production/via_join.py' in mods, str(mods))


def test_a_parameter_is_not_expanded_as_a_constant():
    """A false positive here would have been argued away, and the audit too."""
    d = _tmp_repo({'nfl/production/param.py': (
        "import pathlib\n"
        "p = pathlib.Path('nfl/vintage/weekly_rosters.aa.raw.csv.gz')\n"
        "def unrelated(p):\n"
        "    return open(p, 'rb').read()\n")})
    o = PL.audit_declared_reads(repo=d)
    check('a function parameter shadowing a module constant is not a read',
          o.state is State.PASS,
          f'{o.code}: {str(o.evidence)[:200]}')


def test_the_detector_is_not_satisfied_by_a_neighbouring_declaration():
    """RUNTIME_KEYED_READS is keyed on (module, function) for this reason."""
    d = _tmp_repo({'nfl/capture/delivered_injuries.py': (
        "import pathlib\n"
        "def store_raw(name):\n"
        "    return open(pathlib.Path('nfl/vintage') / name, 'rb').read()\n"
        "def store_raw_too(name):\n"
        "    return open(pathlib.Path('nfl/vintage') / name, 'rb').read()\n")})
    o = PL.audit_declared_reads(repo=d)
    check('the declared function is excused',
          o.state is State.FAIL and all(
              x['function'] != 'store_raw'
              for x in o.evidence.get('unattributable', [])),
          str(o.evidence.get('unattributable')))
    check('the neighbouring function beside it is NOT',
          o.state is State.FAIL
          and o.code == 'VINTAGE_READ_SOURCE_UNKNOWN'
          and any(x['function'] == 'store_raw_too'
                  for x in o.evidence.get('unattributable', [])),
          f'{o.code} {o.evidence.get("unattributable")}')


def test_a_write_into_the_store_is_not_a_consumer_edge():
    d = _tmp_repo({'nfl/production/writer.py': (
        "import pathlib\n"
        "def put(b):\n"
        "    return open(pathlib.Path('nfl/vintage') / 'x.gz', 'wb').write(b)\n")})
    o = PL.audit_declared_reads(repo=d)
    check('a write into the vintage store needs no read edge',
          o.state is State.PASS, f'{o.code}')
    sites = PL.scan_vintage_reads(repo=d)
    check('but it is still inventoried as a WRITE rather than dropped',
          [s for s in sites if s['kind'] == 'WRITE'], str(sites))


# ====================================================== node identity

def _nid(**kw):
    base = dict(spec_version='s1', code_identity='c1',
                input_identities=('a', 'b'), declared_fields=('x', 'y'))
    base.update(kw)
    return PL.node_identity(**base)


def test_node_identity_binds_all_four_components():
    """Spec s.5: H(spec_version, code_identity, sorted inputs, fields)."""
    base = _nid()
    check('changing spec_version changes identity', _nid(spec_version='s2')
          != base)
    check('changing code_identity changes identity',
          _nid(code_identity='c2') != base)
    check('changing an input identity changes identity',
          _nid(input_identities=('a', 'c')) != base)
    check('changing a declared field changes identity',
          _nid(declared_fields=('x', 'z')) != base)
    check('reordering inputs does NOT change identity (the set is sorted)',
          _nid(input_identities=('b', 'a')) == base)
    check('reordering fields does NOT change identity',
          _nid(declared_fields=('y', 'x')) == base)


def test_identity_components_are_length_prefixed():
    """('ab','c') and ('a','bc') are different inputs and must not collide."""
    check('a regrouping of concatenated components does not collide',
          _nid(input_identities=('ab', 'c'))
          != _nid(input_identities=('a', 'bc')))
    check('a field list and an input list do not bleed into each other',
          _nid(input_identities=('a',), declared_fields=('b',))
          != _nid(input_identities=('b',), declared_fields=('a',)))


def test_function_identity_refuses_rather_than_guesses():
    def sample():
        return 1
    fid = PL.function_identity(sample)
    check('a function has a code identity', fid.startswith('fn:'), fid)
    try:
        PL.function_identity(len)          # a C builtin has no source text
        check('a sourceless callable is refused', False, 'no raise')
    except ValueError as exc:
        check('a sourceless callable is refused, not given a stand-in',
              'CODE_IDENTITY_UNAVAILABLE' in str(exc), str(exc)[:120])


def test_code_identity_is_per_function_not_per_repository():
    def a():
        return 1

    def b():
        return 2
    check('two different functions have different code identities',
          PL.function_identity(a) != PL.function_identity(b))


# ======================================================== the graph

def _graph():
    """A small graph shaped like the real one: two vintages, three derived
    nodes, one forecast, plus an unrelated research artifact."""
    g = PL.DAG()
    g.add(PL.SourceNode('official_inactives'))
    g.add(PL.SourceNode('weekly_rosters'))
    ina = g.add(PL.VintageNode('official_inactives', 'a' * 8,
                               '2026-09-11T16:00:00+00:00'))
    ros = g.add(PL.VintageNode('weekly_rosters', 'b' * 8,
                               '2026-09-10T12:00:00+00:00'))
    res = g.add(PL.VintageNode('weekly_rosters', 'c' * 8,
                               '2026-09-01T12:00:00+00:00'))
    g.add(PL.DerivedNode('player_state', 'ps-1', 'fn:aaa',
                         (ina.key, ros.key), ('gsis_id', 'status')))
    g.add(PL.DerivedNode('team_state', 'ts-1', 'fn:bbb',
                         (ros.key,), ('team', 'season', 'week')))
    g.add(PL.DerivedNode('research_panel', 'rp-1', 'fn:ccc',
                         (res.key,), ('season',)))
    g.add(PL.ForecastNode('board', '2026-09-11T23:00:00+00:00', 'fc-1',
                          'fn:ddd', ('derived:player_state',
                                     'derived:team_state')))
    return g


def test_the_graph_refuses_an_ambiguous_or_dangling_node():
    g = _graph()
    try:
        g.add(PL.DerivedNode('player_state', 'ps-2', 'fn:aaa', (), ()))
        check('redefining a node key is refused', False, 'no raise')
    except PL.DagError as exc:
        check('redefining a node key is refused',
              'NODE_KEY_REDEFINED' in str(exc), str(exc)[:100])
    try:
        g.add(PL.DerivedNode('later', 'l-1', 'fn:eee', ('derived:nope',), ()))
        check('an unknown input is refused', False, 'no raise')
    except PL.DagError as exc:
        check('an input that is not yet in the graph is refused',
              'NODE_INPUT_UNKNOWN' in str(exc), str(exc)[:100])


def test_an_inactives_change_invalidates_only_what_reads_inactives():
    """Demonstration 2 of 3."""
    g = _graph()
    hit = g.invalidated_by(['vintage:official_inactives:' + 'a' * 8])
    check('player_state invalidates', 'derived:player_state' in hit)
    check('the forecast invalidates', 'forecast:board' in hit)
    check('team_state does NOT invalidate (it never reads inactives)',
          'derived:team_state' not in hit, str(sorted(hit)))
    check('the research panel does NOT invalidate',
          'derived:research_panel' not in hit, str(sorted(hit)))


def test_an_unrelated_research_artifact_does_not_invalidate_the_forecast():
    """Demonstration 3 of 3."""
    g = _graph()
    hit = g.invalidated_by(['derived:research_panel'])
    check('only the research node invalidates',
          hit == frozenset({'derived:research_panel'}), str(sorted(hit)))
    check('the game-day forecast is untouched', 'forecast:board' not in hit)


def test_a_derived_node_inherits_the_latest_vintage_beneath_it():
    """Spec s.4's second clause, the one that is easy to lose."""
    g = _graph()
    check('player_state inherits the INACTIVES stamp, the later of its two',
          g.max_learned_at('derived:player_state')
          == '2026-09-11T16:00:00+00:00',
          str(g.max_learned_at('derived:player_state')))
    check('team_state inherits its own single roster stamp',
          g.max_learned_at('derived:team_state')
          == '2026-09-10T12:00:00+00:00')
    check('the forecast reaches both vintages beneath it, deduplicated',
          len(g.reachable_vintages('forecast:board')) == 2,
          str([v.key for v in g.reachable_vintages('forecast:board')]))


def test_the_cut_is_judged_against_every_reachable_vintage():
    g = _graph()
    o = g.assert_cut_lawful('forecast:board')
    check('a forecast whose inputs all predate its cut is lawful',
          o.state is State.PASS, f'{o.code}: {o.detail[:160]}')
    late = PL.DAG()
    late.add(PL.SourceNode('official_inactives'))
    v = late.add(PL.VintageNode('official_inactives', 'z' * 8,
                                '2026-09-12T02:00:00+00:00'))
    late.add(PL.DerivedNode('player_state', 'ps-1', 'fn:aaa', (v.key,),
                            ('gsis_id',)))
    late.add(PL.ForecastNode('board', '2026-09-11T23:00:00+00:00', 'fc-1',
                             'fn:ddd', ('derived:player_state',)))
    o2 = late.assert_cut_lawful('forecast:board')
    check('a vintage learned AFTER the cut, two hops down, is caught',
          o2.state is State.FAIL and o2.code == 'FORECAST_READS_AFTER_CUT',
          f'{o2.code}: {o2.detail[:160]}')
    empty = PL.DAG()
    empty.add(PL.ForecastNode('board', '2026-09-11T23:00:00+00:00', 'fc-1',
                              'fn:ddd', ()))
    check('a forecast that reaches no captured bytes is refused',
          empty.assert_cut_lawful('forecast:board').code
          == 'FORECAST_READS_NO_VINTAGE')


# ======================================================== the cache

def test_a_cache_hit_may_not_be_restamped():
    """Spec s.5, rule 2. availability.py already pays for this one."""
    c = PL.NodeCache()
    first = c.put('derived:x', 'nid:1', 'run1.derived:x', '2026-09-11T10:00:00')
    check('the first write is stored', first.state is State.PASS, first.code)
    again = c.put('derived:x', 'nid:1', 'run1.derived:x',
                  '2026-09-11T11:00:00')
    check('restamping an unchanged node is refused',
          again.state is State.FAIL and again.code == 'CACHE_HIT_RESTAMPED',
          f'{again.code}')
    check('and the stored record keeps its ORIGINAL clock',
          c.get('derived:x', 'nid:1')['computed_at'] == '2026-09-11T10:00:00')


def test_a_recomputation_may_not_reuse_the_old_artifact_name():
    """Spec s.5, rule 1: superseding in place loses which bytes made a number."""
    c = PL.NodeCache()
    c.put('derived:x', 'nid:1', 'run1.derived:x', '2026-09-11T10:00:00')
    o = c.put('derived:x', 'nid:2', 'run1.derived:x', '2026-09-11T12:00:00')
    check('a changed identity may not overwrite the old artifact name',
          o.state is State.FAIL
          and o.code == 'RECOMPUTED_NODE_REUSED_ARTIFACT_NAME', f'{o.code}')
    ok = c.put('derived:x', 'nid:2', 'run2.derived:x', '2026-09-11T12:00:00')
    check('under a new name it is stored', ok.state is State.PASS, ok.code)
    check('and the old artifact still resolves to the old identity',
          c.get('derived:x', 'nid:1')['artifact'] == 'run1.derived:x')


# =========================================== the DAG inside the pipeline

def _pipe():
    p = PL.Pipeline('run-p6', tempfile.mkdtemp(prefix='p6run_'), 'arm',
                    '2026-09-18T00:00:00+00:00')
    p.dag.add(PL.SourceNode('weekly_rosters'))
    p.dag.add(PL.VintageNode('weekly_rosters', 'b' * 8,
                             '2026-09-10T12:00:00+00:00'))
    return p


def test_an_unchanged_input_reuses_the_cached_node():
    """Demonstration 1 of 3, through run_stage rather than beside it."""
    from sportsplatform.governance.outcome import Outcome
    calls = []

    def build():
        calls.append(1)
        return Outcome.ok('BUILT', value={'n': 1})

    node = PL.DerivedNode('team_state', 'ts-1', 'fn:bbb',
                          ('vintage:weekly_rosters:' + 'b' * 8,),
                          ('team', 'season', 'week'))
    p = _pipe()
    r1 = p.run_stage('feature_build', build, declared_inputs=['team'],
                     node=node)
    check('the first run executes the stage',
          r1.state == 'PASS' and len(calls) == 1, f'{r1.state} {r1.code}')
    r2 = p.run_stage('team_environment', build, declared_inputs=['team'],
                     node=node)
    check('an unchanged identity reuses the node instead of recomputing',
          r2.code == 'NODE_CACHE_HIT' and len(calls) == 1,
          f'{r2.code} calls={len(calls)}')
    check('and the reused record keeps the ORIGINAL computation stamp',
          r2.metrics.get('node_computed_at')
          == r1.metrics.get('node_computed_at'),
          f'{r1.metrics.get("node_computed_at")} vs '
          f'{r2.metrics.get("node_computed_at")}')
    check('the reuse is recorded as reuse, not as a second computation',
          r2.metrics.get('node_reused') is True
          and r1.metrics.get('node_reused') is False)


def test_a_changed_input_recomputes_the_node():
    from sportsplatform.governance.outcome import Outcome
    calls = []

    def build():
        calls.append(1)
        return Outcome.ok('BUILT', value={'n': 1})

    p = _pipe()
    p.dag.add(PL.VintageNode('weekly_rosters', 'd' * 8,
                             '2026-09-11T12:00:00+00:00'))
    n1 = PL.DerivedNode('team_state', 'ts-1', 'fn:bbb',
                        ('vintage:weekly_rosters:' + 'b' * 8,), ('team',))
    p.run_stage('feature_build', build, node=n1)
    # A NEW KEY, not a redefinition: the spec forbids reusing a name across
    # an identity change, and `DAG.add` refuses the redefinition outright.
    n2 = PL.DerivedNode('team_state_v2', 'ts-1', 'fn:bbb',
                        ('vintage:weekly_rosters:' + 'd' * 8,), ('team',))
    p.run_stage('team_environment', build, node=n2)
    check('a changed input identity produces a different node identity',
          p.dag.identity(n1.key) != p.dag.identity(n2.key))
    check('and the stage is recomputed rather than served from cache',
          len(calls) == 2, str(len(calls)))


def test_the_run_summary_carries_the_dag():
    from sportsplatform.governance.outcome import Outcome
    p = _pipe()
    node = PL.DerivedNode('team_state', 'ts-1', 'fn:bbb',
                          ('vintage:weekly_rosters:' + 'b' * 8,), ('team',))
    p.run_stage('feature_build', lambda: Outcome.ok('BUILT', value=1),
                node=node)
    s = p.summary()
    check('the summary carries the DAG spec version',
          s['dag']['spec_version'] == PL.DAG_SPEC_VERSION)
    check('it carries the declared edge count',
          s['dag']['n_declared_edges'] == len(PL.EDGES))
    check('it carries each node identity by key',
          s['dag']['nodes'].get('derived:team_state', '').startswith('nid:'),
          str(s['dag']['nodes']))
    check('and a record per node computation',
          len(s['dag']['node_records']) == 1, str(s['dag']['node_records']))


def test_a_stage_with_no_node_behaves_exactly_as_before():
    """Wiring the DAG in may not change the thirteen existing call sites."""
    from sportsplatform.governance.outcome import Outcome
    p = _pipe()
    r = p.run_stage('identity_resolution',
                    lambda: Outcome.ok('IDENTITY_RESOLVED', value=[1]),
                    declared_inputs=['players'])
    check('a stage naming no node still runs and passes',
          r.state == 'PASS' and r.code == 'IDENTITY_RESOLVED',
          f'{r.state} {r.code}')
    check('and records no node identity it did not have',
          'node_identity' not in r.metrics, str(r.metrics))


def test_the_postgame_guard_still_runs_before_the_node_is_touched():
    """Order matters: a postgame declaration must not first mint an identity."""
    from sportsplatform.governance.outcome import Outcome
    p = _pipe()
    node = PL.DerivedNode('team_state', 'ts-1', 'fn:bbb',
                          ('vintage:weekly_rosters:' + 'b' * 8,), ('team',))
    r = p.run_stage('feature_build', lambda: Outcome.ok('X', value=1),
                    declared_inputs=['targets'], node=node)
    check('a postgame input is refused before anything else happens',
          r.state == 'FAIL' and r.code == 'POSTGAME_INPUT_DECLARED',
          f'{r.state} {r.code}')
    check('and no node record was written for the refused stage',
          not p.node_records, str(p.node_records))


# ============================== the slice wired into the real run path

def test_register_captures_builds_vintage_nodes_from_the_run_s_own_captures():
    p = _pipe()
    src = {'weekly_rosters': {'sha256': 'ab' * 16,
                              'retrieved_at': '2026-09-11T12:00:00+00:00'},
           'official_inactives': {'sha256': 'cd' * 16,
                                  'retrieved_at': '2026-09-11T16:00:00+00:00'}}
    o = p.register_captures(src, '2026-09-11T23:00:00+00:00')
    check('the captures register', o.state is State.PASS, f'{o.code}')
    check('one vintage node per source, keyed by content hash',
          'vintage:weekly_rosters:' + 'ab' * 16 in p.dag.nodes
          and 'vintage:official_inactives:' + 'cd' * 16 in p.dag.nodes,
          str(sorted(p.dag.nodes)))
    check('and the source nodes above them',
          'source:official_inactives' in p.dag.nodes)
    bad = p.register_captures({'schedules': {'retrieved_at': 'x'}}, 'x')
    check('a capture with no hash is refused, not nodeed with a blank',
          bad.state is State.FAIL and bad.code == 'CAPTURE_NOT_NODEABLE',
          f'{bad.code}')


def test_the_cut_check_is_recorded_with_its_state_and_not_enforced():
    """`BLOCKED must never be interpreted as pass` -- so it is carried whole."""
    p = _pipe()
    p.register_captures(
        {'official_inactives': {'sha256': 'cd' * 16,
                                'retrieved_at': '2026-09-12T02:00:00+00:00'}},
        '2026-09-11T23:00:00+00:00')
    p.dag.add(PL.ForecastNode('run-p6', '2026-09-11T23:00:00+00:00', 'fc-1',
                              'fn:ddd',
                              ('vintage:official_inactives:' + 'cd' * 16,)))
    cc = p.cut_check()
    check('a capture retrieved after the cut is reported as FAIL',
          cc and cc['state'] == 'FAIL'
          and cc['code'] == 'FORECAST_READS_AFTER_CUT', str(cc))
    check('the record says plainly that it is not enforced in this slice',
          cc['enforcement'] == 'OBSERVATIONAL_IN_THIS_SLICE')
    check('and says why, naming the strictness difference',
          'strictly' in cc['why_not_enforced'], cc['why_not_enforced'][:80])
    check('the offending vintage is named, not just counted',
          cc['evidence'].get('offenders'), str(cc['evidence']))
    check('a run with no forecast node reports no cut check rather than a pass',
          _pipe().cut_check() is None)


def test_run_forecast_registers_the_slice_at_the_two_points_it_should():
    """The wiring is read from the source, never assumed from this file."""
    src = open(os.path.join(_ROOT, 'nfl', 'production',
                            'run_forecast.py')).read()
    check('captures are registered only after capture_validation PASSED',
          "if _cap.state == 'PASS':" in src
          and 'p.register_captures(src, args.written_at)' in src)
    check('a forecast node is registered before sealing',
          src.index('p.dag.add(PL.ForecastNode(')
          < src.index("p.run_stage('artifact_sealing'"))
    check('its cut is the run\'s written_at, not "now"',
          'PL.ForecastNode(\n            run_id, args.written_at,' in src)
    check('its code identity comes from the sealing function itself',
          'PL.function_identity(_seal)' in src)


# ================================================ the generated inventory

def test_the_read_inventory_is_generated_and_not_stale():
    """It answers "who reads depth_charts?" -- but only if it is current."""
    import json
    p = pathlib.Path(_ROOT) / 'nfl/research/v4/p7/P7_DECLARED_READS.json'
    check('the inventory exists', p.exists(), str(p))
    if not p.exists():
        return
    on_disk = json.loads(p.read_text())
    live = PL.read_inventory()
    check('the committed inventory matches a live audit of the tree',
          on_disk['by_producer'] == live['by_producer']
          and on_disk['runtime_keyed_reads'] == live['runtime_keyed_reads'],
          'regenerate: python3.12 nfl/production/pipeline.py '
          '--write-read-inventory')
    check('it records the audit state rather than implying one',
          on_disk['audit']['state'] == 'PASS'
          and on_disk['audit']['code'] == 'EVERY_VINTAGE_READ_DECLARED',
          str(on_disk['audit'])[:160])
    check('"who reads depth_charts?" is answerable from the artifact alone',
          len(on_disk['by_producer']['depth_charts']) >= 2,
          str(on_disk['by_producer'].get('depth_charts')))
    check('every producer entry names the consumer and its columns',
          all('consumer' in r and 'fields' in r
              for v in on_disk['by_producer'].values() for r in v))


def test_the_inventory_does_not_claim_phase_2_or_phase_3():
    """A spec presented as an implementation is the false green being audited."""
    import json
    p = pathlib.Path(_ROOT) / 'nfl/research/v4/p7/P7_DECLARED_READS.json'
    if not p.exists():
        check('the inventory exists', False, str(p))
        return
    d = json.loads(p.read_text())
    check('the phase is stated as declaration-only',
          d['phase'] == 'PHASE_1_DECLARATION_ONLY', d['phase'])
    txt = ' '.join(d['not_implemented'])
    check('Phase 2 is named as not implemented', 'PHASE_2' in txt)
    check('Phase 3 is named as not implemented', 'PHASE_3' in txt)
    check('and the limit of Phase 1 is stated in plain words',
          'does not mediate the bytes' in txt, txt[:200])
