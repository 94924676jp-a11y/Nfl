"""Seed and refresh `nfl/tests/DETECTORS.json`, the list of detectors OWNER RULE 2 is enforced for.

`python3.12 nfl/tools/detector_manifest.py seed` rebuilds the manifest from SEED below: for each
listed module the refusal codes are read from the module's AST (`Outcome.fail/blocked/...` calls
with a constant code, plus named constants the module flags with), and each is attributed to its
enclosing function. Hand-listed entries (dict-state detectors, flag codes, harness verdicts) are
merged in. Existing entries are kept; the script only adds, so a detector once under the rule
stays under it until a human removes it.

Entry shape: {"detector": "<module>:<function>:<CODE>", "where": "path:line", "kind": "...",
"note": "..."}.
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'nfl' / 'tests' / 'DETECTORS.json'
_REFUSALS = {'fail', 'blocked', 'not_executed', 'incomplete', 'deferred'}

#: modules whose refusal codes are all under the rule, with the AST attributing each to a function
SEED_MODULES = (
    'nfl/tools/sync_captures.py',
    'nfl/product/quality_gates.py',
    'nfl/production/authorization.py',
    'nfl/production/eligibility_gate.py',
    'nfl/production/world_clock.py',
    'nfl/production/coherence_certificate.py',
    'nfl/production/dfs/portfolio_guard.py',
    'nfl/production/nonqb/readiness.py',
    'nfl/production/run_archive.py',
    'nfl/production/adjustment_registry.py',
    'nfl/production/verdict.py',
    'nfl/production/gate_ids.py',
    'nfl/production/qb_accounting.py',
    'nfl/production/joint.py',
    'nfl/production/ownership_audit.py',
    'nfl/production/fixture_assembler.py',
    'nfl/production/derived.py',
    'nfl/prospective/q9shadow/g0a.py',
)

#: detectors whose trip is not an Outcome code: dict states, flag constants, raised refusals,
#: harness verdicts, and `Outcome.measured` whose code is the caller's code + _EMPTY_INPUT.
SEED_HAND = [
    # football sanity gate: flags collected into one FAIL; the flag code is the detector
    *[(f'nfl.tools.football_sanity:assess:{c}', 'nfl/tools/football_sanity.py', 'flag')
      for c in ('STARTER_CARRIES_APPEARANCE_PENALTY', 'RANK1_QB_NOT_PREDICTED_STARTER',
                'CLUB_PASS_ATTEMPTS_NOT_RECONCILED', 'CLUB_CARRIES_NOT_RECONCILED',
                'CLUB_TARGETS_NOT_RECONCILED', 'INACTIVE_PLAYER_HAS_OPPORTUNITY',
                'ROLE_ABOVE_CEILING_WITHOUT_REASON', 'QB_TARGETS_ABOVE_CEILING_WITHOUT_REASON',
                'NON_QB_PASS_ATTEMPTS_ABOVE_CEILING', 'ZERO_WITHOUT_NAMED_STATE',
                'MISSING_INPUT_READ_AS_ZERO', 'KICKER_OR_DST_MISSING', 'FOOTBALL_SANITY_NO_ROWS')],
    ('nfl.tools.football_sanity:measure_draws:DRAWS_DOC_NOT_SUPPLIED', 'nfl/tools/football_sanity.py', 'dict-state'),
    ('nfl.tools.football_sanity:measure_draws:SIMULATOR_OWN_REGRESSION', 'nfl/tools/football_sanity.py', 'dict-state'),
    # non-QB readiness: dict states
    *[(f'nfl.production.nonqb.readiness:team_readiness:{s}', 'nfl/production/nonqb/readiness.py', 'dict-state')
      for s in ('NOT_READY_NO_LEAGUE_REPORT', 'INJURY_REPORT_NOT_YET_FILED', 'INJURY_REPORT_INCOMPLETE',
                'INJURY_REPORT_STALE', 'INJURY_REPORT_CHRONOLOGY_FAILURE', 'READINESS_CLOCK_UNRESOLVED')],
    # lineup integrity: raised LineupRefusal codes
    *[(f'nfl.dfs.lineup_integrity:check:{c}', 'nfl/dfs/lineup_integrity.py', 'raised')
      for c in ('LINEUP_EMPTY', 'LINEUP_WRONG_SIZE', 'LINEUP_CAPTAIN_COUNT')],
    # rule 1: the primitive and the harness
    ('sportsplatform.governance.outcome:Outcome.measured:X_EMPTY_INPUT', 'sportsplatform/governance/outcome.py', 'measured-suffix'),
    ('sportsplatform.governance.outcome:combine:NOT_APPLICABLE', 'sportsplatform/governance/outcome.py', 'state'),
    ('nfl.tests.run_suite:main:NOT_EXECUTED', 'nfl/tests/run_suite.py', 'harness-verdict'),
    ('nfl.tools.suite_progress:summarise:NOT_EXECUTED', 'nfl/tools/suite_progress.py', 'summary-text'),
    # rule 1: dict-returning and measured() sites repaired 2026-10-02
    ('nfl.production.lineage:audit:LINEAGE_AUDIT_NOT_EXECUTED', 'nfl/production/lineage.py', 'dict-state'),
    ('nfl.prospective.q9shadow.injury_completeness:assess:INCOMPLETE_NO_INJURY_ROWS_FOR_SEASON', 'nfl/prospective/q9shadow/injury_completeness.py', 'dict-state'),
    ('nfl.production.run_archive:verify:SEALED_RUN_INTACT_EMPTY_INPUT', 'nfl/production/run_archive.py', 'measured-suffix'),
    ('nfl.production.run_archive:verify_current:CURRENT_MATCHES_ARCHIVE_EMPTY_INPUT', 'nfl/production/run_archive.py', 'measured-suffix'),
    ('nfl.production.adjustment_registry:audit_frame:ADJUSTMENT_LINEAGE_CLEAN_EMPTY_INPUT', 'nfl/production/adjustment_registry.py', 'measured-suffix'),
    ('nfl.production.pipeline:audit_declared_reads:EVERY_VINTAGE_READ_DECLARED_EMPTY_INPUT', 'nfl/production/pipeline.py', 'measured-suffix'),
    ('nfl.production.qb_v1:identity_check:QB_DROPBACK_IDENTITY_HOLDS_EMPTY_INPUT', 'nfl/production/qb_v1.py', 'measured-suffix'),
    ('nfl.production.qb_accounting:reconcile_team_volume:QB_TEAM_VOLUME_COHERENT_EMPTY_INPUT', 'nfl/production/qb_accounting.py', 'measured-suffix'),
    ('nfl.production.fixture_assembler:verify_declared:DECLARED_CAPTURES_VERIFIED_EMPTY_INPUT', 'nfl/production/fixture_assembler.py', 'measured-suffix'),
    ('nfl.production.derived:verify:DERIVED_ARTIFACTS_VERIFIED_EMPTY_INPUT', 'nfl/production/derived.py', 'measured-suffix'),
    ('nfl.production.stat_contract:reconcile_with_product_registry:COUNT_REGISTRY_AGREES_EMPTY_INPUT', 'nfl/production/stat_contract.py', 'measured-suffix'),
    ('nfl.prospective.q9shadow.g0a:check:G0A_CHECKLIST_INCOMPLETE', 'nfl/prospective/q9shadow/g0a.py', 'incomplete'),
]


def _module_name(rel: str) -> str:
    return rel[:-3].replace('/', '.')


def _enclosing(tree: ast.AST):
    """Map every node to its enclosing function name (dotted for methods)."""
    parents = {}
    for node in ast.walk(tree):
        for ch in ast.iter_child_nodes(node):
            parents[ch] = node

    def fn_of(n):
        names = []
        while n is not None:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(n.name)
            n = parents.get(n)
        return '.'.join(reversed(names)) or '<module>'
    return fn_of


def codes_in(rel: str) -> list[tuple[str, str, int]]:
    """(function, CODE, line) for each refusal call with a constant code, or a module constant."""
    p = ROOT / rel
    tree = ast.parse(p.read_text(encoding='utf-8'), rel)
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) \
                and node.value.value.isupper():
            consts[node.targets[0].id] = node.value.value
    fn_of = _enclosing(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr in _REFUSALS
                and isinstance(f.value, ast.Name) and f.value.id == 'Outcome'):
            continue
        a = node.args[0]
        code = a.value if isinstance(a, ast.Constant) and isinstance(a.value, str) else \
            consts.get(a.id) if isinstance(a, ast.Name) else None
        if code and code.isupper():
            out.append((fn_of(node), code, node.lineno))
    return out


def seed() -> dict:
    existing = json.loads(MANIFEST.read_text())['detectors'] if MANIFEST.exists() else []
    by = {d['detector']: d for d in existing}
    for rel in SEED_MODULES:
        for fn, code, line in codes_in(rel):
            if fn == '<module>':
                continue
            key = f'{_module_name(rel)}:{fn}:{code}'
            by.setdefault(key, {'detector': key, 'where': f'{rel}:{line}', 'kind': 'outcome-code'})
    for key, rel, kind in SEED_HAND:
        by.setdefault(key, {'detector': key, 'where': rel, 'kind': kind})
    doc = {'ARTIFACT': 'DETECTORS', 'spec_version': 'detectors-1',
           'RULE': ('OWNER RULE 2 (2026-10-02): every detector listed here must have at least one '
                    'positive control (nfl/tests/_controls.observe / positive_control) that ran '
                    'and tripped under nfl/tests/run_suite.py. Unlisted refusal codes are '
                    'reported by the census in DETECTOR_VALIDATION.json, never ignored.'),
           'n_detectors': len(by),
           'detectors': sorted(by.values(), key=lambda d: d['detector'])}
    MANIFEST.write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n')
    return doc


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['seed']:
        d = seed()
        print(f'{MANIFEST.relative_to(ROOT)}: {d["n_detectors"]} detector(s)')
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main())
