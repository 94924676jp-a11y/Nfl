"""Read-only audit: which football adjustments does production actually apply?

WHY A SCANNER AND NOT A TABLE

`SINGLE_ADJUSTMENT_OWNERSHIP` is the claim that every adjustment the system
applies is routed through `adjustment_registry`. That claim is about the whole
production tree, so it cannot be established by reading the registry -- the
registry only says what has been DECLARED. Two of its own declarations were
wrong when they were checked by running them, and a third is corrected by this
audit, so a hand-written inventory is not evidence either.

This module scans, and it is re-runnable, so the claim can be re-established
after any change rather than inherited from a previous return.

WHAT IT READS, AND WHY THAT IS THE AST

Every file is parsed and the audit looks at NAMES, ATTRIBUTES and STRING
CONSTANTS -- not raw text. A token that appears only in a comment or a
docstring therefore cannot produce a hit. That matters here: a plain-text grep
for `pace` matches `namespace` 30 times in this tree and finds no pace model,
and a grep for `coverage` matches interval coverage and partial player
coverage 40 times and finds no defensive coverage.

WHAT IT CANNOT DO, STATED PLAINLY

A scanner sees syntax. An adjustment applied through a variable named `k`,
read from a config file at runtime, or buried in a fitted artifact's
coefficients is invisible to it. This audit can therefore DISPROVE
`SINGLE_ADJUSTMENT_OWNERSHIP` and can only SUPPORT it, never prove it. The
verdict it emits says which of those it is.

NOTHING IS PATCHED HERE. The audit reports; it does not repair.
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import adjustment_registry as AR                # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'nfl-ownership-audit-1'

#: EVERY package on the production path, not just `nfl/production`.
#:
#: The first version scanned `nfl/production` alone and reported nine clean
#: NOT_IMPLEMENTED verdicts. `nfl/production` imports `nfl.product`,
#: `nfl.capture`, `nfl.prospective`, `nfl.identity` and `nfl.accounting`, so a
#: roof factor applied in any of those would have been reported as absent. The
#: scan now covers all of `nfl/` and EXCLUDES only the three trees where these
#: quantities are allowed to appear:
#:
#:   nfl/research  -- a research module is SUPPOSED to compute an opponent
#:                    adjustment; that is what RESEARCH_ONLY means;
#:   nfl/tests     -- a test that names a field is testing, not applying;
#:   nfl/tools     -- one-off operator scripts, outside any forecast.
#:
#: Erring toward over-inclusion is deliberate. A module wrongly scanned shows
#: up as an inspectable site; a module wrongly skipped shows up as nothing.
SCAN_ROOT = 'nfl'
SCAN_EXCLUDED = ('nfl/research', 'nfl/tests', 'nfl/tools')
SCAN_ROOTS = (SCAN_ROOT,)

REGISTERED_AND_ENFORCED = 'REGISTERED_AND_ENFORCED'
REGISTERED_BUT_BYPASSED = 'REGISTERED_BUT_BYPASSED'
NOT_REGISTERED = 'NOT_REGISTERED'
NOT_IMPLEMENTED = 'NOT_IMPLEMENTED'

#: What each adjustment would have to READ to be applied at all. These are
#: source-data field names and model-artifact keys, not English words, because
#: an English word matches prose and a field name matches football.
#:
#: `evidence_of_application` is the honest question: if this effect were being
#: applied, at least one of these identifiers would appear in the parsed code
#: of some production module. Absence of all of them is evidence of absence in
#: a way that absence of an English word is not.
FAMILIES = {
    'opponent_pass_strength_v1': {
        'display': 'opponent strength (pass)',
        'fields': ('opponent_strength', 'opp_strength', 'theta_off', 'theta_def',
                   'oas1', 'opponent_adjustment', 'def_adj', 'dvoa',
                   'strength_of_schedule', 'sos'),
        'note': 'the `opponent` key in team_volume_v1 is the PAIRED team-game '
                'lookup for the A3G copula correlation -- a dependence '
                'parameter, not a location shift. It moves no mean.',
    },
    'opponent_rush_strength_v1': {
        'display': 'opponent strength (rush)',
        'fields': ('opponent_strength', 'opp_strength', 'theta_off', 'theta_def',
                   'oas1', 'opponent_adjustment', 'def_adj', 'dvoa',
                   'strength_of_schedule', 'sos'),
        'note': 'same lookup, same conclusion.',
    },
    'pace_v1': {
        'display': 'pace / tempo',
        'fields': ('pace', 'tempo', 'sec_per_play', 'seconds_per_play',
                   'neutral_pace', 'plays_per_game', 'situation_neutral_pace'),
        'note': 'tempo is EMBEDDED in the team snap and dropback levels '
                'team_volume_v1 draws from own history. It is never applied '
                'as a discrete step, which is why nothing consults the '
                'registry about it -- and equally why a future layer that '
                'multiplied a pace factor onto those levels would be counting '
                'the same tempo twice.',
    },
    'game_environment_v1': {
        'display': 'game environment (roof / surface)',
        'fields': ('roof', 'surface', 'stadium_id', 'dome', 'retractable',
                   'turf', 'indoor'),
        'note': 'the production stage NAMED `team_environment` calls '
                'TV.forecast and passes it (season, week, teams, m, seed, '
                'joint_residuals, game_pairs, game_coupling). No roof, no '
                'surface, no stadium. The stage name is a label, not a '
                'football input.',
    },
    'score_state_v1': {
        'display': 'score state / game script',
        'fields': ('score_differential', 'score_diff', 'game_script',
                   'win_probability', 'wp', 'vegas_wp', 'garbage_time',
                   'lead_state'),
        'note': 'the `trailing` hits in this tree are trailing MEANS over '
                'time, not trailing on the scoreboard.',
    },
    'weather_v1': {
        'display': 'weather',
        'fields': ('temp', 'wind', 'weather', 'humidity', 'precipitation',
                   'wind_speed'),
        'note': 'temp and wind are quarantined POSTHOC in the ingest '
                'allowlist: they are the observed game-time conditions.',
    },
    'ol_pass_protection_v1': {
        'display': 'OL / pass protection',
        'fields': ('was_pressure', 'pressure_rate', 'time_to_throw',
                   'number_of_pass_rushers', 'sack_rate_allowed',
                   'pass_block_win', 'pressure'),
        'note': 'was_pressure is 404 for 2026 and publishes after the '
                'postseason.',
    },
    'run_blocking_v1': {
        'display': 'run blocking',
        'fields': ('defenders_in_box', 'box_count', 'yards_before_contact',
                   'run_block_win', 'adjusted_line_yards'),
        'note': 'box counts are FTN charting, the thinnest evidence in the '
                'hierarchy.',
    },
    'coverage_v1': {
        'display': 'defensive coverage',
        'fields': ('defense_coverage_type', 'defense_man_zone_type',
                   'man_rate', 'zone_rate', 'shadow_corner', 'cb_shadow'),
        'note': 'every `coverage` token in this tree is interval coverage or '
                'data coverage. Defensive coverage appears nowhere.',
    },
}

#: The registry API. A module that applies an adjustment is expected to call
#: one of these; a module that calls none of them and still applies one is the
#: bypass this audit is looking for.
#: A HIT IS NOT AN APPLICATION, and conflating the two is how this audit
#: would produce its own false green -- in the opposite direction from the
#: first one. Nine families came back REGISTERED_BUT_BYPASSED on the widened
#: scan and not one of them was applying anything: the hits were a captured
#: source's comma-joined column header, a quarantine list naming the fields it
#: REFUSES, and English prose sitting inside string constants.
#:
#: Sites are therefore classified before they are counted.
PROSE = 'PROSE'                      # the token is natural language
SCHEMA_LIST = 'SCHEMA_LIST'          # a comma-joined column header
ACQUISITION_OR_GUARD = 'ACQUISITION_OR_GUARD'   # capture / ingest / quarantine
APPLICATION_CANDIDATE = 'APPLICATION_CANDIDATE'  # a forecast layer, reviewable

#: Layers that ACQUIRE or REFUSE data rather than forecast with it. A field
#: name here is a column being fetched or a column being quarantined; neither
#: moves a projection. Naming them is a declaration, and it is auditable: if a
#: forecast ever moves into one of these packages this list is wrong and has
#: to be changed deliberately.
ACQUISITION_PACKAGES = ('nfl/capture/', 'nfl/ingest/', 'nfl/parse/',
                        'nfl/schema/', 'nfl/vintage/', 'nfl/adapters/')

REGISTRY_CALLS = ('assert_may_apply', 'assert_consumer', 'audit_frame')

_WORD = re.compile(r'[A-Z]+(?![a-z])|[A-Z][a-z]*|[a-z]+|[0-9]+')


def components(token: str):
    """`pace_factor` -> ['pace', 'factor'], `namespace` -> ['namespace'].

    MATCHING ON COMPONENTS, NOT SUBSTRINGS, AND NOT ON EXACT EQUALITY EITHER.

    Exact equality was the first attempt and the control caught it: a module
    that multiplied volume by `pace_factor` produced NO hit, because
    `pace_factor` is not the string `pace`. Every family then came back
    NOT_IMPLEMENTED, which would have been reported as a finding about this
    repository when it was a fact about the matcher.

    Substring matching is the other failure: `pace` is inside `namespace`
    thirty times in this tree and inside no pace model at all.

    Components give the behaviour actually wanted -- `pace_factor` and
    `neutralPace` hit, `namespace` does not -- and a multi-word field such as
    `defense_coverage_type` requires all three words in order, so interval
    coverage and partial player coverage stay quiet.

    This OVER-detects by design: a field like `temp` matches `temp_dir`. A
    false positive is visible in the reported identifiers and can be dismissed
    by reading it. A false negative is a bypass reported as clean.
    """
    out = []
    for part in re.split(r'[^0-9A-Za-z]+', token):
        if part:
            out.extend(m.group(0).lower() for m in _WORD.finditer(part))
    return out


def field_matches(field: str, token: str) -> bool:
    f, c = components(field), components(token)
    if not f or len(f) > len(c):
        return False
    return any(c[i:i + len(f)] == f for i in range(len(c) - len(f) + 1))


def match_fields(fields, tokens):
    """Every (field, token) pair where the field's words appear in the token."""
    hits = {}
    for tok in tokens:
        for f in fields:
            if field_matches(f, tok):
                hits.setdefault(f, set()).add(tok)
    return {f: sorted(v) for f, v in sorted(hits.items())}
REGISTRY_MODULE = 'adjustment_registry'
LINEAGE_KEYS = ('adjustment_lineage', 'adjustment_tags', 'frame_tags')


#: EVERY APPLICATION_CANDIDATE MUST HAVE A READ DISPOSITION HERE, or the
#: audit refuses. That is the point: a new candidate site appearing in a later
#: commit turns this audit RED until somebody opens the file and writes down
#: what they found. A snapshot would go quietly stale instead.
#:
#: `APPLIED` is the only disposition that makes a family count as implemented.
DISPOSITIONS = {
    ('game_environment_v1', 'nfl/prospective/q9shadow/seal.py'): {
        'verdict': 'CARRIED_NOT_CONSUMED',
        'evidence': 'seal.py:118-120 lists roof, surface and stadium_id in '
                    'SCHEDULE_PREGAME_COLUMNS, and seal.py:216 projects each '
                    'schedule row onto exactly those columns. The only two '
                    'projected fields any later line reads are `gameday` and '
                    '`gametime`, used at :233-:240 to compute kickoff_utc. '
                    'roof, surface and stadium_id are carried into the sealed '
                    'row as metadata and never read again -- grep for each in '
                    'this package returns only the declaration, the '
                    'projection and the leak check at :248.',
    },
}

# THE GATE FIRED ON THE NEXT FILE WRITTEN AFTER IT WAS BUILT, which is the
# behaviour wanted. `gate_ids.py` names WEEK2_OAS1_* and IN_SEASON_PRESSURE_DATA
# and so matched `oas1` and `pressure`; it declares gate STATES and applies
# nothing. Recorded rather than excluded by a rule, because a rule that skipped
# `nfl/production/*_ids.py` would skip the next real applier that happened to
# be named that way.
for _aid in ('opponent_pass_strength_v1', 'opponent_rush_strength_v1',
             'ol_pass_protection_v1'):
    DISPOSITIONS[(_aid, 'nfl/production/gate_ids.py')] = {
        'verdict': 'DECLARATION_NOT_APPLICATION',
        'evidence': 'gate_ids.py holds gate identifiers and their YES/NO/'
                    'UNDECIDED states. The matched tokens are the gate names '
                    'WEEK2_OAS1_FIT_SPEC_READY, WEEK2_OAS1_PREFLIGHT_READY, '
                    'WEEK2_OAS1_FIT_EXECUTABLE, WEEK2_OAS1_DOWNSTREAM_LAWFUL '
                    'and IN_SEASON_PRESSURE_DATA. No arithmetic, no estimate, '
                    'no frame: the module imports only Outcome.',
    }
del _aid


class _Scan(ast.NodeVisitor):
    """Names, attributes and non-docstring string constants. Comments cannot
    reach here: they are not in the tree."""

    def __init__(self):
        self.names, self.strings, self.binop_operands = set(), set(), set()
        self._docstrings = set()

    def _note_doc(self, node):
        b = getattr(node, 'body', None)
        if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) \
                and isinstance(b[0].value.value, str):
            self._docstrings.add(id(b[0].value))

    def visit_Module(self, n):
        self._note_doc(n)
        self.generic_visit(n)

    def visit_FunctionDef(self, n):
        # THE DEFINITION NAME COUNTS. A function called
        # `apply_pace_adjustment` is exactly what this audit is looking for,
        # and a def name is not a Name node, so without this line the most
        # obvious bypass of all would be invisible.
        self.names.add(n.name)
        self._note_doc(n)
        self.generic_visit(n)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, n):
        self.names.add(n.name)
        self._note_doc(n)
        self.generic_visit(n)

    def visit_Name(self, n):
        self.names.add(n.id)
        self.generic_visit(n)

    def visit_Attribute(self, n):
        self.names.add(n.attr)
        self.generic_visit(n)

    def visit_arg(self, n):
        self.names.add(n.arg)
        self.generic_visit(n)

    def visit_keyword(self, n):
        if n.arg:
            self.names.add(n.arg)
        self.generic_visit(n)

    def visit_Constant(self, n):
        if isinstance(n.value, str) and id(n) not in self._docstrings:
            self.strings.add(n.value)
        self.generic_visit(n)

    def visit_BinOp(self, n):
        # A DIRECT ARITHMETIC APPLICATION: `x = base * pace_factor`. Either
        # operand naming a family field is what makes this a candidate bypass.
        for side in (n.left, n.right):
            for sub in ast.walk(side):
                if isinstance(sub, ast.Name):
                    self.binop_operands.add(sub.id)
                elif isinstance(sub, ast.Attribute):
                    self.binop_operands.add(sub.attr)
                elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    self.binop_operands.add(sub.value)
        self.generic_visit(n)


def scan_source(src: str, label: str = '<string>') -> dict:
    """Parse one module. Exposed so a CONTROL can be scanned the same way."""
    tree = ast.parse(src, filename=label)
    s = _Scan()
    s.visit(tree)
    tokens = s.names | s.strings
    calls_registry = (REGISTRY_MODULE in tokens
                      or any(c in tokens for c in REGISTRY_CALLS))
    return {'tokens': tokens, 'binop_operands': s.binop_operands,
            'calls_registry': calls_registry,
            'propagates_lineage': any(k in tokens for k in LINEAGE_KEYS)}


def _classify(relpath: str, hits) -> str:
    """What KIND of site is this? See the constants above."""
    toks = [t for v in hits.values() for t in v]
    # PROSE IS TESTED FIRST. A comma-joined column header has no spaces, so
    # ordering these the other way round labelled two English sentences
    # SCHEMA_LIST purely because they contained a comma.
    if all(' ' in t for t in toks):
        return PROSE
    if all(',' in t for t in toks):
        return SCHEMA_LIST
    if any(relpath.startswith(pkg) for pkg in ACQUISITION_PACKAGES):
        return ACQUISITION_OR_GUARD
    # Mixed prose and identifiers: the identifiers decide.
    if not [t for t in toks if ' ' not in t and ',' not in t]:
        return PROSE
    return APPLICATION_CANDIDATE


def _files():
    out = []
    base = _REPO / SCAN_ROOT
    for p in sorted(base.rglob('*.py')):
        if '__pycache__' in p.parts:
            continue
        rel = str(p.relative_to(_REPO))
        if any(rel.startswith(x + '/') for x in SCAN_EXCLUDED):
            continue
        if p.name in ('adjustment_registry.py', 'ownership_audit.py'):
            continue              # the registry is not its own consumer
        out.append(p)
    return out


def audit() -> Outcome:
    files = _files()
    if not files:
        return Outcome.blocked(
            'OWNERSHIP_AUDIT_NO_FILES',
            f'no production modules found under {SCAN_ROOTS}. An empty scan '
            f'is not a clean scan.', cause=Cause.ENVIRONMENT)
    per_file = {}
    for p in files:
        try:
            per_file[str(p.relative_to(_REPO))] = scan_source(
                p.read_text(), str(p))
        except SyntaxError as e:
            return Outcome.fail(
                'OWNERSHIP_AUDIT_UNPARSEABLE',
                f'{p}: {e}. A module the audit cannot parse is a module the '
                f'audit cannot clear.', cause=Cause.DEPENDENCY)
    rows, registry_callers = {}, sorted(
        f for f, s in per_file.items() if s['calls_registry'])
    unreviewed = []
    for aid, fam in FAMILIES.items():
        fields = set(fam['fields'])
        sites, arith = [], []
        for f, s in per_file.items():
            hit = match_fields(fields, s['tokens'])
            if hit:
                kind = _classify(f, hit)
                site = {'file': f, 'identifiers': hit, 'kind': kind,
                        'calls_registry': s['calls_registry'],
                        'propagates_lineage': s['propagates_lineage']}
                if kind == APPLICATION_CANDIDATE:
                    d = DISPOSITIONS.get((aid, f))
                    if d is None:
                        unreviewed.append({'adjustment_id': aid, 'file': f,
                                           'identifiers': hit})
                    site['disposition'] = (d or {}).get('verdict')
                    site['disposition_evidence'] = (d or {}).get('evidence')
                sites.append(site)
            ah = match_fields(fields, s['binop_operands'])
            if ah:
                arith.append({'file': f, 'operands': ah,
                              'calls_registry': s['calls_registry']})
        registered = aid in AR.ADJUSTMENTS
        # ONLY A SITE READ AND FOUND TO APPLY THE EFFECT COUNTS.
        applying = [s for s in sites
                    if s.get('disposition') == 'APPLIED']
        if not registered and applying:
            state = NOT_REGISTERED
        elif not applying:
            state = NOT_IMPLEMENTED if registered else NOT_REGISTERED
        elif all(s['calls_registry'] for s in applying):
            state = REGISTERED_AND_ENFORCED
        else:
            state = REGISTERED_BUT_BYPASSED
        rows[aid] = {
            'display': fam['display'], 'registered': registered,
            'status_in_registry': (AR.ADJUSTMENTS[aid]['status']
                                   if registered else None),
            'owner': (AR.ADJUSTMENTS[aid]['owner'] if registered else None),
            'applied_at': (AR.ADJUSTMENTS[aid]['applied_at']
                           if registered else None),
            'production_sites': sites, 'n_sites': len(sites),
            'n_application_candidates': sum(
                1 for s in sites if s['kind'] == APPLICATION_CANDIDATE),
            'n_applying': len(applying),
            'site_kinds': sorted({s['kind'] for s in sites}),
            'direct_arithmetic_bypasses': arith,
            'lineage_propagated': any(s['propagates_lineage'] for s in sites),
            'audit_state': state, 'note': fam['note'],
        }
    # AN ADJUSTMENT THE REGISTRY DECLARES BUT THIS AUDIT DOES NOT COVER is a
    # hole in the audit, not a clean result, so it is named.
    uncovered = sorted(set(AR.ADJUSTMENTS) - set(FAMILIES))
    implemented = [a for a, r in rows.items() if r['n_applying']]
    enforced = [a for a in implemented
                if rows[a]['audit_state'] == REGISTERED_AND_ENFORCED]
    ownership_verified = (bool(implemented)
                          and len(enforced) == len(implemented)
                          and not uncovered and not unreviewed)
    if unreviewed:
        return Outcome.fail(
            'OWNERSHIP_AUDIT_UNREVIEWED_SITE',
            f'{len(unreviewed)} application-candidate site(s) have no read '
            f'disposition: '
            f'{[(u["adjustment_id"], u["file"]) for u in unreviewed]}. A site '
            f'nobody has opened is not a clean site. Read it and record what '
            f'it does in DISPOSITIONS.',
            cause=Cause.GOVERNANCE, spec_version=SPEC_VERSION,
            unreviewed=unreviewed)
    ev = {'spec_version': SPEC_VERSION, 'scan_roots': list(SCAN_ROOTS),
          'scan_excluded': list(SCAN_EXCLUDED),
          'n_files_scanned': len(files), 'rows': rows,
          'registry_callers_in_production': registry_callers,
          'adjustments_not_covered_by_this_audit': uncovered,
          'n_implemented_in_production': len(implemented),
          'unreviewed_application_candidates': unreviewed,
          'dispositions': {f'{k[0]}|{k[1]}': v for k, v in DISPOSITIONS.items()},
          'n_enforced': len(enforced),
          'single_adjustment_ownership_verified': ownership_verified,
          'audit_can_only_disprove': (
              'a scanner sees syntax. An adjustment applied through an opaque '
              'variable, a runtime config or a fitted coefficient is invisible '
              'to it, so a clean scan SUPPORTS the claim and never proves it.')}
    return Outcome.ok(
        'OWNERSHIP_AUDIT_COMPLETE', value=rows,
        detail=f'{len(files)} production module(s); {len(implemented)} of '
               f'{len(rows)} adjustment families implemented; '
               f'{len(enforced)} enforced through the registry',
        **ev)


def main() -> int:
    o = audit()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        return 1
    w = max(len(a) for a in o.value)
    for aid, r in o.value.items():
        print(f'  {aid:{w}s}  {r["audit_state"]:24s} '
              f'hits={r["n_sites"]:<2d} candidates='
              f'{r["n_application_candidates"]:<2d} applying={r["n_applying"]:<2d} '
              f'kinds={",".join(k[:4] for k in r["site_kinds"]) or "-"}')
    print()
    print('registry callers in production: '
          f'{o.evidence["registry_callers_in_production"] or "NONE"}')
    print('SINGLE_ADJUSTMENT_OWNERSHIP verified: '
          f'{o.evidence["single_adjustment_ownership_verified"]}')
    out = _REPO / 'nfl/production/OWNERSHIP_AUDIT.json'
    out.write_text(json.dumps(
        {'spec_version': SPEC_VERSION, 'code': o.code, 'detail': o.detail,
         **{k: v for k, v in o.evidence.items() if k != 'cause'}},
        indent=1, sort_keys=True, default=str))
    print(f'wrote {out.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
