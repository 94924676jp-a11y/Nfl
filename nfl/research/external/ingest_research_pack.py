#!/usr/bin/env python3.12
"""Ingest the owner's DFS research pack as IMMUTABLE external research, every claim tagged.

    python3.12 nfl/research/external/ingest_research_pack.py

Tags (owner directive 2026-10-05): EMPIRICAL_HISTORICAL_EVIDENCE, EXTERNAL_MODEL_OUTPUT, EXPERT_OPINION,
FIELD_BEHAVIOR_HYPOTHESIS, PRODUCTION_CANDIDATE, PROHIBITED_DIRECT_INPUT. A claim may carry several.
Excerpt tags are rule-based (AUTO_TAGGED, rules in `tag()`); the 26 key-findings rows are tagged by hand.
Every claim carries DIRECT_USE = 'NOT_A_HARD_LINEUP_RULE': historical percentages are hypotheses for the
field/decision layer and are never converted into constraints or football inputs.
"""
from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent / '2026-10-05_owner_pack'
SRC = HERE / 'NFL_DFS_YouTube_Transcript_Evidence.md'

NUM = re.compile(r'\d+(\.\d+)?\s*(%|percent| of \d+| out of \d+| slates| winners| lineups| contests| games)', re.I)
RULES = [
    ('EXTERNAL_MODEL_OUTPUT', re.compile(r'\b(sim|sims|simulat|optimi[sz]er|projection|projected|model)\w*', re.I)),
    ('FIELD_BEHAVIOR_HYPOTHESIS', re.compile(r'\b(field|owned|ownership|chalk|dupe|duplicat|popular|rostered|leverage)\w*', re.I)),
    ('PRODUCTION_CANDIDATE', re.compile(r'\b(geomean|geometric|product ownership|r-?squared|r²|multiplier|guardrail|re-?sim|'
                                        r'contest sim|field sim|ownership sets?|late swap|swap)\b', re.I)),
    ('EXPERT_OPINION', re.compile(r"\b(i think|i like|i would|i'd|i want|i prefer|you should|my |i'm|i don't|i love|i hate)\b", re.I)),
]
#: anything that reads as a player-level projection or a mandatory construction rule is prohibited as a DIRECT input
PROHIBITED = re.compile(r'\b(always|never|rule|must|only play|stay away|fade|lock|projection for|projected for)\b', re.I)

KEY_FINDINGS = [
    ('KF01', 'Optimal CPT by position: WR 33.1%, RB 28%, QB 20.9% across 163 slates (FTA Sports)', ['EMPIRICAL_HISTORICAL_EVIDENCE']),
    ('KF02', 'QB most-rostered CPT but right ~20% of the time (FTA Sports)', ['EMPIRICAL_HISTORICAL_EVIDENCE', 'FIELD_BEHAVIOR_HYPOTHESIS']),
    ('KF03', 'WR most common CPT across game types; RB rarely CPT in 49+ totals (DFS Army)', ['EMPIRICAL_HISTORICAL_EVIDENCE']),
    ('KF04', 'Field 28-35% QB captain vs optimal near 20% (DFS Army)', ['EMPIRICAL_HISTORICAL_EVIDENCE', 'FIELD_BEHAVIOR_HYPOTHESIS']),
    ('KF05', 'QBs 3.5+ pt underdogs: nut captain 3/205, field ~6.5-7% (DFS Army)', ['EMPIRICAL_HISTORICAL_EVIDENCE', 'FIELD_BEHAVIOR_HYPOTHESIS']),
    ('KF06', 'Favorites produce the nut captain 62-75% (DFS Army)', ['EMPIRICAL_HISTORICAL_EVIDENCE']),
    ('KF07', '50 Milly winners 2021: QB CPT 24%, RB 32%, pass catcher ~36%; 7/50 1-5; 8 onslaughts (Adam Newman)', ['EMPIRICAL_HISTORICAL_EVIDENCE']),
    ('KF08', 'Players from favorite (of 6): 1 2.5%, 2 21.5%, 3 34.4%, 4 31.3%, 5 10.4% (FTA)', ['EMPIRICAL_HISTORICAL_EVIDENCE']),
    ('KF09', '5-1 stacks positively leveraged in top-1%; onslaughts very low owned (ETR)', ['EMPIRICAL_HISTORICAL_EVIDENCE', 'FIELD_BEHAVIOR_HYPOTHESIS']),
    ('KF10', 'All 50 Milly winners had >=1 QB; 26% both (Adam Newman)', ['EMPIRICAL_HISTORICAL_EVIDENCE']),
    ('KF11', '~80% of field lineups contain >=1 QB (One Week Season)', ['FIELD_BEHAVIOR_HYPOTHESIS']),
    ('KF12', 'WR CPT + own QB: 85.2% of top-1% vs 77.4% of field (ETR)', ['EMPIRICAL_HISTORICAL_EVIDENCE', 'FIELD_BEHAVIOR_HYPOTHESIS']),
    ('KF13', 'Kicker in 40.5% of nut lineups, DST 31%, K/DST CPT 8.6% (FTA)', ['EMPIRICAL_HISTORICAL_EVIDENCE']),
    ('KF14', 'DST in 47% of winners at totals <=42, 38% average, 21% at 49+ (DFS Army)', ['EMPIRICAL_HISTORICAL_EVIDENCE']),
    ('KF15', '>=1 kicker in 41-46% of winners; rarely two (DFS Army)', ['EMPIRICAL_HISTORICAL_EVIDENCE']),
    ('KF16', '44% of 50 Milly winners had zero K and zero DST (Adam Newman)', ['EMPIRICAL_HISTORICAL_EVIDENCE']),
    ('KF17', 'Salary left: $0 won 7.4%; up to $900 31.3%; $1,000-1,900 22.7% (FTA)', ['EMPIRICAL_HISTORICAL_EVIDENCE', 'PRODUCTION_CANDIDATE']),
    ('KF18', '$49.1K-$50K ~7-way ties; capping $49.4K ~5 (DFS Army)', ['EMPIRICAL_HISTORICAL_EVIDENCE', 'PRODUCTION_CANDIDATE']),
    ('KF19', 'Under 140% total ownership ~10% of wins, ~2 ties; most wins 155-190% (DFS Army)', ['EMPIRICAL_HISTORICAL_EVIDENCE', 'FIELD_BEHAVIOR_HYPOTHESIS']),
    ('KF20', 'DK winner hits the nut ~66%, ~80% in 100K+ fields (DFS Army)', ['EMPIRICAL_HISTORICAL_EVIDENCE']),
    ('KF21', '~28% of optimal captains under 5% owned; 16% over 20% (925 Sports)', ['EMPIRICAL_HISTORICAL_EVIDENCE', 'FIELD_BEHAVIOR_HYPOTHESIS']),
    ('KF22', 'ETR dupe estimate: product of CPT and FLEX ownership x correlation coef (~0.85 stacked) x salary-left multiplier x field size; R2 0.55 vs 0.26 total ownership', ['EXTERNAL_MODEL_OUTPUT', 'PRODUCTION_CANDIDATE']),
    ('KF23', 'SaberSim: expected dupes ~ ownership product x contest size; geomean = product^(1/n); overestimates very low-salary builds; 20-25 dupe guardrail', ['EXTERNAL_MODEL_OUTPUT', 'PRODUCTION_CANDIDATE']),
    ('KF24', 'Independence breaks for correlated pairs (CPT Lamb -> Dak FLEX) (SaberSim)', ['FIELD_BEHAVIOR_HYPOTHESIS', 'PRODUCTION_CANDIDATE']),
    ('KF25', 'Ownership built from thousands of high-variance optimizer builds off an aggregate projection; 13 ownership sets (SaberSim)', ['PRODUCTION_CANDIDATE', 'EXTERNAL_MODEL_OUTPUT']),
    ('KF26', 'Chalk condenses in small fields: 18% large-field CPT -> ~30% single entry (SaberSim)', ['FIELD_BEHAVIOR_HYPOTHESIS', 'PRODUCTION_CANDIDATE']),
]


def tag(text):
    tags = []
    if NUM.search(text):
        tags.append('EMPIRICAL_HISTORICAL_EVIDENCE')
    for t, rx in RULES:
        if rx.search(text):
            tags.append(t)
    if not tags:
        tags.append('EXPERT_OPINION')
    if PROHIBITED.search(text):
        tags.append('PROHIBITED_DIRECT_INPUT')
    return tags


def parse():
    topic = video = source = None
    out, pending = [], None
    for ln in SRC.read_text().splitlines():
        if ln.startswith('## ') and ln[3:4].isdigit():
            topic = ln[3:].strip()
        elif ln.startswith('### ') and topic:
            video = ln[4:].strip()
            source = None
        elif topic and video and source is None and ' · ' in ln:
            source = ln.split(' · ')[0].strip()
        elif topic and ln.startswith('- [') and '](' in ln:
            m = re.match(r'- \[([^\]]+)\]\(([^)]+)\)\s*"(.*)"\s*$', ln)
            if m:
                pending = {'topic': topic, 'video': video, 'source': source, 'timestamp': m.group(1), 'url': m.group(2),
                           'quote': m.group(3)}
                out.append(pending)
        elif pending is not None and ln.strip().startswith('- Takeaway:'):
            pending['takeaway'] = ln.split('Takeaway:', 1)[1].strip()
    return out


def run():
    ex = parse()
    rows = []
    for i, e in enumerate(ex, 1):
        tags = tag(e['quote'] + ' ' + e.get('takeaway', ''))
        rows.append({'claim_id': f'EX{i:03d}', 'topic': e['topic'], 'source': e['source'], 'video': e['video'],
                     'timestamp': e['timestamp'], 'url': e['url'], 'takeaway': e.get('takeaway', ''),
                     'tags': '|'.join(tags), 'tagging': 'AUTO_TAGGED', 'status': 'UNVERIFIED_EXTERNAL',
                     'DIRECT_USE': 'NOT_A_HARD_LINEUP_RULE'})
    for cid, text, tags in KEY_FINDINGS:
        rows.append({'claim_id': cid, 'topic': 'Key findings at a glance', 'source': '', 'video': '', 'timestamp': '',
                     'url': '', 'takeaway': text, 'tags': '|'.join(tags), 'tagging': 'HAND_TAGGED',
                     'status': 'UNVERIFIED_EXTERNAL (vendor data, see the pack caveats)', 'DIRECT_USE': 'NOT_A_HARD_LINEUP_RULE'})
    out = HERE / 'RESEARCH_CLAIMS_TAGGED.csv'
    with out.open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    c = Counter(t for r in rows for t in r['tags'].split('|'))
    summ = {'ARTIFACT': 'RESEARCH_PACK_CLAIMS', 'label': 'EXTERNAL_RESEARCH_SHADOW', 'source_sha256': hashlib.sha256(SRC.read_bytes()).hexdigest(),
            'n_excerpts_parsed': len(ex), 'n_key_findings': len(KEY_FINDINGS), 'tag_counts': dict(c),
            'IMMUTABLE': 'the pack files are stored read-only (0444); this table is derived and regenerable',
            'NOT_A_FOOTBALL_INPUT': True}
    (HERE / 'RESEARCH_CLAIMS_SUMMARY.json').write_text(json.dumps(summ, indent=1))
    return summ


if __name__ == '__main__':
    print(json.dumps(run(), indent=1))
