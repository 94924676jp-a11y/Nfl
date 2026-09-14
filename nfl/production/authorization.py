"""The publication gate. NFL-1 must be explicitly authorized by the owner.

THERE IS NO PATH FROM A GREEN TEST SUITE TO AUTHORIZATION. The guard reads the
structured gate state and an owner authorization record, and refuses anything
else -- a passing suite, a discharged checklist, an environment variable, a
caller-supplied flag.

WHAT CHANGED, AND WHY IT HAD TO
===============================
`may_publish()` took ZERO ARGUMENTS. It read one board-wide gate and returned
one board-wide answer, so it could not refuse THIS board for THIS board's
defects and it could not make a METRIC-SPECIFIC decision. Every governance
fact the system transports -- the layer warnings and governance tokens WS-D
repaired into `run_status.json`, the hard-invariant verdicts
`draw_coherence` computes on the published draws, the clocked chronology
verdicts, the eligibility matrix, completeness, model health -- arrived
somewhere that could do nothing with them.

This module now takes a `PublicationContext`: run identity, metric, layer,
candidate configuration, chronology, eligibility, hard invariants, warnings,
governance state, composed spec version, completeness, model health, the
TEST_ONLY quarantine flag and whether the run was a dry run.
`may_publish(ctx)` evaluates one DECLARED RULE AT A TIME against those facts
and composes the answers worst-first.

NO FIELD HAS A DEFAULT and `context()` refuses an omitted one, because the
defect being repaired is a decision taken without the facts and a default is
how a missing fact becomes a clean one.

WHAT THIS MODULE DOES NOT DO, STATED AS A LIMIT ON ITSELF
========================================================
It is the MECHANISM, not the policy. `nfl/research/remediation/wave7/
GOVERNANCE_RECOMMENDATION_MATRIX.md` proposes a publication LEVEL for each
governance token. It is a recommendation awaiting an owner ruling and NOT ONE
OF ITS LEVEL ASSIGNMENTS IS IMPLEMENTED HERE. Every token whose level that
matrix proposes is evaluated by a rule whose verdict is `UNDECIDED`, whose
`authority` is `None`, and whose `owed` payload names the ruling that would
settle it. Wiring a level in before the ruling would be this file choosing the
policy by choosing the plumbing.

THREE DISPOSITIONS, AND UNDECIDED IS NOT A SHADE OF THE OTHER TWO
=================================================================
    ALLOW      a settled rule, on these facts, permits publication
    REFUSE     a settled rule, on these facts, refuses it
    UNDECIDED  no rule has been set; here is every input the rule would take

An UNDECIDED metric is neither silently published nor silently withheld. It
surfaces as `State.DEFERRED` -- the state this platform reserves for a debt
that stays OWED until something closes it -- carrying the facts and the name
of the ruling that is missing. A fourth answer, `UNEVALUABLE`, is what a rule
returns when the fact it needs was NOT SUPPLIED: an absent fact is never read
as a clean one, which is this project's Class A defect stated as a rule about
itself.

THE FINDINGS ARE ALWAYS COMPLETE. A refusal does not truncate the report. When
NFL-1 refuses board-wide -- which it does today -- the per-metric findings are
still computed and still ride in the evidence, because "here is everything
known about this number and no rule has been set" is the honest output and a
bare `NFL1_NOT_AUTHORIZED` is not.
"""
from __future__ import annotations

import dataclasses
import json
import pathlib
import sys
from typing import Any, Mapping

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.product import metrics as METRICS                       # noqa: E402
from nfl.production import candidate_mode as CAND                # noqa: E402
from nfl.production.nonqb import eligibility as ELIG             # noqa: E402
from nfl.production.nonqb import vintage_selector as VS          # noqa: E402

STATE = _REPO / 'nfl' / 'research' / 'PATH_C_STATE.json'
AUTH_RECORD = _REPO / 'nfl' / 'NFL1_OWNER_AUTHORIZATION.json'

SPEC_VERSION = 'nfl-publication-mechanism-1'

# The recommendation this module deliberately does not implement. Recorded by
# path so a reader can find it, and by status so nobody mistakes the reference
# for an adoption.
WAVE7_MATRIX = ('nfl/research/remediation/wave7/'
                'GOVERNANCE_RECOMMENDATION_MATRIX.md')
WAVE7_STATUS = 'RECOMMENDATION AWAITING OWNER RULING -- NO LEVEL ACTIVATED'


# ---------------------------------------------------------------------------
# The sentinel, and why it is not None
#
# `None` is a lawful value for several of these facts -- a metric with no
# model-health row genuinely has none. A caller that COULD NOT SUPPLY a fact is
# saying something different, and the two must not collapse. NOT_SUPPLIED is
# the second statement, it is never defaulted in, and every rule that meets it
# returns UNEVALUABLE rather than a pass.
class _NotSupplied:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return 'NOT_SUPPLIED'

    def __bool__(self):
        raise RuntimeError(
            'NOT_SUPPLIED_TRUTHINESS: refusing to let an unsupplied fact be '
            'tested as a boolean, which is how "we did not ask" becomes "it '
            'was fine".')


NOT_SUPPLIED = _NotSupplied()


def supplied(v) -> bool:
    return v is not NOT_SUPPLIED


# ---------------------------------------------------------------------------
# Verdicts and dispositions
ALLOW = 'ALLOW'
REFUSE = 'REFUSE'
UNDECIDED = 'UNDECIDED'
UNEVALUABLE = 'UNEVALUABLE'
NOT_APPLICABLE = 'NOT_APPLICABLE'
VERDICTS = (ALLOW, REFUSE, UNDECIDED, UNEVALUABLE, NOT_APPLICABLE)

# Worst-first, never averaged. Mirrors `outcome.combine`: a refusal dominates,
# then an unevaluable fact, then an undecided rule, and only an all-clear
# reads as ALLOW. UNEVALUABLE outranks UNDECIDED deliberately -- "we do not
# know the fact" is a worse position than "we know the fact and no rule has
# been set for it", and reporting the second while the first is true would
# overstate what the board knows.
_SEVERITY = {REFUSE: 4, UNEVALUABLE: 3, UNDECIDED: 2, ALLOW: 1,
             NOT_APPLICABLE: 0}

# Rule scopes. A board-wide rule cannot be settled by a metric's facts and a
# metric rule cannot speak for the board; keeping them apart is the point of
# the whole change.
BOARD = 'BOARD'
METRIC = 'METRIC'
RANKING = 'RANKING'


# ---------------------------------------------------------------------------
# A fact a caller must never be able to offer as a basis for publishing.
#
# `authorization.py` has always said there is no path from a green test suite
# to authorization. With a context object there is now a place to TRY, so the
# refusal is made mechanical rather than left to prose.
FORBIDDEN_BASES = ('tests_passed', 'suite_green', 'suite', 'test_result',
                   'checklist', 'checklist_discharged', 'override',
                   'force', 'authorized', 'authorize', 'publish')


class ForbiddenBasis(RuntimeError):
    """Raised when a caller offers a non-basis as evidence for publication."""


# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class PublicationContext:
    """Everything a per-run, per-metric publication decision consumes.

    NO FIELD HAS A DEFAULT. A default would be chosen once by whoever wrote
    the constructor and would then be wrong at every call site that forgot the
    fact -- and the specific wrong answer that matters here is an absent
    governance fact read as a clean one. A caller that cannot supply a fact
    passes `NOT_SUPPLIED` explicitly and gets UNEVALUABLE back.
    """
    run_id: str                       # run identity, from the sealed run
    metric: str                       # 'receiving/receiving_yards'
    layer: str                        # pipeline layer, e.g. 'receiving_conversion'
    model_configuration: str          # candidate_mode.MODES member
    chronology: Any                   # {family: verdict} in VS.CHRONOLOGY
    eligibility: Any                  # eligibility.matrix()[layer]
    hard_invariants: Any              # {name: {'state','code','class'}}
    warnings: Any                     # run_status stage warnings_detail
    governance: Any                   # [{'layer','governance'}]
    completeness: Any                 # artifact.COMPLETENESS member
    model_health: Any                 # model_health.evaluate() row, or None
    test_only: Any                    # bool: a TEST_ONLY fixture was consumed
    dry_run: Any                      # bool: run_status['dry_run']
    # THE THIRD CHANNEL, AND THE ONLY ONE TWO TOKENS TRAVEL IN.
    # `layers.SPEC['targets_carries']` is 'p4c-system-C-frozen; governance
    # DATA_BLOCKED' and `layers.SPEC['appearance']` carries
    # INFORMATION_CONSTRAINED the same way. Neither layer passes a
    # `governance=` key, so scanning only the governance records and the
    # warnings would miss both -- two of the four tokens Wave 7 calls
    # transport-blocked, missed by the thing built to read them.
    spec_version: Any                 # the composed spec string, verbatim

    def __post_init__(self):
        for f in ('run_id', 'metric', 'layer'):
            v = getattr(self, f)
            if not isinstance(v, str) or not v.strip():
                raise ValueError(
                    f'PUBLICATION_CONTEXT_IDENTITY_MISSING: {f} is {v!r}. A '
                    f'decision that cannot name the run and metric it is '
                    f'about is a board-wide decision wearing a metric label.')

    def as_dict(self) -> dict:
        d = {}
        for f in dataclasses.fields(self):
            v = getattr(self, f.name)
            d[f.name] = 'NOT_SUPPLIED' if v is NOT_SUPPLIED else v
        return d


def context(**facts) -> PublicationContext:
    """Build a context, refusing a non-basis by name.

    Keyword-only so a fact is never positioned into the wrong slot, and every
    declared field is REQUIRED: a missing keyword raises rather than
    defaulting, because the whole defect being repaired is a decision made
    without the facts.
    """
    for k in facts:
        if k.lower() in FORBIDDEN_BASES:
            raise ForbiddenBasis(
                f'PUBLICATION_BASIS_FORBIDDEN: {k!r} was offered as an input '
                f'to a publication decision. There is no path from a green '
                f'test suite, a discharged checklist or a caller-supplied '
                f'flag to authorization -- only an owner authorization '
                f'record. Remove it from the call.')
    declared = {f.name for f in dataclasses.fields(PublicationContext)}
    unknown = sorted(set(facts) - declared)
    if unknown:
        raise ValueError(
            f'PUBLICATION_CONTEXT_UNKNOWN_FACT: {unknown}. A fact this '
            f'mechanism does not declare cannot be weighed by a declared '
            f'rule, so accepting it would be carrying an input that nothing '
            f'reads.')
    missing = sorted(declared - set(facts))
    if missing:
        raise ValueError(
            f'PUBLICATION_CONTEXT_INCOMPLETE: {missing} not supplied. Pass '
            f'authorization.NOT_SUPPLIED explicitly for a fact you do not '
            f'hold -- an omitted fact would be indistinguishable from a '
            f'clean one, which is the defect this object exists to end.')
    return PublicationContext(**facts)


# ---------------------------------------------------------------------------
# The governance token vocabulary, DERIVED rather than retyped.
def _path_c() -> dict:
    return json.loads(STATE.read_text())


def gate_state() -> dict:
    return _path_c()['gates']


def _declared_action_tokens() -> tuple:
    """The action axis of PATH_C_STATE, minus the two production actions.

    Read from the governance artifact, so a token added there is weighed here
    without an edit. `eligibility.PRODUCTION_ACTIONS` names the two that
    license a production role; everything else on the axis is a state a
    publication rule might have to answer for.
    """
    axis = (_path_c().get('axes') or {}).get('action') or []
    return tuple(a for a in axis if a not in ELIG.PRODUCTION_ACTIONS)


# SIGNAL_WEAK has NO governance-artifact home. It is authored in
# `layers.py` free text and in a `metrics.py` caveat, and
# `PATH_C_STATE.subsystems.receiving_conversion.action` is HOLD_CHARACTERIZED,
# not SIGNAL_WEAK. It is declared here as a token the mechanism must be able
# to see, WITH that provenance defect attached, rather than being silently
# promoted to the same standing as a registered state.
UNREGISTERED_TOKENS = {
    'SIGNAL_WEAK': 'no PATH_C_STATE home; layer-authored free text at '
                   'layers.py and a metrics.py caveat. Registering it is '
                   'itself an open governance item.',
}


def governance_tokens() -> dict:
    """token -> where it is declared. Derived from the artifact plus the
    unregistered ones, which are labelled as unregistered."""
    out = {t: 'PATH_C_STATE.axes.action' for t in _declared_action_tokens()}
    for t, why in UNREGISTERED_TOKENS.items():
        out.setdefault(t, f'UNREGISTERED: {why}')
    return out


def _tokens_in(ctx: PublicationContext) -> list:
    """Every declared token this run's own governance and warnings name.

    Matched by substring against the derived vocabulary. The strings are the
    layers' own -- `governance='HOLD_CHARACTERIZED + CALIBRATION_DEFECT'`
    carries two -- and nothing here rewrites them: the match records WHICH
    token was seen and WHERE, and the source string travels with it.
    """
    vocab = governance_tokens()
    seen = []
    sources = []
    if supplied(ctx.governance):
        for rec in (ctx.governance or []):
            if isinstance(rec, Mapping):
                sources.append(('governance', rec.get('layer'),
                                str(rec.get('governance') or '')))
            else:
                sources.append(('governance', None, str(rec)))
    if supplied(ctx.warnings):
        for rec in (ctx.warnings or []):
            if isinstance(rec, Mapping):
                sources.append(('warning', rec.get('layer'),
                                str(rec.get('warning') or '')))
            else:
                sources.append(('warning', None, str(rec)))
    if supplied(ctx.spec_version) and ctx.spec_version:
        sources.append(('spec_version', ctx.layer, str(ctx.spec_version)))
    for kind, layer, text in sources:
        for tok, home in vocab.items():
            if tok in text:
                seen.append({'token': tok, 'declared_in': home,
                             'seen_in': kind, 'layer': layer,
                             'source_text': text[:300]})
    return seen


# ---------------------------------------------------------------------------
def _finding(rule, scope, verdict, why, *, authority=None, owed=None,
             inputs=None, **facts) -> dict:
    if verdict not in VERDICTS:
        raise ValueError(f'PUBLICATION_VERDICT_UNDECLARED: {verdict!r}')
    if verdict in (ALLOW, REFUSE) and not authority:
        raise ValueError(
            f'PUBLICATION_RULE_WITHOUT_AUTHORITY: {rule} returned {verdict} '
            f'with no authority named. A settled verdict must say which '
            f'ruling settled it, or it is this file inventing a policy.')
    if verdict == UNDECIDED and authority:
        raise ValueError(
            f'PUBLICATION_RULE_UNDECIDED_WITH_AUTHORITY: {rule} claims both '
            f'an authority and that no rule exists.')
    return {'rule': rule, 'scope': scope, 'verdict': verdict, 'why': why,
            'authority': authority, 'owed': owed, 'inputs': inputs or [],
            'facts': facts}


# --------------------------------------------------------------- BOARD rules
def _rel(p: pathlib.Path) -> str:
    try:
        return str(p.relative_to(_REPO))
    except ValueError:
        return str(p)


def _rule_nfl1(ctx) -> dict:
    """The gate that has always been here. Board-wide, and settled."""
    g = gate_state()
    inputs = ['PATH_C_STATE.gates', _rel(AUTH_RECORD)]
    if g.get('NFL_1') != 'AUTHORIZED':
        return _finding(
            'NFL1_AUTHORIZATION', BOARD, REFUSE,
            f'NFL-1 is {g.get("NFL_1")!r} and G0A is {g.get("G0A")!r}. A '
            f'forecast may be COMPUTED and SEALED locally, but it may not be '
            f'published. No test result, checklist state or caller flag can '
            f'change this -- only an owner authorization record.',
            authority='owner gate, PATH_C_STATE.gates.NFL_1',
            inputs=inputs, gates=g)
    if not AUTH_RECORD.exists():
        return _finding(
            'NFL1_AUTHORIZATION', BOARD, REFUSE,
            'the gate reads AUTHORIZED but no owner authorization record '
            'exists. A gate flipped without a record behind it is exactly '
            'the auto-authorization this guard prevents.',
            authority='owner authorization record (absent)',
            inputs=inputs, gates=g, defect='AUTHORIZATION_RECORD_MISSING')
    rec = json.loads(AUTH_RECORD.read_text())
    if rec.get('basis') != 'OWNER_DECISION' or not rec.get('owner_decision_id'):
        return _finding(
            'NFL1_AUTHORIZATION', BOARD, REFUSE,
            f'authorization basis is {rec.get("basis")!r}. Only an explicit, '
            f'identified owner decision authorizes publication.',
            authority='owner authorization record (invalid basis)',
            inputs=inputs, gates=g, defect='AUTHORIZATION_BASIS_INVALID')
    return _finding(
        'NFL1_AUTHORIZATION', BOARD, ALLOW,
        f'owner decision {rec.get("owner_decision_id")!r} authorizes '
        f'publication board-wide.',
        authority=f'owner decision {rec.get("owner_decision_id")!r}',
        inputs=inputs, gates=g,
        owner_decision_id=rec.get('owner_decision_id'))


# -------------------------------------------------------------- METRIC rules
def _rule_test_only(ctx) -> dict:
    if not supplied(ctx.test_only):
        return _finding('TEST_ONLY_DATA', METRIC, UNEVALUABLE,
                        'the run did not say whether a TEST_ONLY fixture was '
                        'consumed, and an unanswered quarantine question is '
                        'not a clean one.',
                        inputs=['layers.assert_publishable'])
    if ctx.test_only:
        return _finding(
            'TEST_ONLY_DATA', METRIC, REFUSE,
            'a TEST_ONLY fixture reached this metric. A fixture may exercise '
            'the engine and may never reach a published forecast.',
            authority='layers.assert_publishable, TEST_ONLY fixture '
                      'quarantine',
            inputs=['layers.assert_publishable'])
    return _finding('TEST_ONLY_DATA', METRIC, ALLOW,
                    'no TEST_ONLY fixture reached this metric.',
                    authority='layers.assert_publishable',
                    inputs=['layers.assert_publishable'])


def _rule_dry_run(ctx) -> dict:
    """A run the system already declares is not evidence cannot be published.

    This is not a new policy. `run_forecast`'s own `--dry-run` help says
    "historical fixture run; NEVER prospective evidence", and the run writes
    `prospective_eligible: False` for one. The rule reads that declaration at
    the gate instead of leaving it as a string in a help message -- which is
    where it was, while `make_board.build_one` passed `dry_run=True` on every
    board it has ever produced.
    """
    inputs = ['run_status.dry_run', 'run_status.prospective_eligible']
    if not supplied(ctx.dry_run):
        return _finding('DRY_RUN', METRIC, UNEVALUABLE,
                        'the run did not say whether it was a dry run.',
                        inputs=inputs)
    if ctx.dry_run:
        return _finding(
            'DRY_RUN', METRIC, REFUSE,
            'this is a dry run. run_forecast declares a dry run a historical '
            'fixture run and NEVER prospective evidence, and the run seals '
            'prospective_eligible False. A number that is not evidence '
            'cannot be published as a forecast.',
            authority="run_forecast --dry-run: 'historical fixture run; "
                      "NEVER prospective evidence'",
            inputs=inputs)
    return _finding('DRY_RUN', METRIC, ALLOW,
                    'this is not a dry run.',
                    authority='run_forecast --dry-run declaration',
                    inputs=inputs)


def _rule_metric_has_control(ctx) -> dict:
    """metrics.py is the anti-fabrication spine and it is already a ruling."""
    key = tuple(str(ctx.metric).split('/', 1))
    inputs = ['product.metrics.SUPPORTED', 'product.metrics.UNSUPPORTED']
    if len(key) != 2:
        return _finding('METRIC_HAS_GOVERNED_CONTROL', METRIC, UNEVALUABLE,
                        f'{ctx.metric!r} is not a layer/key metric name, so '
                        f'the product contract cannot be consulted.',
                        inputs=inputs)
    un = METRICS.UNSUPPORTED.get(key)
    if un:
        return _finding(
            'METRIC_HAS_GOVERNED_CONTROL', METRIC, REFUSE,
            f'{ctx.metric} is a declared absence: {un.get("code")}. '
            f'{un.get("reason", "")[:200]}',
            authority='product.metrics.UNSUPPORTED (declared absence)',
            inputs=inputs, code=un.get('code'))
    sup = METRICS.SUPPORTED.get(key)
    if not sup:
        return _finding(
            'METRIC_HAS_GOVERNED_CONTROL', METRIC, REFUSE,
            f'{ctx.metric} appears in neither SUPPORTED nor UNSUPPORTED. A '
            f'metric the product contract has never heard of cannot be '
            f'published under it.',
            authority='product.metrics contract (metric undeclared)',
            inputs=inputs)
    return _finding(
        'METRIC_HAS_GOVERNED_CONTROL', METRIC, ALLOW,
        f'{ctx.metric} is declared {sup.get("status")} by the product '
        f'contract.',
        authority='product.metrics.SUPPORTED',
        inputs=inputs, metric_status=sup.get('status'),
        caveat=sup.get('caveat'))


def _rule_hard_invariants(ctx) -> dict:
    """FAIL or BLOCKED on a HARD invariant refuses. That rule is settled.

    DEFERRED and NOT_APPLICABLE are NOT treated as refusals here. Wave 7 rows
    9 and 10 propose changing that; the change is not made, and each of those
    states is instead surfaced as its own undecided finding by
    `_rule_hard_invariant_states_undecided`.
    """
    inputs = ['draw_coherence.assert_draw_coherence',
              'prospective.artifact.HARD_REFUSING_STATES']
    if not supplied(ctx.hard_invariants):
        return _finding('HARD_INVARIANT_STATE', METRIC, UNEVALUABLE,
                        'no hard-invariant verdicts were supplied. A check '
                        'that did not run has not passed.', inputs=inputs)
    hv = ctx.hard_invariants or {}
    if not hv:
        return _finding('HARD_INVARIANT_STATE', METRIC, UNEVALUABLE,
                        'the verdict set is empty. Zero checks is an error, '
                        'not a clean result.', inputs=inputs)
    bad = sorted(k for k, v in hv.items()
                 if str((v or {}).get('class', 'HARD')) == 'HARD'
                 and str((v or {}).get('state')) in ('FAIL', 'BLOCKED'))
    if bad:
        return _finding(
            'HARD_INVARIANT_STATE', METRIC, REFUSE,
            f'{len(bad)} HARD invariant(s) carry FAIL or BLOCKED on the '
            f'published draws: {bad}. An impossible state, or a check that '
            f'could not run, is not survivable.',
            authority='prospective.artifact.HARD_REFUSING_STATES',
            inputs=inputs, failing=bad)
    return _finding(
        'HARD_INVARIANT_STATE', METRIC, ALLOW,
        f'{len(hv)} invariant verdict(s) supplied and none is a HARD FAIL or '
        f'BLOCKED.', authority='prospective.artifact.HARD_REFUSING_STATES',
        inputs=inputs, n_verdicts=len(hv))


def _rule_hard_invariant_states_undecided(ctx) -> dict:
    """HARD DEFERRED / HARD NOT_APPLICABLE at the PUBLICATION boundary.

    They seal today, by a design `artifact.py` argues and this file does not
    reopen. Whether a board may be OFFERED while a construction identity was
    never checked is a different question, and no ruling answers it. Wave 7
    rows 9 and 10 propose one; it is reported, not applied.
    """
    inputs = ['draw_coherence.assert_draw_coherence',
              'prospective.artifact.INVARIANTS']
    if not supplied(ctx.hard_invariants):
        return _finding('HARD_INVARIANT_UNEVALUATED_AT_PUBLICATION', METRIC,
                        UNEVALUABLE, 'no hard-invariant verdicts supplied.',
                        inputs=inputs)
    hv = ctx.hard_invariants or {}
    unevaluated = sorted(
        k for k, v in hv.items()
        if str((v or {}).get('class', 'HARD')) == 'HARD'
        and str((v or {}).get('state')) in ('DEFERRED', 'NOT_APPLICABLE'))
    if not unevaluated:
        return _finding('HARD_INVARIANT_UNEVALUATED_AT_PUBLICATION', METRIC,
                        NOT_APPLICABLE,
                        'every HARD invariant supplied was evaluated.',
                        inputs=inputs)
    return _finding(
        'HARD_INVARIANT_UNEVALUATED_AT_PUBLICATION', METRIC, UNDECIDED,
        f'{len(unevaluated)} HARD invariant(s) were not evaluated on this '
        f'run: {unevaluated}. They lawfully seal. Whether a board may be '
        f'published while a construction identity went unchecked has no '
        f'ruling.',
        owed={'owner_ruling': 'publication-boundary treatment of HARD '
                              'DEFERRED and HARD NOT_APPLICABLE',
              'recommendation': f'{WAVE7_MATRIX} rows 9 and 10',
              'recommendation_status': WAVE7_STATUS},
        inputs=inputs, unevaluated=unevaluated)


def _rule_chronology(ctx) -> dict:
    """A forecast that ate a capture taken after its own cut is not a forecast."""
    inputs = ['vintage_selector.CHRONOLOGY', 'refusal.SOURCE_TOO_LATE']
    if not supplied(ctx.chronology):
        return _finding('CHRONOLOGY_LAWFUL', METRIC, UNEVALUABLE,
                        'no chronology verdicts were supplied, so nothing '
                        'establishes that this metric was built from '
                        'information that existed at forecast time.',
                        inputs=inputs)
    ch = ctx.chronology
    if isinstance(ch, str):
        ch = {'(unnamed family)': ch}
    if not ch:
        return _finding('CHRONOLOGY_LAWFUL', METRIC, UNEVALUABLE,
                        'the chronology verdict set is empty.', inputs=inputs)
    undeclared = sorted(f for f, v in ch.items() if v not in VS.CHRONOLOGY)
    if undeclared:
        return _finding(
            'CHRONOLOGY_LAWFUL', METRIC, UNEVALUABLE,
            f'{undeclared} carry a verdict outside the closed vocabulary '
            f'{list(VS.CHRONOLOGY)}. A verdict outside it is a bug, not a '
            f'nuance.', inputs=inputs, undeclared=undeclared)
    late = sorted(f for f, v in ch.items() if v != VS.LAWFUL)
    if late:
        return _finding(
            'CHRONOLOGY_LAWFUL', METRIC, REFUSE,
            f'{len(late)} consumed source family/families are not lawful at '
            f'the cut: {[(f, ch[f]) for f in late]}.',
            authority='vintage_selector closed chronology vocabulary; '
                      'refusal.SOURCE_TOO_LATE',
            inputs=inputs, unlawful=late)
    return _finding(
        'CHRONOLOGY_LAWFUL', METRIC, ALLOW,
        f'all {len(ch)} consumed source family/families were retrieved at or '
        f'before the cut.',
        authority='vintage_selector closed chronology vocabulary',
        inputs=inputs, families=sorted(ch))


def _rule_candidate_configuration(ctx) -> dict:
    inputs = ['candidate_mode.MODES', 'candidate_mode.COMPONENTS']
    if not supplied(ctx.model_configuration):
        return _finding('CANDIDATE_CONFIGURATION', METRIC, UNEVALUABLE,
                        'the run did not name its model configuration.',
                        inputs=inputs)
    mode = str(ctx.model_configuration)
    if mode not in CAND.MODES:
        return _finding(
            'CANDIDATE_CONFIGURATION', METRIC, REFUSE,
            f'{mode!r} is not a declared configuration. An undeclared '
            f'configuration cannot be audited, so it cannot publish.',
            authority='candidate_mode.MODES', inputs=inputs, mode=mode)
    if mode != CAND.PRODUCTION_BASELINE:
        return _finding(
            'CANDIDATE_CONFIGURATION', METRIC, REFUSE,
            f'this run used {mode}. Every candidate component is '
            f'REHEARSAL_ONLY and engineering integration is not prospective '
            f'validation; a candidate configuration may not masquerade as '
            f'the promoted production model.',
            authority='candidate_mode: candidate components are '
                      'REHEARSAL_ONLY until an owner artifact says otherwise',
            inputs=inputs, mode=mode)
    return _finding('CANDIDATE_CONFIGURATION', METRIC, ALLOW,
                    'this run used the production baseline configuration.',
                    authority='candidate_mode.PRODUCTION_BASELINE',
                    inputs=inputs, mode=mode)


def _rule_governance_tokens(ctx) -> list:
    """One finding per governance token this metric's layers actually raised.

    THIS IS THE ROW THE WHOLE CHANGE EXISTS FOR, and it is deliberately the
    one that decides nothing. INFORMATION_CONSTRAINED, DATA_BLOCKED,
    SIGNAL_WEAK, CALIBRATION_DEFECT, HOLD_TENTATIVE and HOLD_CHARACTERIZED
    now REACH this function -- WS-D repaired the transport that dropped them
    -- and no ruling says what any of them does to publication. Each surfaces
    UNDECIDED with its source text, the layer that said it, where the token is
    declared, and the recommendation that is awaiting a ruling.
    """
    inputs = ['run_status.stages[].governance',
              'run_status.stages[].warnings_detail',
              'run_status.stages[].spec_version',
              'PATH_C_STATE.axes.action']
    absent = [n for n, v in (('governance', ctx.governance),
                             ('warnings', ctx.warnings),
                             ('spec_version', ctx.spec_version))
              if not supplied(v)]
    seen = _tokens_in(ctx)
    if absent and not seen:
        # EITHER channel missing is enough to make "no token" unsafe to read
        # as "no token was raised". The channels are not interchangeable:
        # `receiving_conversion` publishes CALIBRATION_DEFECT in BOTH, and
        # `targets_carries` publishes DATA_BLOCKED in its spec only, so an
        # empty warnings list next to an unsupplied governance record says
        # nothing at all.
        return [_finding(
            'LAYER_GOVERNANCE_TOKEN', METRIC, UNEVALUABLE,
            f'{absent} were not supplied and no token was found in what was. '
            f'A silent channel cannot be read as a quiet one.',
            inputs=inputs, channels_not_supplied=absent)]
    if not seen:
        return [_finding(
            'LAYER_GOVERNANCE_TOKEN', METRIC, NOT_APPLICABLE,
            'both channels were supplied and the layers behind this metric '
            'raised no declared governance token.', inputs=inputs)]
    out = []
    for s in seen:
        out.append(_finding(
            f'LAYER_GOVERNANCE_TOKEN:{s["token"]}@{s["seen_in"]}'
            f':{s["layer"]}', METRIC, UNDECIDED,
            f'layer {s["layer"]!r} published governance token '
            f'{s["token"]} ({s["seen_in"]}). No ruling states what this '
            f'token does to publication of this metric.',
            owed={'owner_ruling': f'publication level for {s["token"]}',
                  'recommendation': WAVE7_MATRIX,
                  'recommendation_status': WAVE7_STATUS},
            inputs=inputs, **s))
    return out


def _rule_completeness(ctx) -> dict:
    inputs = ['run_status.completeness', 'run_status.absent_layers']
    if not supplied(ctx.completeness):
        return _finding('COMPLETENESS', METRIC, UNEVALUABLE,
                        'the run did not report its completeness.',
                        inputs=inputs)
    c = str(ctx.completeness)
    if c == 'COMPLETE':
        return _finding('COMPLETENESS', METRIC, ALLOW,
                        'the run covered every player it declared.',
                        authority='run_forecast completeness contract',
                        inputs=inputs, completeness=c)
    return _finding(
        'COMPLETENESS', METRIC, UNDECIDED,
        f'the run is {c}. The players who WERE modelled are modelled '
        f'properly, so this describes coverage rather than correctness, and '
        f'no ruling says whether a partial board may be published or only '
        f'may not be CALLED complete.',
        owed={'owner_ruling': 'publication treatment of '
                              'PARTIAL_PLAYER_COVERAGE, and separately of a '
                              'completeness CLAIM',
              'recommendation': f'{WAVE7_MATRIX} row 6',
              'recommendation_status': WAVE7_STATUS},
        inputs=inputs, completeness=c)


def _rule_model_health_ranking(ctx) -> dict:
    """Settled, and settled for RANKING ONLY.

    `product.model_health` states its own scope in its own words: a warning
    makes a metric ineligible for RANKING and "does not delete the row, hide
    the disagreement, or alter any projection". So this rule answers the
    ranking question and is explicitly scoped away from the publication one.
    """
    inputs = ['product.model_health.evaluate',
              'product.model_health.assert_ranking_admissible']
    if not supplied(ctx.model_health):
        return _finding('MODEL_HEALTH_RANKING', RANKING, UNEVALUABLE,
                        'no model-health row was supplied for this metric.',
                        inputs=inputs)
    h = ctx.model_health
    if h is None:
        return _finding(
            'MODEL_HEALTH_RANKING', RANKING, UNEVALUABLE,
            'this metric has no model-health row. An unmeasured metric is '
            'not a healthy one.', inputs=inputs)
    w = list((h or {}).get('warnings') or [])
    if w:
        return _finding(
            'MODEL_HEALTH_RANKING', RANKING, REFUSE,
            f'the metric is under {len(w)} health warning(s): {w}. A large '
            f'model-versus-market gap produced by a layer under a health '
            f'warning is evidence about the layer, not a candidate.',
            authority='product.model_health.assert_ranking_admissible',
            inputs=inputs, warnings=w,
            warning_meanings=(h or {}).get('warning_meanings'),
            n_scored=(h or {}).get('n_scored'),
            n_game_clusters=(h or {}).get('n_game_clusters'),
            outcome_selection_basis=(h or {}).get('outcome_selection_basis'))
    return _finding(
        'MODEL_HEALTH_RANKING', RANKING, ALLOW,
        'the metric carries no health warning and may be ranked.',
        authority='product.model_health.assert_ranking_admissible',
        inputs=inputs, n_scored=(h or {}).get('n_scored'),
        n_game_clusters=(h or {}).get('n_game_clusters'))


def _rule_model_health_publication(ctx) -> dict:
    """The question model_health does NOT answer, kept separate from the one
    it does."""
    inputs = ['product.model_health.evaluate']
    if not supplied(ctx.model_health) or ctx.model_health is None:
        return _finding('MODEL_HEALTH_PUBLICATION', METRIC, UNEVALUABLE,
                        'no model-health row was supplied for this metric, '
                        'so nothing is known about its measured behaviour.',
                        inputs=inputs)
    w = list((ctx.model_health or {}).get('warnings') or [])
    if not w:
        return _finding('MODEL_HEALTH_PUBLICATION', METRIC, NOT_APPLICABLE,
                        'no health warning, so no publication question '
                        'arises from health.', inputs=inputs)
    return _finding(
        'MODEL_HEALTH_PUBLICATION', METRIC, UNDECIDED,
        f'the metric is under health warning(s) {w}. model_health rules on '
        f'RANKING and says in terms that it does not delete the row. Whether '
        f'a warned metric may be PUBLISHED is a separate question with no '
        f'ruling.',
        owed={'owner_ruling': 'publication treatment of a metric under a '
                              'model-health warning',
              'note': 'model_health.assert_ranking_admissible settles '
                      'ranking only, by its own declaration'},
        inputs=inputs, warnings=w)


def _rule_eligibility_contradiction(ctx) -> dict:
    """Surface the contradiction. DO NOT resolve it.

    `eligibility.matrix()` records every pipeline layer `production_role`
    REHEARSAL_ONLY or BLOCKED with `publication_eligible: False` -- a constant
    False whose in-code reason is "NFL-1 gates everything anyway" -- while
    `product.metrics` marks 13 of 20 SUPPORTED entries MODELED and
    `daily_board.eligibility` gates ranking on
    `metric_status in ('MODELED','PROVISIONAL')`. Two governance-facing
    statements about the same layer disagree, and governance has no path to
    the gate. Deciding which one wins is an owner ruling; this reports both.
    """
    inputs = ['eligibility.matrix()', 'product.metrics.SUPPORTED',
              'daily_board.eligibility']
    if not supplied(ctx.eligibility):
        return _finding('ELIGIBILITY_VS_PRODUCT_STATUS', METRIC, UNEVALUABLE,
                        'no eligibility row was supplied for this layer.',
                        inputs=inputs)
    row = ctx.eligibility or {}
    key = tuple(str(ctx.metric).split('/', 1))
    product_status = (METRICS.SUPPORTED.get(key) or {}).get('status')
    role = row.get('allowed_runtime_role')
    pub_elig = row.get('publication_eligible')
    if pub_elig is True and role == 'PRODUCTION':
        return _finding(
            'ELIGIBILITY_VS_PRODUCT_STATUS', METRIC, ALLOW,
            f'the eligibility matrix grants layer {ctx.layer!r} a PRODUCTION '
            f'role and publication eligibility.',
            authority='eligibility.matrix(), derived from PATH_C_STATE',
            inputs=inputs, role=role, product_status=product_status)
    contradiction = (product_status in ('MODELED', 'PROVISIONAL')
                     and pub_elig is not True)
    return _finding(
        'ELIGIBILITY_VS_PRODUCT_STATUS', METRIC, UNDECIDED,
        f'the governance matrix records layer {ctx.layer!r} as '
        f'production_role {role!r}, publication_eligible {pub_elig!r}, '
        f'owner_state {row.get("owner_state")!r}, while the product contract '
        f'marks {ctx.metric} {product_status!r} and daily_board ranks on '
        f'exactly that status. '
        + ('The two disagree about the same layer and no ruling says which '
           'governs publication.' if contradiction else
           'No ruling says whether the matrix governs publication of this '
           'metric.'),
        owed={'owner_ruling': 'which of eligibility.matrix() and '
                              'product.metrics governs publication, and '
                              'whether publication_eligible is a real '
                              'per-layer fact or a constant False',
              'recommendation': f'{WAVE7_MATRIX} rows 1 and 2',
              'recommendation_status': WAVE7_STATUS},
        inputs=inputs, contradiction=contradiction,
        production_role=role, publication_eligible=pub_elig,
        owner_state=row.get('owner_state'),
        research_state=row.get('research_state'),
        product_status=product_status,
        reason=row.get('reason'))


# The declared rule order. Precedence is DECLARED, not incidental: the first
# REFUSE in this order names the composed Outcome, so a reader can predict
# which refusal a run will report without running it.
_RULES = (
    _rule_nfl1,
    _rule_test_only,
    _rule_dry_run,
    _rule_metric_has_control,
    _rule_hard_invariants,
    _rule_chronology,
    _rule_candidate_configuration,
    _rule_eligibility_contradiction,
    _rule_governance_tokens,
    _rule_hard_invariant_states_undecided,
    _rule_completeness,
    _rule_model_health_ranking,
    _rule_model_health_publication,
)


def findings(ctx: PublicationContext) -> list:
    """Every declared rule, evaluated against one run and one metric."""
    out = []
    for r in _RULES:
        got = r(ctx)
        out.extend(got if isinstance(got, list) else [got])
    return out


def _compose(fs, scopes) -> str:
    sel = [f for f in fs if f['scope'] in scopes]
    if not sel:
        return NOT_APPLICABLE
    worst = max(_SEVERITY[f['verdict']] for f in sel)
    for v, s in _SEVERITY.items():
        if s == worst:
            return v
    return NOT_APPLICABLE


def decide(ctx: PublicationContext) -> dict:
    """The whole finding: every rule, the two dispositions, the composed one.

    The two dispositions are kept apart because collapsing them is the defect.
    `board_disposition` is what the board-wide gate says; `metric_disposition`
    is what THIS metric's own facts say. Tonight they differ -- the board
    refuses and several metrics are UNDECIDED -- and a single number would
    have destroyed exactly that distinction.
    """
    fs = findings(ctx)
    board = _compose(fs, (BOARD,))
    metric = _compose(fs, (METRIC,))
    ranking = _compose(fs, (RANKING,))
    overall = max((board, metric), key=lambda v: _SEVERITY[v])
    undecided = [f for f in fs if f['verdict'] == UNDECIDED
                 and f['scope'] in (BOARD, METRIC)]
    return {
        'spec_version': SPEC_VERSION,
        'run_id': ctx.run_id, 'metric': ctx.metric, 'layer': ctx.layer,
        'board_disposition': board,
        'metric_disposition': metric,
        'ranking_disposition': ranking,
        'disposition': overall,
        # Split by scope, because a refusal on RANKING is not a refusal to
        # PUBLISH and the two must never be composed into one answer.
        # `product.model_health` says so in its own words: a warning makes a
        # metric ineligible for ranking and does not delete the row.
        'refusals': [f for f in fs if f['verdict'] == REFUSE
                     and f['scope'] in (BOARD, METRIC)],
        'ranking_refusals': [f for f in fs if f['verdict'] == REFUSE
                             and f['scope'] == RANKING],
        'undecided': undecided,
        'unevaluable': [f for f in fs if f['verdict'] == UNEVALUABLE
                        and f['scope'] in (BOARD, METRIC)],
        'owed_rulings': [f['owed'] for f in undecided if f.get('owed')],
        'findings': fs,
        'facts_consumed': ctx.as_dict(),
        'wave7_matrix': {'path': WAVE7_MATRIX, 'status': WAVE7_STATUS,
                         'levels_activated': []},
    }


# ---------------------------------------------------------------------------
def may_publish(ctx: PublicationContext | None = None) -> Outcome:
    """The only function permitted to say a forecast may be PUBLISHED.

    WITHOUT a context it answers the board-wide question only, exactly as it
    always did, and SAYS SO in its evidence: `scope: BOARD_WIDE` and
    `metric_decision: NOT_MADE`. That is not a convenience -- a caller that
    has not been wired to supply the facts is now visible in the artifact
    instead of receiving a metric-shaped answer to a board-shaped question.

    WITH a context it evaluates every declared rule and composes worst-first:
        a settled REFUSE  -> BLOCKED (GOVERNANCE) -- or FAIL where the refusal
                             is a defect in the authorization record itself
        an UNEVALUABLE    -> BLOCKED (DATA); an unsupplied fact is not a pass
        an UNDECIDED      -> DEFERRED, with every owed ruling named
        all ALLOW         -> PASS
    The complete findings ride in the evidence of ALL FOUR, so a refusal never
    truncates the report.
    """
    if ctx is None:
        f = _rule_nfl1(None)
        g = f['facts'].get('gates')
        ev = {'gates': g, 'scope': 'BOARD_WIDE',
              'metric_decision': 'NOT_MADE',
              'why_no_metric_decision':
                  'may_publish() was called without a PublicationContext, so '
                  'no per-run, per-metric rule could be evaluated. This is a '
                  'board-wide answer and must not be read as a statement '
                  'about any one metric.',
              'spec_version': SPEC_VERSION}
        if f['verdict'] == ALLOW:
            return Outcome.ok('PUBLICATION_AUTHORIZED',
                              value=f['facts'].get('owner_decision_id'), **ev)
        defect = f['facts'].get('defect')
        if defect:
            return Outcome.fail(defect, f['why'], **ev)
        return Outcome.blocked('NFL1_NOT_AUTHORIZED', f['why'],
                               cause=Cause.GOVERNANCE, **ev)

    if not isinstance(ctx, PublicationContext):
        return Outcome.fail(
            'PUBLICATION_CONTEXT_MALFORMED',
            f'may_publish received a {type(ctx).__name__}. Build the context '
            f'with authorization.context(**facts) so every declared fact is '
            f'present or explicitly NOT_SUPPLIED.')

    d = decide(ctx)
    ev = {'decision': d, 'spec_version': SPEC_VERSION,
          'scope': 'RUN_AND_METRIC',
          'board_disposition': d['board_disposition'],
          'metric_disposition': d['metric_disposition'],
          'ranking_disposition': d['ranking_disposition'],
          'disposition': d['disposition']}
    if d['refusals']:
        first = d['refusals'][0]
        defect = first['facts'].get('defect')
        detail = (f'{first["rule"]} refuses {ctx.metric} on run '
                  f'{ctx.run_id}: {first["why"]}')
        if d['undecided']:
            detail += (f' ALSO UNDECIDED, and reported rather than hidden '
                       f'behind the refusal: '
                       f'{[u["rule"] for u in d["undecided"]]}.')
        if defect:
            return Outcome.fail(defect, detail, **ev)
        code = ('NFL1_NOT_AUTHORIZED' if first['rule'] == 'NFL1_AUTHORIZATION'
                else 'PUBLICATION_REFUSED')
        return Outcome.blocked(code, detail, cause=Cause.GOVERNANCE, **ev)
    if d['unevaluable']:
        names = [u['rule'] for u in d['unevaluable']]
        return Outcome.blocked(
            'PUBLICATION_FACTS_NOT_SUPPLIED',
            f'{len(names)} rule(s) could not be evaluated for {ctx.metric} '
            f'because the facts they take were not supplied: {names}. An '
            f'unanswered question is not a clean answer.',
            cause=Cause.DATA, **ev)
    if d['undecided']:
        return Outcome.deferred(
            'PUBLICATION_RULE_UNDECIDED',
            f'{ctx.metric} on run {ctx.run_id} clears every settled rule and '
            f'{len(d["undecided"])} rule(s) governing it have never been '
            f'set: {[u["rule"] for u in d["undecided"]]}. The number is '
            f'neither published nor withheld by this mechanism; every input '
            f'to the missing rule is attached.',
            owed=d['owed_rulings'], **ev)
    return Outcome.ok(
        'PUBLICATION_AUTHORIZED',
        value=ctx.metric,
        detail=f'every declared rule allows {ctx.metric} on run '
               f'{ctx.run_id}.', **ev)


def may_compute() -> Outcome:
    """Computing and sealing locally is always allowed. Publishing is not."""
    return Outcome.ok('COMPUTE_ALLOWED', value=True,
                      detail='a run may compute and seal; publication is gated '
                             'separately by may_publish()')


# ---------------------------------------------------------------------------
# WHICH LAYER PRODUCES WHICH METRIC, AND WHAT THE RUN CALLS THAT LAYER.
#
# The product contract names METRICS. The governance artifact, the eligibility
# matrix and `layers.py` name LAYERS. `run_status.json` names STAGES, and the
# two vocabularies are not the same: `run_forecast.STAGE_LAYERS` maps stage
# `conversion` onto engine layer `receiving_conversion`, and that one rename
# is enough to make `eligibility.matrix().get('conversion')` return nothing.
# Measured: reading a sealed run with the stage name yields no eligibility row
# at all, so the layer's governance state never reaches the metric.
#
# The join is declared here, one row per SUPPORTED metric, because nothing in
# the repository exposes it -- `STAGE_LAYERS` is a local inside
# `run_forecast.build` and cannot be imported. `assert_metric_origin_complete`
# fails if the product contract gains a metric this table does not place, so
# the map cannot go quietly stale the way a hand-written tuple does.
#
# `layer` is the name eligibility and PATH_C_STATE use. `stage` is the name
# `run_status.stages[].stage` uses. Where they are the same the row still
# says both, so a future divergence is a changed row rather than a silent one.
METRIC_ORIGIN = {
    ('qb', 'att'): ('qb_layer', 'qb_layer'),
    ('qb', 'cmp'): ('qb_layer', 'qb_layer'),
    ('qb', 'db'): ('qb_layer', 'qb_layer'),
    ('qb', 'pyds'): ('qb_layer', 'qb_layer'),
    ('qb', 'ptd'): ('qb_layer', 'qb_layer'),
    ('qb', 'int'): ('qb_layer', 'qb_layer'),
    ('qb', 'sacks'): ('qb_layer', 'qb_layer'),
    ('qb', 'scr'): ('qb_layer', 'qb_layer'),
    ('qb', 'rush_opp'): ('qb_layer', 'qb_layer'),
    ('qb', 'ryds'): ('qb_layer', 'qb_layer'),
    ('qb', 'rtd'): ('qb_layer', 'qb_layer'),
    # layers.targets_carries emits the opportunity draws.
    ('receiving', 'targets'): ('targets_carries', 'targets_carries'),
    ('rushing', 'carries'): ('targets_carries', 'targets_carries'),
    # layers.receiving_conversion turns targets into receptions and yards.
    ('receiving', 'receptions'): ('receiving_conversion', 'conversion'),
    ('receiving', 'receiving_yards'): ('receiving_conversion', 'conversion'),
    # layers.td_layer and layers.rushing_td, both reported by stage td_layer
    # (run_forecast.STAGE_LAYERS: 'td_layer' -> receiving_td, rushing_td).
    ('receiving', 'receiving_td'): ('td_layer', 'td_layer'),
    ('rushing', 'rushing_td'): ('td_layer', 'td_layer'),
}


def assert_metric_origin_complete() -> Outcome:
    """Every SUPPORTED metric must be placed on a layer, or it has no
    governance route at all."""
    missing = sorted(f'{a}/{b}' for (a, b) in METRICS.SUPPORTED
                     if (a, b) not in METRIC_ORIGIN)
    extra = sorted(f'{a}/{b}' for (a, b) in METRIC_ORIGIN
                   if (a, b) not in METRICS.SUPPORTED)
    unknown = sorted({lay for lay, _ in METRIC_ORIGIN.values()
                      if lay not in ELIG.LAYER_SUBSYSTEM})
    if missing or extra or unknown:
        return Outcome.fail(
            'METRIC_ORIGIN_INCOMPLETE',
            f'metrics with no producing layer: {missing}; rows for metrics '
            f'the product contract does not declare: {extra}; layers the '
            f'eligibility matrix has never heard of: {unknown}. A metric with '
            f'no layer has no route from a governance state to a publication '
            f'decision, which is the defect this module exists to end.',
            missing=missing, extra=extra, unknown_layers=unknown)
    return Outcome.ok('METRIC_ORIGIN_COMPLETE', value=len(METRIC_ORIGIN),
                      detail='every SUPPORTED metric is placed on a layer the '
                             'eligibility matrix knows')


def decide_board(run_status: Mapping, *, chronology, model_health=None,
                 metrics=None) -> dict:
    """Every SUPPORTED metric on one run, decided separately.

    `chronology` and `model_health` are supplied by the CALLER, because the
    seal holds neither: the chronology verdicts live in the board's vintage
    selection and model health is a graded research artifact whose own vintage
    the caller must vouch for. Pass `NOT_SUPPLIED` rather than a guess -- the
    rules that need them will say UNEVALUABLE and the board will say so too,
    which is the honest answer and not a failure of this function.

    `model_health` maps metric -> health row. A metric absent from the mapping
    is passed `None`, which the health rules read as "measured nothing about
    this metric" -- distinct from NOT_SUPPLIED, which is "we did not look".
    """
    want = metrics or sorted(f'{a}/{b}' for (a, b) in METRICS.SUPPORTED)
    out = {}
    for m in want:
        key = tuple(m.split('/', 1))
        origin = METRIC_ORIGIN.get(key)
        if origin is None:
            out[m] = {'spec_version': SPEC_VERSION, 'metric': m,
                      'disposition': UNEVALUABLE,
                      'why': 'no producing layer is declared for this metric, '
                             'so no governance state can be routed to it',
                      'findings': []}
            continue
        layer, stage = origin
        mh = (NOT_SUPPLIED if model_health is NOT_SUPPLIED
              else (model_health or {}).get(m))
        ctx = facts_from_run_status(run_status, m, layer, stage=stage,
                                    chronology=chronology, model_health=mh)
        out[m] = decide(ctx)
    return out


# ---------------------------------------------------------------------------
def facts_from_run_status(run_status: Mapping, metric: str, layer: str, *,
                          stage: str | None = None,
                          chronology=NOT_SUPPLIED,
                          model_health=NOT_SUPPLIED,
                          eligibility=NOT_SUPPLIED) -> PublicationContext:
    """Read a sealed `run_status.json` into a context. TRANSPORT, NOT REPAIR.

    Every value is taken from the run or marked NOT_SUPPLIED. Nothing is
    defaulted, derived or improved: if the run did not record a fact, the
    rule that needs it returns UNEVALUABLE and the board says so. The three
    keyword facts are the ones a sealed run does not carry today -- the
    chronology verdicts live in the board's vintage selection, model health in
    a research artifact, and the eligibility row is computed from
    PATH_C_STATE at read time -- so they are supplied by the caller that holds
    them rather than invented here.
    """
    rs = dict(run_status or {})
    stages = {s.get('stage'): s for s in (rs.get('stages') or [])}
    st = stages.get(stage or layer) or {}
    if eligibility is NOT_SUPPLIED:
        try:
            eligibility = ELIG.matrix().get(layer, NOT_SUPPLIED)
        except Exception:                                      # noqa: BLE001
            eligibility = NOT_SUPPLIED
    gov = st.get('governance')
    warns = st.get('warnings_detail')
    if warns is None:
        warns = st.get('warnings')
    dc = rs.get('draw_coherence') or {}
    hard = {}
    for v in (rs.get('accounting_verdicts') or []):
        hard[v.get('invariant')] = {'state': v.get('state'),
                                    'code': v.get('code'),
                                    'class': v.get('class')}
    if dc.get('state') is not None:
        hard['draw_coherence'] = {
            'state': dc.get('state'), 'code': dc.get('code'),
            'class': 'HARD' if dc.get('gating') else 'DIAGNOSTIC'}
    return context(
        run_id=str(rs.get('run_id') or 'UNKNOWN_RUN'),
        metric=metric, layer=layer,
        model_configuration=rs.get('model_configuration', NOT_SUPPLIED),
        chronology=chronology,
        eligibility=eligibility,
        hard_invariants=hard if hard else NOT_SUPPLIED,
        warnings=warns if warns is not None else NOT_SUPPLIED,
        governance=gov if gov is not None else NOT_SUPPLIED,
        completeness=rs.get('completeness', NOT_SUPPLIED),
        model_health=model_health,
        spec_version=(st.get('spec_version')
                      if 'spec_version' in st else NOT_SUPPLIED),
        dry_run=(bool(rs['dry_run']) if 'dry_run' in rs else NOT_SUPPLIED),
        test_only=bool(rs.get('TEST_ONLY')) if 'TEST_ONLY' in rs
        else (False if rs.get('dry_run') is False else NOT_SUPPLIED),
    )
