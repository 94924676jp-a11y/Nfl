"""The production pipeline orchestrator.

FOURTEEN STAGES, each returning success/failure, input hashes, model/spec
version, warnings, a refusal code if blocked, and timing.

TWO STRUCTURAL RULES

1. NO STAGE MAY CONSUME ANOTHER STAGE'S POSTGAME OUTPUT. Stages declare what
   they read, and the orchestrator refuses a declaration that names a postgame
   field.
2. A STAGE WITH NO PRODUCTION MODEL RETURNS A NAMED REFUSAL, never a fabricated
   forecast. `STAGE_NOT_IMPLEMENTED` is a result; a made-up number is not.
3. A STAGE MAY NOT READ BYTES IT HAS NOT DECLARED. The P7 dependency DAG at the
   foot of this file states every read of the vintage store as an edge with its
   columns enumerated, and an AST audit fails on any read that is not declared.
   Spec: `nfl/research/v4/p7/P7_DEPENDENCY_DAG_SPEC.md`, Phase 1.
"""
from __future__ import annotations

import ast as _ast
import dataclasses
import datetime as _dt
import hashlib
import inspect as _inspect
import json
import pathlib
import re as _re
import sys
import time
from typing import Callable, Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.production import refusal as RF                             # noqa: E402

PIPELINE_VERSION = 'nfl-production-pipeline-1'

STAGES = ('capture_validation', 'identity_resolution', 'feature_build',
          'team_environment', 'appearance', 'participation',
          'targets_carries', 'conversion', 'td_layer', 'qb_layer',
          'joint_reconciliation', 'player_draws', 'scoring',
          'artifact_sealing')

# Fields that exist only after a game is played. A stage declaring any of these
# as an input is refused before it runs.
POSTGAME_FIELDS = {
    'n_td', 'rec_td', 'rush_td', 'pass_td', 'targets', 'receptions',
    'rec_yards', 'rush_yards', 'pass_yards', 'carries', 'interceptions',
    'sacks', 'completions', 'attempts', 'snaps', 'pass_snaps', 'offense_snaps',
    'final_status', 'inactive', 'appeared', 'did_not_appear', 'score',
    'result', 'weekly_rosters.status',
}


@dataclasses.dataclass
class StageResult:
    stage: str
    state: str
    code: str
    detail: str = ''
    input_hashes: dict = dataclasses.field(default_factory=dict)
    spec_version: Optional[str] = None
    warnings: list = dataclasses.field(default_factory=list)
    refusal_code: Optional[str] = None
    elapsed_s: float = 0.0
    # Stage-reported measurements. `elapsed_s` is orchestrator wall clock for
    # the stage; a stage that generates draws reports the draw-generation time
    # separately here, because the two are not the same number and reporting
    # only the first would overstate how much of the run is modelling.
    metrics: dict = dataclasses.field(default_factory=dict)
    # GOVERNANCE THE STAGE REPORTED, NOT GOVERNANCE THIS CLASS DECIDED.
    #
    # A stage that composes several engine layers returns their governance
    # values and their per-layer spec versions in its evidence, and every one
    # of them used to be dropped here, because this class copied `warnings`
    # and a metrics whitelist and nothing else. The sealed run then showed
    # `"warnings": []` on four stages whose layers had raised warnings naming
    # SIGNAL_WEAK and CALIBRATION_DEFECT by name, and the only surviving copy
    # of those states was a sentence a human had retyped into `spec_version`
    # at the call site -- where the two copies had already drifted.
    #
    # These three fields are TRANSPORT. Nothing here reads them, ranks them or
    # decides what any of them means for publication: they carry what the
    # producing layer said, with the layer's name attached, so the question
    # can be put to the artifact instead of to the source code.
    governance: list = dataclasses.field(default_factory=list)
    spec_versions: dict = dataclasses.field(default_factory=dict)
    warnings_detail: list = dataclasses.field(default_factory=list)
    value: object = None

    def as_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d.pop('value', None)
        return d


def _governance_records(evidence) -> list:
    """A stage's declared governance values, as records, never summarised.

    Two shapes arrive here and both are the producer's, not this function's.
    A stage that aggregates several engine layers reports a LIST of records
    that already name the layer each value came from. A single layer reports a
    BARE value -- `layers.receiving_conversion` returns
    `governance='HOLD_CHARACTERIZED + CALIBRATION_DEFECT'` -- and there is no
    layer name to attach to it, so `layer` is recorded as None rather than
    guessed from the stage name. A guess here would be indistinguishable from
    a fact once it is in the artifact.

    Nothing is merged, ordered by severity, or dropped. Two layers declaring
    the same value stay two records, because "both said it" and "one said it"
    are different facts.
    """
    gov = (evidence or {}).get('governance')
    if gov is None:
        return []
    if isinstance(gov, list):
        return list(gov)
    if isinstance(gov, dict):
        return [{'layer': k, 'governance': v} for k, v in sorted(gov.items())]
    return [{'layer': None, 'governance': gov}]


def assert_no_postgame_inputs(stage: str, declared_inputs) -> Outcome:
    """A stage may not declare a postgame field as an input."""
    bad = sorted(set(declared_inputs) & POSTGAME_FIELDS)
    if bad:
        return Outcome.fail(
            'POSTGAME_INPUT_DECLARED',
            f'{stage} declares {bad} as inputs. Those exist only after the '
            f'game. A pipeline that reads them is not forecasting.',
            stage=stage, fields=bad)
    return Outcome.ok('INPUTS_ARE_PREGAME', value=sorted(declared_inputs))


class Pipeline:
    def __init__(self, run_id: str, out_dir: pathlib.Path, arm: str,
                 written_at: str):
        self.run_id = run_id
        self.out_dir = pathlib.Path(out_dir)
        self.arm = arm
        self.written_at = written_at
        self.results: list = []
        self.refusals: list = []
        self.halted_by = None
        self.started = time.time()
        # THE DAG IS PART OF THE RUN, not a side report. A stage that names a
        # node gets its identity computed here and its cache consulted here,
        # so "this stage was reused" is recorded in the same artifact as
        # "this stage ran" rather than in a log nobody keeps.
        self.dag = DAG()
        self.cache = NodeCache()
        self.node_records: list = []
        self.cut = None

    def run_stage(self, stage: str, fn: Callable, declared_inputs=(),
                  spec_version: str = None, node=None) -> StageResult:
        """Run one stage, or reuse it.

        `node` is OPTIONAL and additive. A stage that names a DerivedNode or
        ForecastNode gets content-addressed reuse: identity is
        H(spec_version, code_identity, sorted(input identities), fields), and
        an unchanged identity means the stage is not re-executed and the
        cached record keeps its ORIGINAL stamp. A stage that names no node
        behaves exactly as before, which is why wiring the DAG in did not
        require editing thirteen call sites.
        """
        if stage not in STAGES:
            raise ValueError(f'{stage!r} is not a declared pipeline stage')
        t0 = time.time()
        # HALT ON THE FIRST REFUSAL. A stage after a refusal must not run: the
        # pipeline previously recorded IDENTITY_UNRESOLVED and then went on to
        # execute the QB model on those unresolved players and SEAL an
        # artifact. The overall status was REFUSED, so nothing published -- but
        # modelling on inputs that failed validation, and sealing the result,
        # is exactly the 'prefer NO FORECAST over an unverifiable one' rule
        # being broken. Every stage still gets a record, so the stage count is
        # unchanged and the skip is visible rather than silent.
        if self.halted_by is not None:
            r = StageResult(
                stage=stage, state='NOT_APPLICABLE', code='STAGE_NOT_REACHED',
                detail=f'not run: the pipeline refused at '
                       f'{self.halted_by[0]} with {self.halted_by[1]}. '
                       f'Running a model on inputs that failed validation '
                       f'would produce a number nobody should read.',
                spec_version=spec_version)
            self.results.append(r)
            return r
        pg = assert_no_postgame_inputs(stage, declared_inputs)
        if pg.state is not State.PASS:
            r = StageResult(stage=stage, state='FAIL', code=pg.code,
                            detail=pg.detail, spec_version=spec_version,
                            elapsed_s=time.time() - t0)
            self.halted_by = (stage, r.code)
            self.results.append(r)
            return r
        if node is not None:
            try:
                if node.key not in self.dag.nodes:
                    self.dag.add(node)
                ident = self.dag.identity(node.key)
            except DagError as exc:
                r = StageResult(stage=stage, state='FAIL',
                                code=str(exc).split(':', 1)[0],
                                detail=str(exc), spec_version=spec_version,
                                elapsed_s=time.time() - t0)
                self.halted_by = (stage, r.code)
                self.results.append(r)
                return r
            hit = self.cache.get(node.key, ident)
            if hit is not None:
                # A CACHE HIT KEEPS ITS OWN CLOCK. `computed_at` is the stamp
                # from when the node was actually computed, never now.
                r = StageResult(
                    stage=stage, state='PASS', code='NODE_CACHE_HIT',
                    detail=f'{node.key} at {ident} was computed at '
                           f'{hit["computed_at"]} and is reused unchanged.',
                    spec_version=spec_version, elapsed_s=time.time() - t0,
                    metrics={'node_identity': ident,
                             'node_computed_at': hit['computed_at'],
                             'node_reused': True})
                self.node_records.append(dict(hit, stage=stage, reused=True))
                self.results.append(r)
                return r
        try:
            out = fn()
        except Exception as exc:                                  # noqa: BLE001
            r = StageResult(stage=stage, state='FAIL',
                            code='STAGE_RAISED',
                            detail=f'{type(exc).__name__}: {exc}',
                            spec_version=spec_version,
                            elapsed_s=time.time() - t0)
            self.halted_by = (stage, r.code)
            self.results.append(r)
            return r
        code = getattr(out, 'code', 'OK')
        st = getattr(out, 'state', None)
        state = st.value if st is not None else 'PASS'
        ev = getattr(out, 'evidence', {}) or {}
        r = StageResult(
            stage=stage, state=state, code=code,
            detail=(getattr(out, 'detail', '') or '')[:400],
            input_hashes=ev.get('input_hashes', {}),
            metrics={k: ev[k] for k in
                     ('draw_generation_seconds', 'n_qb_games', 'n_draws',
                      'draw_cells', 'qb_frame_sha256')
                     if ev.get(k) is not None},
            # THE STAGE'S OWN SPEC VERSION OUTRANKS THE CALLER'S LABEL.
            #
            # `spec_version` is a caller-supplied string, stored verbatim, and
            # for five stages the caller's string was a hand-typed paraphrase
            # of a constant the layer already publishes. `layers.SPEC` records
            # the appearance layer as `governance INFORMATION_CONSTRAINED`
            # while the call site passed the literal `'P3 appearance'`, so the
            # appearance layer's governance state reached neither the run
            # status nor the board. The caller's label is kept as the fallback
            # -- a stage that did not run has reported nothing, and a label is
            # better than a null there -- but where the stage answered for
            # itself, its answer is what is recorded.
            spec_version=(ev.get('spec_version') or spec_version),
            spec_versions=dict(ev.get('spec_versions') or {}),
            governance=_governance_records(ev),
            warnings=list(ev.get('warnings', [])),
            warnings_detail=list(ev.get('warnings_detail') or []),
            refusal_code=(code if state == 'BLOCKED' and code in RF.REFUSALS
                          else None),
            elapsed_s=time.time() - t0,
            value=getattr(out, 'value', None))
        if node is not None and r.state == 'PASS':
            stamp = _dt.datetime.now(_dt.timezone.utc).isoformat()
            put = self.cache.put(node.key, self.dag.identity(node.key),
                                 f'{self.run_id}.{node.key}', stamp)
            if put.state is not State.PASS:
                r = dataclasses.replace(r, state='FAIL', code=put.code,
                                        detail=put.detail)
            else:
                r.metrics['node_identity'] = self.dag.identity(node.key)
                r.metrics['node_computed_at'] = stamp
                r.metrics['node_reused'] = False
                self.node_records.append(dict(put.value, stage=stage,
                                              reused=False))
        if r.state in ('FAIL', 'BLOCKED'):
            self.halted_by = (stage, r.code)
        if r.refusal_code:
            self.refusals.append({'code': r.refusal_code, 'stage': stage,
                                  'detail': r.detail, 'run_id': self.run_id,
                                  'at': _dt.datetime.now(
                                      _dt.timezone.utc).isoformat()})
        self.results.append(r)
        return r

    def register_captures(self, src: dict, cut: str) -> Outcome:
        """Register the run's validated captures as DAG nodes. THE SLICE.

        `src` is what `capture_validation` already validated: one entry per
        source name carrying `sha256` and `retrieved_at`. That is exactly a
        `VintageNode`, so registering it needs no new plumbing and invents
        nothing -- every value comes from the capture the stage already
        checked.

        WHAT THIS DOES NOT DO, AND WHY IT IS DELIBERATE.

        The cut check below is RECORDED, NOT ENFORCED, in this slice, and the
        reason is a measured difference rather than caution. `_capture`
        refuses a source only when `retrieved_at > written_at`, so a capture
        retrieved at EXACTLY the write instant passes it.
        `bitemporal.readable_at` requires `learned_at < cut` STRICTLY, so the
        same capture fails here. The DAG is the stricter of the two, and the
        frequency of exact equality in real runs has not been measured.

        Promoting this to a halt is a production behaviour change on an
        untested boundary, and this project does not make two changes at once.
        The outcome is carried verbatim in `summary()['dag']['cut_check']`
        with its state, so a BLOCKED or FAIL is visible as itself and is not
        read as a pass. What would make it a halt: a measurement of how often
        `retrieved_at == written_at` occurs across sealed runs, and a decision
        on which of the two rules is correct.
        """
        for name, meta in (src or {}).items():
            sha = (meta or {}).get('sha256')
            got = (meta or {}).get('retrieved_at')
            if not sha or not got:
                # `_capture` already refuses this. Reaching it here means the
                # stage order changed, and a node built on a missing hash
                # would carry an identity that means nothing.
                return Outcome.fail(
                    'CAPTURE_NOT_NODEABLE',
                    f'{name} carries sha256={sha!r} retrieved_at={got!r}; a '
                    f'vintage node needs both.', source=name)
            if f'source:{name}' not in self.dag.nodes:
                self.dag.add(SourceNode(name))
            v = VintageNode(name, sha, got)
            if v.key not in self.dag.nodes:
                self.dag.add(v)
        self.cut = cut
        return Outcome.ok(
            'CAPTURES_REGISTERED',
            value=sorted(k for k in self.dag.nodes
                         if k.startswith('vintage:')),
            n_sources=len(src or {}))

    def cut_check(self) -> Optional[dict]:
        """The s.4 invariant over whatever forecast node the run registered."""
        cut = getattr(self, 'cut', None)
        fk = [k for k in self.dag.nodes if k.startswith('forecast:')]
        if cut is None or not fk:
            return None
        o = self.dag.assert_cut_lawful(sorted(fk)[0])
        return {'forecast_node': sorted(fk)[0], 'cut': cut,
                'state': o.state.value, 'code': o.code,
                'detail': o.detail[:400],
                'enforcement': 'OBSERVATIONAL_IN_THIS_SLICE',
                'why_not_enforced':
                    'bitemporal.readable_at requires learned_at < cut '
                    'strictly; capture_validation refuses only '
                    'retrieved_at > written_at. The DAG is stricter at exact '
                    'equality and that boundary has not been measured against '
                    'sealed runs.',
                'evidence': {k: v for k, v in (o.evidence or {}).items()
                             if k in ('offenders', 'n_vintages',
                                      'max_learned_at')}}

    def status(self) -> str:
        """STARTED / INPUT_VALIDATED / MODELED / RECONCILED / SEALED / REFUSED."""
        done = {r.stage for r in self.results if r.state == 'PASS'}
        if any(r.state in ('FAIL', 'BLOCKED') for r in self.results):
            return 'REFUSED'
        if 'artifact_sealing' in done:
            return 'SEALED'
        if 'joint_reconciliation' in done:
            return 'RECONCILED'
        if 'player_draws' in done or 'td_layer' in done:
            return 'MODELED'
        if 'capture_validation' in done:
            return 'INPUT_VALIDATED'
        return 'STARTED'

    def summary(self) -> dict:
        return {
            'run_id': self.run_id, 'arm': self.arm,
            'written_at': self.written_at,
            'pipeline_version': PIPELINE_VERSION,
            'status': self.status(),
            'elapsed_s': round(time.time() - self.started, 4),
            'stages': [r.as_dict() for r in self.results],
            'n_refusals': len(self.refusals),
            'refusals': self.refusals,
            'first_failure': next((r.as_dict() for r in self.results
                                   if r.state in ('FAIL', 'BLOCKED')), None),
            'dag': {
                'spec_version': DAG_SPEC_VERSION,
                'n_declared_edges': len(EDGES),
                'n_nodes': len(self.dag.nodes),
                'nodes': {k: self.dag.identity(k)
                          for k in sorted(self.dag.nodes)},
                'node_records': self.node_records,
                'cut_check': self.cut_check(),
            },
        }

    def persist(self) -> Outcome:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        (self.out_dir / 'run_status.json').write_text(
            json.dumps(self.summary(), indent=1, default=str) + '\n')
        RF.persist(self.refusals, self.out_dir)
        return Outcome.ok('RUN_PERSISTED', value=str(self.out_dir))


# =====================================================================
# P7 DEPENDENCY DAG -- PHASE 1, IMPLEMENTED HERE AND NOWHERE ELSE
# =====================================================================
#
# `nfl/research/v4/p7/P7_DEPENDENCY_DAG_SPEC.md` specified four node types,
# a declared-edge rule, a bitemporal reachability invariant, and a
# content-addressed identity. It specified Phase 1 -- "a module that states
# the edges, plus a test that walks the AST of every production module for
# direct glob/open against nfl/vintage and nfl_vintage/raw and fails on any
# read not declared as an edge" -- as the next piece of work, and said
# plainly that none of it was started.
#
# It is started here. It lives in this file rather than in a new package
# because this file is already the orchestrator, and a second orchestration
# surface beside it is the thing the DAG is supposed to prevent.
#
# WHAT IS IMPLEMENTED: the four node types, the declared edges with
# enumerated fields, the AST audit, node identity
# H(spec_version, code_identity, sorted(input identities), declared_fields),
# the two non-optional caching rules from spec s.5, and the s.4 reachability
# invariant.
#
# WHAT IS NOT: spec Phase 2. No consumer's glob has been rewritten to go
# through an accessor. Every read listed in `EDGES` still happens by globbing
# a directory; what has changed is that the read is now DECLARED, so an
# undeclared one fails a test. That is a bound on who reads what, not a
# capability gate. Do not read this section as "reads are now mediated".

DAG_SPEC_VERSION = 'p7-dependency-dag-phase1'

# Packages whose modules are audited for undeclared vintage reads. The
# acquisition layer is IN scope: `coverage.load_week_plan` is one of the four
# glob-shaped findings the spec said this test would catch, and it lives in
# nfl/capture. Leaving capture out would have let the audit claim four
# findings while covering two.
AUDITED_ROOTS = ('nfl/production/', 'nfl/product/', 'nfl/dfs/', 'nfl/capture/')

# The bytes this audit is about. `vintage_manifest` is not a capture source;
# it is the ledger over them, and a reader of it is a reader of the store.
VINTAGE_MARKERS = ('nflvintage', 'nfl_vintage', 'vintage_manifest')
MANIFEST_PRODUCER = 'vintage_manifest'

# Market columns carried by the `schedules` blob. They are not postgame --
# a closing line exists before kickoff -- so `POSTGAME_FIELDS` does not
# catch them, and the project's rule that market data may evaluate a forecast
# but never feed one has to be enforced against them separately.
MARKET_FIELDS = frozenset({
    'spread_line', 'total_line', 'away_moneyline', 'home_moneyline',
    'away_spread_odds', 'home_spread_odds', 'under_odds', 'over_odds',
})

# Column names on the `schedules` blob that are realised outcomes. They are
# spelled differently from `POSTGAME_FIELDS` -- `home_score`, not `score` --
# and a set that does not name them would let them through.
POSTGAME_COLUMNS = frozenset({
    'result', 'total', 'home_score', 'away_score', 'overtime',
})

READER_CALLS = frozenset({
    'glob', 'iglob', 'rglob', 'open', 'read_text', 'read_bytes',
    'read_csv', 'read_json',
})

# COMMAS BELONG IN THE NOISE CLASS. `os.path.join(_ROOT, 'nfl', 'vintage',
# 'weekly_rosters.*.reduced.csv.gz')` unparses with commas between the
# segments, so a noise class without `,` leaves `nfl,vintage`, which does not
# match the marker `nflvintage` -- and `rehearsal/run_slate.py` dropped out of
# the inventory silently. It was caught because `audit_declared_reads` reports
# a DECLARED EDGE THAT NOTHING EXERCISES, which is the only reason a detector
# false negative was visible at all.
_PATH_NOISE = _re.compile(r"['\"\s/\\*()\[\],]")
_IDENT = _re.compile(r'\b[A-Za-z_][A-Za-z_0-9]*\b')


# ---------------------------------------------------------------- nodes

@dataclasses.dataclass(frozen=True)
class SourceNode:
    """One entry in `registry.REGISTRY` or `registry.DELIVERED`.

    Has no inputs. Its identity is its name, because a source is a standing
    declaration rather than a computation: renaming it is a registry edit.
    """
    name: str

    @property
    def key(self) -> str:
        return f'source:{self.name}'

    def identity(self, _dag=None) -> str:
        return f'source:{self.name}'


@dataclasses.dataclass(frozen=True)
class VintageNode:
    """One `(source, content_sha256)` pair: specific bytes, first observed at
    `learned_at`.

    The same bytes seen twice are ONE vintage, not two. That is why identity
    is the content hash and not the capture event, and it is the property
    everything downstream has to agree on.
    """
    source: str
    content_sha256: str
    learned_at: str

    @property
    def key(self) -> str:
        return f'vintage:{self.source}:{self.content_sha256}'

    def identity(self, _dag=None) -> str:
        return f'vintage:{self.source}:{self.content_sha256}'


@dataclasses.dataclass(frozen=True)
class DerivedNode:
    """Anything computed from vintages and other derived nodes.

    `code_identity` is the identity of the FUNCTION that produced it, not of
    the repository. A repository-wide digest changes when an unrelated test
    is edited, which would invalidate every cached node on every commit and
    make the cache worthless -- and worse, would make "it recomputed" carry
    no information about what changed.
    """
    name: str
    spec_version: str
    code_identity: str
    inputs: tuple = ()
    declared_fields: tuple = ()

    @property
    def key(self) -> str:
        return f'derived:{self.name}'

    def identity(self, dag) -> str:
        return node_identity(self.spec_version, self.code_identity,
                             sorted(dag.identity(k) for k in self.inputs),
                             self.declared_fields)


@dataclasses.dataclass(frozen=True)
class ForecastNode:
    """One sealed board. Its distinguishing property is that it carries a CUT,
    and that cut is what every read beneath it is judged against."""
    name: str
    cut: str
    spec_version: str
    code_identity: str
    inputs: tuple = ()

    @property
    def key(self) -> str:
        return f'forecast:{self.name}'

    def identity(self, dag) -> str:
        return node_identity(self.spec_version, self.code_identity,
                             sorted(dag.identity(k) for k in self.inputs),
                             (f'cut={self.cut}',))


def node_identity(spec_version: str, code_identity: str,
                  input_identities, declared_fields) -> str:
    """H(spec_version, code_identity, sorted(input identities), fields).

    Spec s.5, and nothing more clever than that: not a staleness heuristic
    and not a timestamp comparison. The four components are length-prefixed
    before hashing so that no regrouping of them collides -- ('ab','c') and
    ('a','bc') are different inputs and must be different identities.
    """
    h = hashlib.sha256()
    for part in (spec_version, code_identity):
        b = str(part).encode()
        h.update(f'{len(b)}:'.encode() + b)
    for group in (sorted(input_identities), sorted(declared_fields)):
        h.update(f'n={len(group)};'.encode())
        for item in group:
            b = str(item).encode()
            h.update(f'{len(b)}:'.encode() + b)
    return 'nid:' + h.hexdigest()[:32]


def function_identity(fn) -> str:
    """The code identity of one function, from its own source text.

    REFUSES rather than guesses. A C builtin, a partial, or a function whose
    source file is gone has no recoverable text, and returning a name-based
    stand-in there would produce a node identity that does not change when
    the code changes -- a cache that serves stale bytes and says it is fresh.
    """
    try:
        src = _inspect.getsource(fn)
    except (OSError, TypeError) as exc:                        # noqa: BLE001
        raise ValueError(
            f'CODE_IDENTITY_UNAVAILABLE: no source text for '
            f'{getattr(fn, "__qualname__", fn)!r} ({type(exc).__name__}). A '
            f'node identity that cannot see the code cannot detect a change '
            f'in it.')
    mod = getattr(fn, '__module__', '?')
    qn = getattr(fn, '__qualname__', '?')
    return 'fn:' + hashlib.sha256(
        f'{mod}.{qn}\n{src}'.encode()).hexdigest()[:24]


# ---------------------------------------------------------------- edges

@dataclasses.dataclass(frozen=True)
class Edge:
    """A declared read: (consumer, producer, fields, why). Spec s.3.

    `fields` is mandatory and enumerated. Not "reads schedules" but "reads
    season, week, game_type, gameday, gametime, home_team, away_team". The
    schedules blob carries 46 columns including `result`, `home_score`,
    `spread_line` and `total_line`; today the guard against reading those is
    that nobody does, which is weaker than a bound.

    `kind` is COLUMNS or BLOB_SELECTION. A BLOB_SELECTION read chooses or
    orders files and projects no column, so an empty `fields` is the honest
    declaration for it and the only case where empty is legal.

    `basis` records HOW the field list was established: READ_BY_HAND means a
    person read the reader; LITERAL_SCAN means the list came from matching
    the module's string literals against the blob header, which is a
    SUPERSET and is labelled as one rather than presented as a measurement.
    """
    consumer: str
    producer: str
    fields: tuple
    why: str
    kind: str = 'COLUMNS'
    basis: str = 'READ_BY_HAND'


# THE DECLARED EDGE SET.
#
# Every entry corresponds to a read that exists in the tree today, found by
# `audit_declared_reads` rather than recalled. Adding a reader means adding a
# line here; that is the whole mechanism.
EDGES = (
    # --- schedules. The leak surface, and the reason `fields` is mandatory.
    Edge('nfl/capture/coverage.py', 'schedules',
         ('season', 'week', 'game_type', 'gameday', 'gametime',
          'home_team', 'away_team'),
         'the week capture plan: which games exist and when they kick off. '
         'A kickoff time is scheduled months ahead and is not an outcome. '
         'The same blob carries result, home_score, spread_line and '
         'total_line and this reader takes none of them.'),
    Edge('nfl/capture/coverage.py', 'schedules', (),
         'orders schedule blobs by manifest transaction time to pick the '
         'newest lawful one; projects no column.',
         kind='BLOB_SELECTION'),
    Edge('nfl/production/team_volume_v1.py', 'schedules',
         ('season', 'week', 'game_type',
          'home_team', 'away_team', 'home_coach', 'away_coach'),
         'coach_prior is the selected estimator for three of five volume '
         'metrics, so the head coach per team is a prediction-time input. '
         'home_coach/away_coach are reached through an f-string, which is '
         'why a literal scan missed them and a person had to read it.'),

    # --- depth_charts
    Edge('nfl/production/nonqb/qb_allocation.py', 'depth_charts',
         ('dt', 'team', 'gsis_id', 'pos_abb', 'pos_rank'),
         'QB room ordering at a cut. This is the `captured_depth_chart` call '
         'the spec named as an undeclared glob; it is now declared.'),
    Edge('nfl/production/nonqb/depth_vintage.py', 'depth_charts',
         ('dt', 'team', 'gsis_id', 'pos_abb', 'pos_rank', 'pos_slot'),
         'point-in-time depth selection. pos_slot is the vendor tiebreak '
         'within pos_abb and exists only on the raw blob.'),

    # --- weekly_rosters
    Edge('nfl/production/nonqb/roster_status.py', 'weekly_rosters',
         ('season', 'week', 'team', 'gsis_id', 'status'),
         'roster membership at a cut. The reduced vintage drops `status`, so '
         'the retained raw files under nfl_vintage/raw are the only source.'),
    Edge('nfl/production/nonqb/participant_class.py', 'weekly_rosters',
         ('season', 'week', 'team', 'gsis_id', 'position', 'status'),
         'maps a roster status code to one participation class.'),
    Edge('nfl/production/nonqb/current_season_panel.py', 'weekly_rosters',
         ('season', 'week', 'team', 'gsis_id', 'position', 'full_name',
          'pfr_id'),
         'current-season non-QB usage panel membership.',
         basis='LITERAL_SCAN'),
    Edge('nfl/production/nonqb/appearance_panel_2026.py', 'weekly_rosters',
         ('season', 'week', 'team', 'gsis_id', 'position', 'full_name',
          'pfr_id'),
         'appearance panel membership.', basis='LITERAL_SCAN'),
    Edge('nfl/production/nonqb/panel_2026w1.py', 'weekly_rosters',
         ('season', 'week', 'team', 'gsis_id', 'position', 'full_name',
          'pfr_id'),
         'week-1 cold-start panel membership.', basis='LITERAL_SCAN'),
    Edge('nfl/production/nonqb/rushing_conversion.py', 'weekly_rosters',
         ('season', 'week', 'gsis_id', 'position'),
         'position attach for the rushing conversion frame.',
         basis='LITERAL_SCAN'),
    Edge('nfl/production/kicking.py', 'weekly_rosters',
         ('season', 'week', 'team', 'gsis_id', 'position', 'full_name',
          'status'),
         'the kicker of record per club. Player-keyed, never (team, '
         'position): that substitution is what OUT-023 was about.',
         basis='LITERAL_SCAN'),
    Edge('nfl/product/daily_board.py', 'weekly_rosters',
         ('team', 'gsis_id', 'full_name', 'football_name', 'status'),
         'board display identity.', basis='LITERAL_SCAN'),
    Edge('nfl/dfs/showdown/kicker_identity.py', 'weekly_rosters',
         ('team', 'gsis_id', 'full_name', 'position'),
         'resolves a kicking-layer row id to a named player, so a DFS '
         'entrant is keyed by player and not by (team, position).'),

    # --- espn_injuries_json (a JSON document, so `fields` are dotted paths)
    Edge('nfl/production/nonqb/availability_feed.py', 'espn_injuries_json',
         ('timestamp', 'injuries[].displayName',
          'injuries[].injuries[].athlete.displayName',
          'injuries[].injuries[].athlete.position.abbreviation',
          'injuries[].injuries[].status',
          'injuries[].injuries[].date',
          'injuries[].injuries[].shortComment'),
         'designation text per player at a cut, kept verbatim.'),

    # --- the manifest itself
    Edge('nfl/capture/bitemporal.py', MANIFEST_PRODUCER,
         ('source', 'blob', 'content_sha256', 'retrieved_at',
          'effective_scope'),
         'builds the Fact list every cut check is judged on.'),
    Edge('nfl/capture/live_game_evidence.py', MANIFEST_PRODUCER,
         ('source', 'blob', 'retrieved_at'),
         'locates the evidence blob for a live game.'),
    Edge('nfl/production/eligibility_gate.py', MANIFEST_PRODUCER,
         ('source', 'blob', 'content_sha256', 'retrieved_at'),
         'stamps the vintage of each gating input onto the gate record.'),
    Edge('nfl/production/nonqb/inputs.py', MANIFEST_PRODUCER,
         ('source', 'blob', 'content_sha256', 'retrieved_at'),
         'resolves which captured bytes a non-QB layer ran on.'),
    Edge('nfl/production/nonqb/qb_allocation.py', MANIFEST_PRODUCER,
         ('source', 'blob', 'content_sha256', 'retrieved_at'),
         'clocks the depth-chart blobs it selects among.'),
    Edge('nfl/production/nonqb/vintage_selector.py', MANIFEST_PRODUCER,
         ('source', 'blob', 'content_sha256', 'retrieved_at',
          'effective_scope'),
         'the sanctioned point-in-time selector. It is a declared reader '
         'like any other; being the intended channel does not exempt it.'),

    # --- whole-blob reads that project nothing
    Edge('nfl/production/nonqb/vintage_selector.py', 'weekly_rosters', (),
         'joins retained raw files to the manifest by content hash.',
         kind='BLOB_SELECTION'),
    Edge('nfl/production/nonqb/vintage_selector.py', 'depth_charts', (),
         'joins retained raw files to the manifest by content hash.',
         kind='BLOB_SELECTION'),
    Edge('nfl/production/nonqb/vintage_selector.py', 'schedules', (),
         'joins retained raw files to the manifest by content hash.',
         kind='BLOB_SELECTION'),
    Edge('nfl/production/nonqb/vintage_selector.py', 'injuries', (),
         'joins retained raw files to the manifest by content hash.',
         kind='BLOB_SELECTION'),
    Edge('nfl/production/nonqb/availability_feed.py', 'injuries', (),
         'the espn glob pattern also matches the `injuries` family name; '
         'declared so the audit is not satisfied by a coincidence.',
         kind='BLOB_SELECTION'),

    # --- a rehearsal path, declared because it reads the same store
    Edge('nfl/production/rehearsal/run_slate.py', 'weekly_rosters',
         ('season', 'week', 'team', 'gsis_id', 'position'),
         'rehearsal slate membership from the reduced vintage.',
         basis='LITERAL_SCAN'),
)

@dataclasses.dataclass(frozen=True)
class RuntimeKeyedRead:
    """A read whose FILE NAME is only known at run time.

    Three of these exist. Each takes its path from a manifest row or from
    bytes already in hand, so no static expression names a source family and
    an `Edge` would be a fiction: the producer would have to be `*any*`,
    which is not a bound.

    They are declared here instead, by (module, function), with what actually
    bounds each one. The audit reports them under their own code and will
    still FAIL on a NEW unattributable read, including one in a neighbouring
    function of a module that appears below -- which is why the key is the
    function and not the module.
    """
    module: str
    function: str
    why: str
    bounded_by: str


RUNTIME_KEYED_READS = (
    RuntimeKeyedRead(
        'nfl/capture/coverage.py', '_has_declared_rows',
        'substring-checks a captured blob for the team codes a manifest row '
        'claims it covers, so a row cannot assert coverage the bytes do not '
        'carry.',
        'the path is the `blob` field of the manifest row being checked, so '
        'the reachable set is the manifest\'s own. No CSV is parsed and no '
        'column is projected: the read is a lowercase substring test.'),
    RuntimeKeyedRead(
        'nfl/capture/delivered_injuries.py', 'store_raw',
        'reads back the blob it has just written and refuses if the gzip '
        'round-trip does not hash to the same sha256.',
        'the path is the file this call created from bytes already in hand. '
        'NOTE, and it is a finding of this audit rather than a repair: the '
        '`delivered_injury_evidence` blob family is in nfl/vintage/ and is in '
        'neither registry.REGISTRY nor registry.DELIVERED, so no source name '
        'exists to declare an edge to. Naming it is a capture-layer change '
        'and is not made here.'),
    RuntimeKeyedRead(
        'nfl/capture/persisted_provenance.py', 'attempt_recovery',
        're-derives the content hash of a retained raw file to recover the '
        'provenance of a manifest row whose blob is missing.',
        'both the source name and the content hash in the path come from the '
        'manifest row being recovered, and the recovered hash is compared '
        'back against that row.'),
)


# Reads that are WRITES into the store. The capture layer writes the vintage
# directory and its manifest; that is its job and it is not a consumer edge.
# They are listed so the audit reports them rather than silently dropping
# them -- a write site that quietly disappeared from the inventory is how a
# reader later hides as a writer.
DECLARED_WRITERS = (
    'nfl/production/nonqb/inactives.py',
    'nfl/capture/delivered_injuries.py',
)


def edge_index(edges=EDGES) -> dict:
    out: dict = {}
    for e in edges:
        out.setdefault(e.consumer, set()).add(e.producer)
    return out


def assert_edge_fields_are_pregame(edge: Edge) -> Outcome:
    """A declared field may be neither a realised outcome nor a market price.

    Two rules, one check, and they fail with different codes because they are
    different rules. POSTGAME_FIELDS is the pipeline's existing set;
    POSTGAME_COLUMNS adds the schedules blob's own spellings. MARKET_FIELDS
    is separate because a closing line is not postgame -- it exists before
    kickoff -- so a postgame check alone would pass it.
    """
    f = set(edge.fields)
    bad = sorted(f & (POSTGAME_FIELDS | POSTGAME_COLUMNS))
    if bad:
        return Outcome.fail(
            'EDGE_DECLARES_POSTGAME_FIELD',
            f'{edge.consumer} declares {bad} from {edge.producer}. Those '
            f'exist only after the game.',
            consumer=edge.consumer, producer=edge.producer, fields=bad)
    mk = sorted(f & MARKET_FIELDS)
    if mk:
        return Outcome.fail(
            'EDGE_DECLARES_MARKET_FIELD',
            f'{edge.consumer} declares {mk} from {edge.producer}. Market '
            f'data may evaluate a forecast and may never feed one.',
            consumer=edge.consumer, producer=edge.producer, fields=mk)
    if edge.kind == 'COLUMNS' and not edge.fields:
        return Outcome.fail(
            'EDGE_FIELDS_NOT_ENUMERATED',
            f'{edge.consumer} -> {edge.producer} declares no field. "Reads '
            f'schedules" is not a bound. Declare the columns, or declare '
            f'kind=BLOB_SELECTION and say why nothing is projected.',
            consumer=edge.consumer, producer=edge.producer)
    if edge.kind not in ('COLUMNS', 'BLOB_SELECTION'):
        return Outcome.fail(
            'EDGE_KIND_UNKNOWN', f'{edge.kind!r} is not an edge kind',
            consumer=edge.consumer)
    if not (edge.why or '').strip():
        return Outcome.fail(
            'EDGE_WHY_MISSING',
            f'{edge.consumer} -> {edge.producer} declares no reason.',
            consumer=edge.consumer)
    return Outcome.ok('EDGE_FIELDS_PREGAME', value=sorted(f))


def assert_edges_declarable(edges=EDGES) -> Outcome:
    bad = []
    for e in edges:
        o = assert_edge_fields_are_pregame(e)
        if o.state is not State.PASS:
            bad.append({'consumer': e.consumer, 'producer': e.producer,
                        'code': o.code, 'detail': o.detail})
    if bad:
        return Outcome.fail('EDGE_DECLARATION_INVALID',
                            f'{len(bad)} edge(s) declare a field they may '
                            f'not read', offenders=bad)
    return Outcome.ok('EDGES_DECLARABLE', value=len(edges))


# ------------------------------------------------- the AST read audit

def _path_expression(call: _ast.Call) -> str:
    """The path expression of a reader call, receiver included.

    `VINTAGE.glob(pat)` puts the directory in the RECEIVER and the pattern in
    the argument, so an argument-only reading of the call sees `'*.csv.gz'`
    and concludes nothing about the store. Both halves are needed.
    """
    parts = []
    if isinstance(call.func, _ast.Attribute):
        parts.append(_ast.unparse(call.func.value))
    for a in call.args:
        parts.append(_ast.unparse(a))
    for kw in call.keywords:
        if kw.arg in (None, 'file', 'path', 'pathname', 'filepath_or_buffer'):
            parts.append(_ast.unparse(kw.value))
    return ' '.join(parts)


def _assignments(nodes) -> dict:
    out: dict = {}
    for root in nodes:
        for n in _ast.walk(root):
            if isinstance(n, _ast.Assign):
                try:
                    v = _ast.unparse(n.value)
                except Exception:                              # noqa: BLE001
                    continue
                for t in n.targets:
                    if isinstance(t, _ast.Name):
                        out[t.id] = v
    return out


def _module_constants(tree: _ast.AST) -> dict:
    """Name -> source text, for every MODULE-LEVEL assignment.

    Function-local assignments are deliberately excluded here and added back
    per function by `_scopes`. A first version collected every assignment
    anywhere in the module, and a local `p = VINTAGE / name` in one function
    then made an unrelated `open(p)` in another function look like a vintage
    read. One such false positive would have been argued away and the audit
    with it.
    """
    return _assignments([n for n in tree.body])


def _scopes(tree: _ast.AST):
    """(enclosing_function_name, node_to_walk, constants_in_scope) per scope.

    A reader call is attributed to the innermost function containing it, and
    resolves names against module-level constants plus that function's own
    locals. `RUNTIME_KEYED_READS` is keyed on that function name, so a new
    unattributable read in a declared function's NEIGHBOUR still fails.
    """
    mod_consts = _module_constants(tree)
    fns = [n for n in _ast.walk(tree)
           if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))]
    inner = {}
    for f in fns:
        for n in _ast.walk(f):
            if isinstance(n, _ast.Call):
                prior = inner.get(id(n))
                if prior is None or (f.end_lineno - f.lineno) < (
                        prior[0].end_lineno - prior[0].lineno):
                    scope = dict(mod_consts, **_assignments([f]))
                    # A PARAMETER IS NOT A CONSTANT. `_sha256_file(p)` takes
                    # `p` from its caller, and expanding that `p` against an
                    # unrelated module-level `p` attributed the read to the
                    # manifest -- a confident answer to a question the code
                    # does not answer statically.
                    for a in _params(f):
                        scope.pop(a, None)
                    inner[id(n)] = (f, scope)
    return mod_consts, inner


def _params(f) -> tuple:
    a = f.args
    names = [x.arg for x in (list(a.posonlyargs) + list(a.args)
                             + list(a.kwonlyargs))]
    for extra in (a.vararg, a.kwarg):
        if extra is not None:
            names.append(extra.arg)
    return tuple(names)


def _expand(expr: str, consts: dict, rounds: int = 4) -> str:
    for _ in range(rounds):
        new = _IDENT.sub(
            lambda m: consts.get(m.group(0), m.group(0))
            if consts.get(m.group(0), m.group(0)) != m.group(0)
            else m.group(0), expr)
        if new == expr:
            break
        expr = new
    return expr


def _pattern_sources(call: _ast.Call, consts: dict, names) -> tuple:
    """Source families named by a glob pattern, whatever the path root is.

    The store's blob convention is `<source>.<content_sha16>.<kind>.<ext>`,
    so a pattern beginning `weekly_rosters.` names that family and nothing
    else. Matching on the pattern rather than the root is what lets the audit
    see a read whose directory arrived as a function argument.
    """
    lits = []
    for arg in list(call.args) + [k.value for k in call.keywords]:
        # WALK THE ARGUMENT, do not merely test it. The pattern is often
        # buried in an `os.path.join(...)` or an f-string rather than sitting
        # bare in the call.
        for a in _ast.walk(arg):
            if isinstance(a, _ast.Constant) and isinstance(a.value, str):
                lits.append(a.value)
            elif isinstance(a, _ast.Name) and a.id in consts:
                lits.append(consts[a.id].strip('\'"'))
    out = []
    for lit in lits:
        base = lit.rsplit('/', 1)[-1]
        for s in names:
            if base.startswith(s + '.'):
                out.append(s)
    return tuple(sorted(set(out)))


def _is_write(call: _ast.Call) -> bool:
    if not (isinstance(call.func, _ast.Name) and call.func.id == 'open') and \
       not (isinstance(call.func, _ast.Attribute) and call.func.attr == 'open'):
        return False
    mode = None
    if len(call.args) > 1 and isinstance(call.args[1], _ast.Constant):
        mode = call.args[1].value
    for kw in call.keywords:
        if kw.arg == 'mode' and isinstance(kw.value, _ast.Constant):
            mode = kw.value.value
    return bool(isinstance(mode, str) and mode and mode[0] in 'wax')


def _source_names() -> tuple:
    from nfl.capture import registry as _REG
    return tuple(sorted(set(_REG.BY_NAME) | set(_REG.DELIVERED_BY_NAME)))


def scan_vintage_reads(repo=None, roots=AUDITED_ROOTS) -> list:
    """Every direct read of the vintage store in the audited packages.

    Walks the AST, not the text: a grep for `nfl/vintage` finds a prose
    docstring and misses `VINTAGE.glob(...)`, and both of those errors have
    already happened in this repository.
    """
    repo = pathlib.Path(repo or _REPO)
    names = _source_names()
    sites = []
    for root in roots:
        for p in sorted(repo.glob(root + '**/*.py')):
            rel = str(p.relative_to(repo))
            try:
                tree = _ast.parse(p.read_text())
            except SyntaxError as exc:
                sites.append({'module': rel, 'line': getattr(exc, 'lineno', 0),
                              'call': 'SYNTAX_ERROR', 'kind': 'UNPARSEABLE',
                              'sources': [], 'expr': str(exc)})
                continue
            mod_consts, inner = _scopes(tree)
            for n in _ast.walk(tree):
                if not isinstance(n, _ast.Call):
                    continue
                f = n.func
                nm = (f.attr if isinstance(f, _ast.Attribute)
                      else f.id if isinstance(f, _ast.Name) else None)
                if nm not in READER_CALLS:
                    continue
                fn_node, consts = inner.get(id(n), (None, mod_consts))
                expr = _PATH_NOISE.sub(
                    '', _expand(_path_expression(n), consts))
                # TWO DETECTION CHANNELS, because one is not enough.
                #
                # (1) the path expression names the store. Misses a read
                #     rooted on a PARAMETER -- `_schedule_snapshots(
                #     vintage_dir).glob('schedules.*.csv.gz')` -- and that
                #     read is `coverage.load_week_plan`, one of the four
                #     findings this audit exists to catch.
                # (2) the glob PATTERN matches the store's blob naming
                #     convention, `<source>.<sha16>.<kind>.<ext>`. That names
                #     the family whatever the root is.
                by_pattern = _pattern_sources(n, consts, names)
                if not any(m in expr for m in VINTAGE_MARKERS) \
                        and not by_pattern:
                    continue
                srcs = [s for s in names if s in expr] + list(by_pattern)
                if 'vintage_manifest' in expr:
                    srcs = srcs + [MANIFEST_PRODUCER]
                sites.append({
                    'module': rel, 'line': n.lineno, 'call': nm,
                    'function': getattr(fn_node, 'name', '<module>'),
                    'kind': 'WRITE' if _is_write(n) else 'READ',
                    'sources': sorted(set(srcs)), 'expr': expr[:160]})
    return sites


def audit_declared_reads(repo=None, roots=AUDITED_ROOTS,
                         edges=EDGES) -> Outcome:
    """Spec s.6 Phase 1: no read of the vintage store without a declared edge.

    Three failure shapes, each with its own code, because collapsing them
    would let the weakest one hide inside the strongest:

      UNDECLARED_VINTAGE_READ      -- a module reads a source it never declared.
      VINTAGE_READ_SOURCE_UNKNOWN  -- a read whose path names no known source.
                                      Not excused: an unattributable read is
                                      the one you cannot bound at all.
      EDGE_DECLARES_NO_READ        -- a declared edge no consumer performs.
                                      Reported, and NOT a failure: a consumer
                                      may have been repaired to route through
                                      `vintage_selector`, and a stale edge is
                                      a tidiness problem, not a leak.
    """
    decl = assert_edges_declarable(edges)
    if decl.state is not State.PASS:
        return decl
    idx = edge_index(edges)
    rk = {(r.module, r.function) for r in RUNTIME_KEYED_READS}
    sites = scan_vintage_reads(repo=repo, roots=roots)
    undeclared, unknown, exercised = [], [], set()
    runtime_keyed = []
    for s in sites:
        if s['kind'] == 'WRITE':
            continue
        if s['kind'] == 'UNPARSEABLE':
            unknown.append(s)
            continue
        if not s['sources']:
            if (s['module'], s['function']) in rk:
                runtime_keyed.append(s)
            else:
                unknown.append(s)
            continue
        have = idx.get(s['module'], set())
        for src in s['sources']:
            if src in have:
                exercised.add((s['module'], src))
            else:
                undeclared.append({'module': s['module'], 'line': s['line'],
                                   'producer': src, 'expr': s['expr']})
    stale = sorted({(e.consumer, e.producer) for e in edges} - exercised)
    if undeclared or unknown:
        return Outcome.fail(
            'UNDECLARED_VINTAGE_READ' if undeclared
            else 'VINTAGE_READ_SOURCE_UNKNOWN',
            f'{len(undeclared)} undeclared read(s) and {len(unknown)} '
            f'unattributable read(s) of the vintage store. A consumer that is '
            f'not in the DAG may not take bytes: adding a reader is a '
            f'declaration, not a glob.',
            undeclared=undeclared, unattributable=unknown,
            runtime_keyed=runtime_keyed, n_sites=len(sites))
    return Outcome.ok(
        'EVERY_VINTAGE_READ_DECLARED',
        value={'n_sites': len(sites),
               'n_reads': sum(1 for s in sites if s['kind'] == 'READ'),
               'n_writes': sum(1 for s in sites if s['kind'] == 'WRITE'),
               'n_edges': len(edges),
               'n_runtime_keyed': len(runtime_keyed),
               'runtime_keyed': [
                   {'module': x['module'], 'function': x['function'],
                    'line': x['line']} for x in runtime_keyed],
               'edges_not_exercised': [list(x) for x in stale]},
        detail=f'{len(sites)} vintage read/write site(s) in '
               f'{len(roots)} package(s); every read declared.')


# ------------------------------------------------------------ the DAG

class DagError(RuntimeError):
    pass


class DAG:
    """The declared graph, plus identity and reachability over it.

    Holds nodes by key. A node may be added twice only if it is identical;
    two different definitions of one key is the defect the DAG exists to
    make impossible, not something to resolve by last-write-wins.
    """

    def __init__(self, edges=EDGES):
        self.edges = tuple(edges)
        self.nodes: dict = {}
        self._identity: dict = {}

    def add(self, node):
        k = node.key
        prior = self.nodes.get(k)
        if prior is not None and prior != node:
            raise DagError(
                f'NODE_KEY_REDEFINED: {k} is already defined as {prior!r} '
                f'and cannot be redefined as {node!r}. Two definitions of one '
                f'node is not a merge, it is an ambiguity.')
        for i in getattr(node, 'inputs', ()):
            if i not in self.nodes:
                raise DagError(
                    f'NODE_INPUT_UNKNOWN: {k} declares input {i!r}, which is '
                    f'not in the graph. An input added later would change '
                    f'this node\'s identity after it was computed.')
        self.nodes[k] = node
        self._identity.clear()
        return node

    def identity(self, key: str) -> str:
        if key in self._identity:
            return self._identity[key]
        node = self.nodes.get(key)
        if node is None:
            raise DagError(f'NODE_UNKNOWN: {key!r}')
        v = node.identity(self)
        self._identity[key] = v
        return v

    def consumers_of(self, key: str) -> tuple:
        return tuple(sorted(
            k for k, n in self.nodes.items()
            if key in getattr(n, 'inputs', ())))

    def invalidated_by(self, changed) -> frozenset:
        """The downstream closure of a set of changed nodes, changed included.

        This is the question the DAG exists to answer: an inactives change
        must invalidate the nodes that read inactives and nothing else. A
        timestamp sweep answers it by invalidating everything.
        """
        out, stack = set(), list(changed)
        while stack:
            k = stack.pop()
            if k in out:
                continue
            out.add(k)
            stack.extend(self.consumers_of(k))
        return frozenset(out)

    def reachable_vintages(self, key: str) -> tuple:
        """Every VintageNode beneath a node. Spec s.4's missing half.

        `bitemporal.assert_forecast_reads_only_learned_before_cut` already
        checks a FLAT LIST of facts. What it lacks is the reachability --
        the caller has to know which facts to hand it, which is exactly the
        knowledge the DAG holds and nothing else did.
        """
        seen, out, stack = set(), [], [key]
        while stack:
            k = stack.pop()
            if k in seen:
                continue
            seen.add(k)
            n = self.nodes.get(k)
            if n is None:
                raise DagError(f'NODE_UNKNOWN: {k!r}')
            if isinstance(n, VintageNode):
                out.append(n)
            stack.extend(getattr(n, 'inputs', ()))
        return tuple(sorted(out, key=lambda v: (v.source, v.content_sha256)))

    def max_learned_at(self, key: str):
        """A derived node inherits the transaction time of the LATEST vintage
        beneath it, not of the run that reads it. Spec s.4, second clause --
        the one that is easy to lose. A panel built on Monday from a
        Sunday-evening capture is not lawful for a Sunday-afternoon forecast,
        however old the forecast thinks the panel is."""
        vs = self.reachable_vintages(key)
        return max((v.learned_at for v in vs), default=None)

    def assert_cut_lawful(self, forecast_key: str) -> Outcome:
        """Spec s.4: every vintage reachable from F has learned_at < cut(F)."""
        f = self.nodes.get(forecast_key)
        if not isinstance(f, ForecastNode):
            return Outcome.fail('NOT_A_FORECAST_NODE',
                                f'{forecast_key!r} carries no cut')
        from nfl.capture import bitemporal as _BT
        vs = self.reachable_vintages(forecast_key)
        if not vs:
            return Outcome.fail(
                'FORECAST_READS_NO_VINTAGE',
                f'{forecast_key} reaches no captured bytes. A forecast with '
                f'no input is not a lawful forecast, it is a constant.')
        bad = []
        for v in vs:
            # `subject` is what the fact is ABOUT. A VintageNode is one set
            # of bytes, so its subject is the content hash and nothing is
            # invented to fill the field.
            fact = _BT.Fact(subject=v.content_sha256, source=v.source,
                            content_sha256=v.content_sha256,
                            learned_at=v.learned_at)
            o = _BT.readable_at(fact, f.cut)
            if o.state is not State.PASS:
                bad.append({'source': v.source,
                            'content_sha256': v.content_sha256,
                            'learned_at': v.learned_at, 'code': o.code})
        if bad:
            return Outcome.fail(
                'FORECAST_READS_AFTER_CUT',
                f'{len(bad)} of {len(vs)} vintage(s) reachable from '
                f'{forecast_key} were learned at or after the cut {f.cut}.',
                offenders=bad, cut=f.cut)
        return Outcome.ok('FORECAST_CUT_LAWFUL',
                          value={'n_vintages': len(vs),
                                 'max_learned_at': self.max_learned_at(
                                     forecast_key), 'cut': f.cut})


# ------------------------------------------------------- the node cache

class NodeCache:
    """Content-addressed reuse, with spec s.5's two non-optional rules.

    Rule 1: a recomputation that changes a node's identity may not reuse the
    old artifact's name. Superseding in place is how a reader ends up unable
    to say which bytes produced a number.

    Rule 2: a cache hit may not be restamped. `availability.py` already has a
    test for this exact failure (test_f3_cache_hit_does_not_restamp),
    inherited from the V7 weather defect where one clock was substituted for
    another and a stale artifact was certified as fresh.
    """

    def __init__(self):
        self.by_identity: dict = {}
        self.by_name: dict = {}

    def get(self, key: str, identity: str):
        """The stored record, WITH ITS ORIGINAL STAMP, or None."""
        return self.by_identity.get((key, identity))

    def put(self, key: str, identity: str, artifact_name: str,
            computed_at: str) -> Outcome:
        prior_name = self.by_name.get(artifact_name)
        if prior_name is not None and prior_name != identity:
            return Outcome.fail(
                'RECOMPUTED_NODE_REUSED_ARTIFACT_NAME',
                f'{artifact_name!r} already holds identity {prior_name} and '
                f'may not be overwritten with {identity}. A recomputation '
                f'that changes identity gets a new name.',
                artifact=artifact_name, had=prior_name, got=identity)
        hit = self.by_identity.get((key, identity))
        if hit is not None:
            if hit['computed_at'] != computed_at:
                return Outcome.fail(
                    'CACHE_HIT_RESTAMPED',
                    f'{key} at {identity} was computed at '
                    f'{hit["computed_at"]} and a write is trying to stamp it '
                    f'{computed_at}. A cache hit keeps its own clock.',
                    had=hit['computed_at'], got=computed_at)
            return Outcome.ok('NODE_CACHED_ALREADY', value=hit)
        rec = {'key': key, 'identity': identity, 'artifact': artifact_name,
               'computed_at': computed_at}
        self.by_identity[(key, identity)] = rec
        self.by_name[artifact_name] = identity
        return Outcome.ok('NODE_CACHED', value=rec)


# ------------------------------------------------------ the read inventory

READ_INVENTORY = _REPO / 'nfl' / 'research' / 'v4' / 'p7' / \
    'P7_DECLARED_READS.json'


def read_inventory(repo=None) -> dict:
    """The artifact that answers "who reads depth_charts?" without a grep.

    Generated, never hand-written:

        python3.12 nfl/production/pipeline.py --write-read-inventory

    `test_p7_dag` compares it against a live audit, so a stale copy fails
    rather than quietly describing a tree that no longer exists.
    """
    o = audit_declared_reads(repo=repo)
    by_producer: dict = {}
    for e in EDGES:
        by_producer.setdefault(e.producer, []).append(
            {'consumer': e.consumer, 'kind': e.kind, 'basis': e.basis,
             'fields': list(e.fields), 'why': e.why})
    return {
        'spec_version': DAG_SPEC_VERSION,
        'spec': 'nfl/research/v4/p7/P7_DEPENDENCY_DAG_SPEC.md',
        'phase': 'PHASE_1_DECLARATION_ONLY',
        'not_implemented': [
            'PHASE_2: a read(node, cut) accessor. Every read below still '
            'happens by globbing a directory; the declaration bounds who '
            'reads what, it does not mediate the bytes.',
            'PHASE_3: content-addressed recomputation ACROSS RUNS. The '
            'identity algebra and the cache exist and are exercised inside a '
            'run; nothing is persisted between runs yet.',
        ],
        'audited_roots': list(AUDITED_ROOTS),
        'audit': {'state': o.state.value, 'code': o.code,
                  'value': o.value if o.state is State.PASS else None,
                  'evidence': {k: v for k, v in (o.evidence or {}).items()
                               if k in ('undeclared', 'unattributable')}},
        'by_producer': {k: sorted(v, key=lambda r: (r['consumer'], r['kind']))
                        for k, v in sorted(by_producer.items())},
        'runtime_keyed_reads': [dataclasses.asdict(r)
                                for r in RUNTIME_KEYED_READS],
        'declared_writers': list(DECLARED_WRITERS),
    }


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--audit-reads', action='store_true')
    ap.add_argument('--write-read-inventory', action='store_true')
    a = ap.parse_args()
    if a.audit_reads or a.write_read_inventory:
        out = read_inventory()
        if a.write_read_inventory:
            READ_INVENTORY.parent.mkdir(parents=True, exist_ok=True)
            READ_INVENTORY.write_text(
                json.dumps(out, indent=1, sort_keys=True) + '\n')
            print(f'wrote {READ_INVENTORY}')
        print(f"{out['audit']['state']} {out['audit']['code']}")
        sys.exit(0 if out['audit']['state'] == 'PASS' else 1)
    ap.print_help()
