#!/usr/bin/env python3.12
"""Ingest the 2026-10-05 Ownership / Field / Dupe / Conditional-Role research addendum as IMMUTABLE research.

    python3.12 nfl/research/external/ingest_research_addendum.py

Outputs (derived, regenerable) in nfl/research/external/2026-10-05_addendum/:
  ADDENDUM_CLAIMS_TAGGED.csv     every table row (the addendum's own tag, mapped to the owner taxonomy) and
                                 every verbatim transcript excerpt (rule-tagged as for the first pack)
  METHOD_CANDIDATES.json         the registered PRODUCTION_CANDIDATE methods, tonight's status for each, and
                                 the evidence each needs before promotion
  ADDENDUM_SUMMARY.json

Owner ruling 2026-10-05: ingest without destabilising tonight; these are PRODUCTION_CANDIDATE methods; ownership /
field / dupe run in SHADOW where feasible; the sealed football model is untouched unless a pre-existing correctness
defect is found; promotion requires post-game and multi-slate validation. Nothing here is a hard lineup rule and
nothing here reaches the football projection.
"""
from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from nfl.research.external import ingest_research_pack as P  # noqa: E402

DIR = HERE / '2026-10-05_addendum'
SRC = DIR / 'Ownership_Field_Dupe_Role_Research_Addendum.md'
TAG_MAP = {'HIST': 'EMPIRICAL_HISTORICAL_EVIDENCE', 'EXT-MODEL': 'EXTERNAL_MODEL_OUTPUT', 'EXPERT': 'EXPERT_OPINION',
           'HYPOTHESIS': 'FIELD_BEHAVIOR_HYPOTHESIS', 'CANDIDATE': 'PRODUCTION_CANDIDATE',
           'PROHIBITED': 'PROHIBITED_DIRECT_INPUT'}
SCOPE = {'2': 'OWNERSHIP', '3': 'CONFLICT', '4': 'FIELD', '5': 'DUPLICATION', '6': 'FOOTBALL_ROLE'}
#: markdown link whose URL may itself contain one level of parentheses (e.g. "...(and%20Win).pdf")
LINK = re.compile(r'\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)')

METHOD_CANDIDATES = [
    {'id': 'MC-OWN-1', 'scope': 'OWNERSHIP', 'section': '2.2',
     'method': 'slot-specific (CPT, FLEX), contest-bucket (P150/P20/P2) Dirichlet-multinomial / conditional-logit share '
               'model, Haugh & Singal (2021) form alpha = exp(X beta), p ~ Dir(phi * pi); CPT modelled directly, never 0.5 x FLEX',
     'tonight': 'NOT FITTED -- no Showdown ownership history exists in this repository (one classic slate only); fitting it '
                'tonight would be fitting to nothing. Registered; tonight\'s three Showdown standings are observation #1.',
     'baseline_it_must_beat': 'optimizer-exposure field (nfl/field/showdown_shadow_field.py, FC_ONLY and BLEND)',
     'promotion_requires': 'beats the optimizer-exposure baseline on HELD-OUT slates in log-loss on shares and interval '
                           'coverage, CPT and FLEX separately, per contest bucket; multi-slate; owner ruling'},
    {'id': 'MC-FIELD-1', 'scope': 'FIELD', 'section': '4.2',
     'method': 'archetype-first field generator: team split / QB count / K-DST count / CPT-WR-with-own-QB drawn first, then '
               'slots from Dirichlet-jittered shares, DK legality accept/reject, iterated to slot-ownership targets with '
               'residuals reported',
     'tonight': 'SHADOW -- nfl/field/showdown_archetype_field.py. Archetype priors are NOT fitted on standings (none exist); '
                'they are read from the optimizer field and labelled so; one contest bucket.',
     'promotion_requires': 'reproduces actual slot ownership and archetype rates on held-out standings within a stated '
                           'tolerance better than the optimizer field; multi-slate; owner ruling'},
    {'id': 'MC-DUPE-1', 'scope': 'DUPLICATION', 'section': '5.2',
     'method': 'three estimators per lineup side by side: (1) independent product x N, (2) adjusted product (correlation, '
               'salary-left, construction factors), (3) empirical count in a generated field scaled to N; flag > 2x disagreement',
     'tonight': 'SHADOW -- estimators 1 and 3 computed; estimator 2 carries only the ETR-seeded correlation factors '
                '(CPT WR + own QB x2, CPT QB + opposing DST x0.36), labelled SEEDED_NOT_FITTED; salary-left and construction '
                'factors are 1.0 and labelled NOT_FITTED. Linear scaling from field size to N is stated, not assumed silently.',
     'promotion_requires': 'calibrated against actual duplicate counts in our captured Showdown standings (tonight is the '
                           'first), out of sample; owner ruling'},
    {'id': 'MC-ROLE-1', 'scope': 'FOOTBALL_ROLE', 'section': '6.1',
     'method': 'team volume first -> active-set participation -> role/alignment shares -> target/carry/red-zone allocation, '
               'Dirichlet-multinomial within-team shares over the ACTIVE set; absences act only through the active set; '
               'fitted concentration compared to the 63% median top-beneficiary benchmark (GWTTKB)',
     'tonight': 'NOT IMPLEMENTED -- post-lock candidate. The sealed football model is unchanged tonight (owner ruling); no '
                'pre-existing correctness defect in the current allocation was found that would justify touching it.',
     'promotion_requires': 'forward-chained evaluation on our own play-by-play and participation data against the current '
                           'allocator, preregistered, no DFS or market inputs; owner ruling'},
]
CONFLICTS = [
    {'id': 'CF-1', 'question': 'Does the field over-captain QBs?', 'A': 'DFS Army: field 28-35% QB CPT vs ~20% optimal',
     'B': 'ETR: field makes very few positional CPT mistakes (QB 24.1% of top-1%)',
     'test': 'CPT position share, field vs top 1%, on every captured DK Showdown standings file'},
    {'id': 'CF-2', 'question': 'Product-ownership vs dupes R^2', 'A': '0.55 (ETR video 2022)', 'B': '0.43 (ETR article, current)',
     'test': 'refit on our captured Showdown standings'},
    {'id': 'CF-3', 'question': 'Does CPT ownership drive dupes?', 'A': 'common belief: yes', 'B': 'ETR: minimal correlation',
     'test': 'regress dupe count on CPT ownership vs FLEX product ownership'},
    {'id': 'CF-4', 'question': 'Showdown field size in a sim', 'A': 'SaberSim 5,000 (2023)', 'B': 'SaberSim 20,000 (2024)',
     'test': 'design choice; report sensitivity of our dupe estimates to the generated-field size'},
]


def map_tags(cell):
    tags = [TAG_MAP[t] for t in re.findall(r'HIST|EXT-MODEL|EXPERT|HYPOTHESIS|CANDIDATE|PROHIBITED', cell)]
    return list(dict.fromkeys(tags))


def parse():
    sec = None
    rows, quotes = [], []
    head = video = None
    hdr = []
    for ln in SRC.read_text().splitlines():
        m = re.match(r'^## (\d+)\.', ln)
        if m:
            sec = m.group(1)
            continue
        if sec == '9':
            if ln.startswith('### '):
                head = ln[4:].strip()
            elif ln.startswith('**') and ' — ' in ln:
                video = ln.strip('*').split('**')[0]
            else:
                q = re.match(r'- \[([^\]]+)\]\(([^)]+)\)\s*"(.*)"\s*$', ln)
                if q:
                    quotes.append({'section': '9', 'topic': head, 'video': video, 'timestamp': q.group(1),
                                   'url': q.group(2), 'text': q.group(3)})
            continue
        if ln.startswith('|---') or not ln.startswith('| '):
            continue
        cells = [c.strip() for c in ln.strip().strip('|').split('|')]
        if cells[0] in ('Source', 'Method', 'Item', 'Finding', 'Question'):
            hdr = cells          # each table's own header decides which column is which
            continue
        if sec == '3' or len(cells) < 2:
            continue
        col = {h: i for i, h in enumerate(hdr)}
        si = col.get('Source', 0)
        links = LINK.findall(' '.join(cells))
        text = ' | '.join(LINK.sub(r'\1', c) for i, c in enumerate(cells[:-1]) if i != si)
        rows.append({'section': sec, 'scope': SCOPE.get(sec, ''), 'source': LINK.sub(r'\1', cells[si]),
                     'url': links[0][1] if links else '', 'text': text,
                     'addendum_tag': cells[-1], 'tags': map_tags(cells[-1])})
    return rows, quotes


def run():
    rows, quotes = parse()
    out = []
    for i, r in enumerate(rows, 1):
        tags = r['tags'] or ['EXPERT_OPINION']
        if r['scope'] == 'FOOTBALL_ROLE':
            # football-layer evidence: allowed only into a preregistered football experiment, never tonight
            tags = tags + ['FOOTBALL_LAYER_ONLY']
        out.append({'claim_id': f'AD{i:03d}', 'section': r['section'], 'scope': r['scope'], 'source': r['source'],
                    'url': r['url'], 'text': r['text'], 'addendum_tag': r['addendum_tag'], 'tags': '|'.join(tags),
                    'tagging': 'ADDENDUM_TAG_MAPPED', 'status': 'UNVERIFIED_EXTERNAL',
                    'DIRECT_USE': 'NOT_A_HARD_LINEUP_RULE'})
    for j, q in enumerate(quotes, 1):
        out.append({'claim_id': f'AQ{j:03d}', 'section': '9', 'scope': q['topic'] or '', 'source': q['video'] or '',
                    'url': q['url'], 'text': q['text'], 'addendum_tag': 'VERBATIM_TRANSCRIPT',
                    'tags': '|'.join(P.tag(q['text'])), 'tagging': 'AUTO_TAGGED', 'status': 'UNVERIFIED_EXTERNAL',
                    'DIRECT_USE': 'NOT_A_HARD_LINEUP_RULE'})
    if not rows or not quotes:
        raise SystemExit(f'ADDENDUM_PARSE_EMPTY rows={len(rows)} quotes={len(quotes)}')
    with (DIR / 'ADDENDUM_CLAIMS_TAGGED.csv').open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    (DIR / 'METHOD_CANDIDATES.json').write_text(json.dumps(
        {'ARTIFACT': 'METHOD_CANDIDATES', 'source': SRC.name, 'status_of_all': 'PRODUCTION_CANDIDATE (none promoted)',
         'candidates': METHOD_CANDIDATES, 'conflicts_to_settle_on_our_standings': CONFLICTS,
         'gaps_stated_by_the_addendum': ['no validated public Showdown CPT ownership model',
                                         'no sample-backed salary-left -> dupe function',
                                         'Haugh & Singal coefficients are FanDuel classic 2016-17: the method transfers, '
                                         'the coefficients do not',
                                         'within-game alignment-based transfer rules are expert claims to test on our pbp']},
        indent=1))
    from collections import Counter
    c = Counter(t for r in out for t in r['tags'].split('|'))
    summ = {'ARTIFACT': 'ADDENDUM_CLAIMS', 'label': 'EXTERNAL_RESEARCH_SHADOW',
            'source_sha256': hashlib.sha256(SRC.read_bytes()).hexdigest(), 'n_table_claims': len(rows),
            'n_verbatim_quotes': len(quotes), 'quotes_expected_by_addendum': 92, 'tag_counts': dict(c),
            'by_scope': dict(Counter(r['scope'] for r in out if r['claim_id'].startswith('AD'))),
            'NOT_A_FOOTBALL_INPUT': True}
    (DIR / 'ADDENDUM_SUMMARY.json').write_text(json.dumps(summ, indent=1))
    return summ


if __name__ == '__main__':
    print(json.dumps(run(), indent=1))
