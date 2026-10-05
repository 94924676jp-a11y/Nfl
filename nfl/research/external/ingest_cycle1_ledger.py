#!/usr/bin/env python3.12
"""Ingest the Cycle 1 external research ledger (Perplexity Computer, 2026-10-05) as IMMUTABLE research.

    python3.12 nfl/research/external/ingest_cycle1_ledger.py BUNDLE_INPUTS_DIR

Owner ruling 2026-10-05: the updated handoff bundle is the current external-research authority. Ingest the Cycle 1
ledger and its machine-readable evidence without destabilising tonight; anything requiring a manual DraftKings
export is DEFERRED until the owner has computer access; new ownership/field/dupe methods are SHADOW or
PRODUCTION_CANDIDATE unless already validated (none is).

Stores the bundle's NEW files read-only in nfl/research/external/2026-10-05_cycle1/, maps the files that are
byte-identical to captures already in the repository (no duplicate copies), validates the ledger schema, and writes
an ACTION REGISTER: for every claim, what can be done from the repository now, what waits on an owner export, what is
an owner decision, and what is post-lock football research.
"""
from __future__ import annotations

import collections
import csv
import datetime
import hashlib
import json
import pathlib
import shutil
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
DIR = pathlib.Path(__file__).resolve().parent / '2026-10-05_cycle1'
FIELDS = ['allowed_use', 'claim', 'claim_id', 'claim_tag', 'code_data_availability', 'conflicting_evidence', 'date',
          'falsification', 'features_data', 'format', 'implementation_candidate', 'independence_note', 'layer',
          'limitations', 'method', 'outcome_definition', 'priority', 'quote', 'quote_verified', 'reproducibility',
          'result', 'sample_size', 'site', 'source', 'source_type', 'test_on_our_data', 'time_period', 'topic', 'url',
          'youtube_timestamp']
TAXONOMY = {'EMPIRICAL_HISTORICAL_EVIDENCE', 'EXTERNAL_MODEL_OUTPUT', 'EXPERT_OPINION', 'FIELD_BEHAVIOR_HYPOTHESIS',
            'PRODUCTION_CANDIDATE', 'PROHIBITED_DIRECT_INPUT'}
#: files in the bundle that must already exist in the repository byte for byte (sha256 -> repo path)
KNOWN = {
    'CLAUDE_DIRECTIVE_ATL_NO_2026-10-05.md': 'nfl/research/external/2026-10-05_owner_pack/CLAUDE_DIRECTIVE_ATL_NO_2026-10-05.md',
    'NFL_DFS_YouTube_Transcript_Evidence.md': 'nfl/research/external/2026-10-05_owner_pack/NFL_DFS_YouTube_Transcript_Evidence.md',
    'Ownership_Field_Dupe_Role_Research_Addendum.md': 'nfl/research/external/2026-10-05_addendum/Ownership_Field_Dupe_Role_Research_Addendum.md',
    'DKEntries-2026-10-05T111816.801.csv': 'nfl/dfs/salaries/raw/showdown_atl_no_2026W4/DKEntries_ATL_NO_SHOWDOWN_2026W4.fd0c1faa2271ca66.csv',
    'draftkings_showdown_NFL_2026-week-4_players-2.csv': 'nfl/dfs/salaries/raw/showdown_atl_no_2026W4/THIRDPARTY_FC_showdown_ATL_NO_2026W4_CONTEXT_ONLY.330fdd518c66ea57.csv',
}
NEW = ('NFL_DFS_Research_Program_Cycle1_Ledger.md', 'ledger.jsonl', 'SHA256SUMS')

#: hand-assigned action class per claim (default by layer below). REPO_NOW items are done tonight in SHADOW.
ACTION = {
    'OWN-05': ('REPO_NOW', 'unit test: CPT score = 1.5 x same-world FLEX score (nfl/tests/test_cycle1_checks.py)'),
    'COR-01': ('REPO_NOW', 'correlation recovery on tonight\'s sealed worlds vs the published ranges; validation target only'),
    'COR-02': ('REPO_NOW', 'as COR-01 (FantasyLabs table); validation target only, never an imposed copula'),
    'FC-08': ('REPO_NOW', 'salary-anchored archetype-field SENSITIVITY: share of field lineups >= $49,500 ~90%'),
    'FC-09': ('REPO_NOW', 'second field-side salary anchor (~80% max salary, ~10% $100-200 below); reported beside FC-08'),
    'DATA-04': ('REPO_NOW', 'cross-slate comparison point for shadow CPT/FLEX ownership (a prior ATL Showdown); not a fit'),
    'NEWS-05': ('REPO_NOW', 'every shadow ownership snapshot carries an as_of timestamp and the inputs it reflects'),
    'NEWS-03': ('TONIGHT_SCHEDULED', 'shadow ownership snapshots after the official inactives and near lock'),
    'DATA-01': ('OWNER_MANUAL_EXPORT', 'after lock and after final: export ATL@NO flagship + other Showdown tiers (DK GameCenter, manual)'),
    'DATA-02': ('OWNER_MANUAL_EXPORT', 'PHI@CHI 9/28 (window ~10/8) and PIT@CLE 10/1 (window ~10/11) Showdown CSVs'),
    'DATA-06': ('OWNER_MANUAL_EXPORT', 'PIT@CLE 10/1 CPT/FLEX verification from its DK CSV'),
    'DATA-03': ('OWNER_DECISION', 'stat-api Pro (research-only, single user) after a free-preview cross-check vs our 10/4 CSVs; provenance unknown'),
    'DATA-07': ('OWNER_DECISION', 'ask DFS Hero for export terms'),
    'DATA-10': ('PROHIBITED', 'automates DK collection: schema reference only, never run'),
    'DATA-11': ('CONSTRAINT', 'DK Fair Play: no automation of DK collection, ever'),
    'DATA-12': ('CONSTRAINT', 'stat-api license: no redistribution; enterprise licence if anyone else uses it'),
    'DATA-08': ('NOT_INGESTIBLE', 'in-app only'), 'DATA-09': ('OUT_OF_SCOPE', 'FanDuel'),
    'OWN-03': ('REPO_LATER', 'classic stack mix on the 10/4 standings already captured (cross-format)'),
}


def classify(r):
    if r['claim_id'] in ACTION:
        return ACTION[r['claim_id']]
    lay = r['layer']
    if lay.startswith('football') or lay.startswith('evaluation (diagnostic)'):
        return ('FOOTBALL_RESEARCH_POSTLOCK', 'football-layer research; preregistered, forward-chained; never tonight')
    t = str(r['test_on_our_data'])
    if 'n/a' in t[:5]:
        return ('NO_TEST_ON_OUR_DATA', t[:120])
    if 'archive' in t or 'archived' in t or 'export' in t.lower() or 'capture' in t:
        return ('AWAITS_OWNER_EXPORT_ARCHIVE', t[:160])
    return ('POSTLOCK_CANDIDATE', t[:160])


def run(inputs):
    inputs = pathlib.Path(inputs)
    sums = {l.split()[1]: l.split()[0] for l in (inputs / 'SHA256SUMS').read_text().splitlines() if l.strip()}
    actual = {f: hashlib.sha256((inputs / f).read_bytes()).hexdigest() for f in sums}
    bad = {f for f in sums if sums[f] != actual[f]}
    if bad:
        raise SystemExit(f'BUNDLE_CHECKSUM_MISMATCH {sorted(bad)}')
    identical = {}
    for f, rp in KNOWN.items():
        h = hashlib.sha256((_REPO / rp).read_bytes()).hexdigest()
        identical[f] = {'repo_path': rp, 'identical': h == actual[f], 'sha256': actual[f]}
        if h != actual[f]:
            raise SystemExit(f'BUNDLE_FILE_DIFFERS_FROM_REPO {f}')
    DIR.mkdir(parents=True, exist_ok=True)
    for f in NEW:
        dst = DIR / f
        if dst.exists():
            dst.chmod(0o644)
        shutil.copy2(inputs / f, dst)
        dst.chmod(0o444)
    rows = [json.loads(l) for l in (inputs / 'ledger.jsonl').read_text().splitlines() if l.strip()]
    problems = []
    if len(rows) != 69:
        problems.append(f'expected 69 records, got {len(rows)}')
    ids = [r['claim_id'] for r in rows]
    if len(set(ids)) != len(ids):
        problems.append('duplicate claim_id')
    for r in rows:
        if sorted(r) != sorted(FIELDS):
            problems.append(f"{r['claim_id']}: schema differs")
        if r['claim_tag'] not in TAXONOMY:
            problems.append(f"{r['claim_id']}: tag {r['claim_tag']} outside taxonomy")
        if r['quote_verified'] is not True:
            problems.append(f"{r['claim_id']}: quote_verified={r['quote_verified']}")
    reg = []
    for r in rows:
        a, note = classify(r)
        reg.append({'claim_id': r['claim_id'], 'priority': r['priority'], 'layer': r['layer'], 'claim_tag': r['claim_tag'],
                    'allowed_use': r['allowed_use'], 'action_class': a, 'action': note, 'topic': r['topic'],
                    'DIRECT_USE': 'NOT_A_HARD_LINEUP_RULE'})
    with (DIR / 'CYCLE1_ACTION_REGISTER.csv').open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(reg[0]))
        w.writeheader()
        w.writerows(reg)
    prov = {'ARTIFACT': 'EXTERNAL_RESEARCH_CYCLE1', 'label': 'EXTERNAL_RESEARCH_SHADOW',
            'supplied_by': 'owner upload 2026-10-05 ATL_NO_handoff_bundle.zip',
            'bundle_zip_sha256': '17a0147a2ac381e55f23f5442e531831f656ebc7651c60fde55079c49bdc77c1',
            'captured_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'new_files': {f: actual[f] for f in NEW if f in actual} | {'SHA256SUMS': hashlib.sha256((inputs / 'SHA256SUMS').read_bytes()).hexdigest()},
            'identical_to_repository': identical,
            'standings_identical_to_repository': 'contest-standings-196208416/7/8 CSVs inside the zips are byte-identical to '
                                                 'nfl/postgame/raw/2026W4_standings*/DK_STANDINGS.*.csv (sha256 733e8fd7, e7212baf, ac54fe2a)',
            'MISSING_FROM_BUNDLE': ['ledger.csv (named in the ledger header as a machine-readable copy; not in the bundle; '
                                    'ledger.jsonl is the machine-readable record used)'],
            'OWNER_RULING_2026-10-05': ('current external-research authority; ingest without destabilising tonight; manual DK '
                                        'exports deferred until the owner has computer access; new methods SHADOW or '
                                        'PRODUCTION_CANDIDATE unless validated'),
            'USE': 'evidence, hypotheses, validation targets; NEVER a football-projection input; never a hard lineup rule'}
    (DIR / 'PROVENANCE.json').write_text(json.dumps(prov, indent=1))
    summ = {'ARTIFACT': 'CYCLE1_LEDGER_INGEST', 'n_records': len(rows),
            'by_priority': dict(collections.Counter(r['priority'] for r in rows)),
            'by_tag': dict(collections.Counter(r['claim_tag'] for r in rows)),
            'by_action_class': dict(collections.Counter(x['action_class'] for x in reg)),
            'schema_problems': problems, 'NOT_A_FOOTBALL_INPUT': True}
    (DIR / 'CYCLE1_SUMMARY.json').write_text(json.dumps(summ, indent=1))
    if problems:
        raise SystemExit(f'LEDGER_SCHEMA_PROBLEMS {problems}')
    return summ


if __name__ == '__main__':
    print(json.dumps(run(sys.argv[1]), indent=1))
