#!/usr/bin/env python3.12
"""Read the external Week-3 research package. Nothing here is availability truth.

The package was frozen at 2026-09-27 11:32 ET, BEFORE official inactives existed.
Its own text says so twice -- `**State:** PRE-INACTIVES` in the header and "official
inactives were unavailable at retrieval" under Limitations -- and its machine-readable
handoff block carries `snapshot.type: PRE_INACTIVES` with
`second_pass.trigger: official_inactives_release`.

So this module is a reader for *context*, and it is deliberately incapable of
producing a confirmed availability state. That job belongs to `availability.py`, which
will not emit CONFIRMED_* without a captured official document.

THE ONE DESIGN DECISION WORTH EXPLAINING. The report states several absences in prose
rather than in its YAML block. I could have typed those names into a list. I have been
wrong doing exactly that before -- a hash abbreviated from memory, a census keyed on a
name that silently dropped duplicates -- so instead every prose claim carries the
literal substring it must match, and the extractor reads the surrounding sentence out
of the preserved file. If the source does not contain the anchor, the claim refuses
with EXTERNAL_CLAIM_NOT_FOUND_IN_SOURCE rather than passing through unverified. A
claim I cannot locate in the artifact is a claim I do not get to make.
"""
from __future__ import annotations

import csv
import hashlib
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'external-research-2026w3-1'

PKG = _REPO / 'nfl/research/external_benchmarks/PERPLEXITY_EARLY_2026W3_PRE_INACTIVES'

REPORT = PKG / 'NFL_Week3_Early_Only_Pre-Inactives_Football-Intelligence_Report.md'
MASTER = PKG / 'master_player_table.csv'
USAGE = PKG / 'player_usage_evidence.csv'
ENVIRON = PKG / 'game_environment.csv'
WATCH = PKG / 'inactives_watchlist.csv'

RETRIEVED_ET = '2026-09-27 11:32 ET'
RETRIEVED_UTC = '2026-09-27T15:32:00Z'
SNAPSHOT_TYPE = 'PRE_INACTIVES'

#: Nothing this module returns may be read as a current availability state.
NOT_AVAILABILITY_TRUTH = (
    'Frozen 2026-09-27 11:32 ET, before official inactives. RotoWire showed "Not Yet '
    'Available" for inactives at retrieval. Every lineup in here is '
    'ROTOWIRE_PREDICTED, every QUESTIONABLE is UNKNOWN_ACTIVE_STATE, and no row in '
    'this package can promote a player to CONFIRMED_ACTIVE or CONFIRMED_INACTIVE.')

# --- prose absence claims -----------------------------------------------------
# (claim_id, player, club_hint, status, anchor). `anchor` must appear verbatim in the
# report or the claim refuses. club_hint is the club the surrounding paragraph is
# about; where the sentence itself does not settle it, it is CLUB_AMBIGUOUS_IN_SOURCE
# and gets resolved by joining to the DK universe, never from recall.
_PROSE_CLAIMS = (
    ('EX-OUT-01', 'Nico Collins', 'HOU', 'REPORTED_OUT',
     'Nico Collins is officially out after DNP all week.'),
    ('EX-OUT-02', 'Alec Pierce', 'IND', 'REPORTED_OUT',
     'Indianapolis is without Pierce and Dulin'),
    ('EX-OUT-03', 'Ashton Dulin', 'IND', 'REPORTED_OUT',
     'Indianapolis is without Pierce and Dulin'),
    ('EX-OUT-04', 'Andrei Iosivas', 'CIN', 'REPORTED_OUT',
     'Iosivas is out/IR'),
    ('EX-OUT-05', 'Rico Dowdle', 'PIT', 'REPORTED_OUT',
     'while Dowdle is out'),
    ('EX-OUT-06', 'Jayden Daniels', 'WAS', 'REPORTED_OUT',
     'Daniels, Okonkwo, Cosmi and Luvu are officially out.'),
    ('EX-OUT-07', 'Chig Okonkwo', 'WAS', 'REPORTED_OUT',
     'Daniels, Okonkwo, Cosmi and Luvu are officially out.'),
    ('EX-OUT-08', 'Cosmi', 'WAS', 'REPORTED_OUT',
     'Daniels, Okonkwo, Cosmi and Luvu are officially out.'),
    ('EX-OUT-09', 'Luvu', 'WAS', 'REPORTED_OUT',
     'Daniels, Okonkwo, Cosmi and Luvu are officially out.'),
    ('EX-OUT-10', 'Mason Taylor', 'CLUB_AMBIGUOUS_IN_SOURCE', 'REPORTED_OUT',
     'Mason Taylor and Minkah Fitzpatrick are out'),
    ('EX-OUT-11', 'Minkah Fitzpatrick', 'CLUB_AMBIGUOUS_IN_SOURCE', 'REPORTED_OUT',
     'Mason Taylor and Minkah Fitzpatrick are out'),
    ('EX-OUT-12', 'Jaxson Dart', 'NYG', 'REPORTED_OUT',
     'Winston replaces injured Jaxson Dart'),
    ('EX-OUT-13', 'Jonathon Brooks', 'CAR', 'REPORTED_OUT_IR',
     'after Jonathon Brooks went to IR'),
    ('EX-DBT-01', 'Jaylen Wright', 'MIA', 'REPORTED_DOUBTFUL',
     'Wright is doubtful after LP/LP/DNP'),
)

# Offensive-line and defensive absences the report states. These never create direct
# fantasy opportunity, which is exactly why they are kept apart from the skill list --
# an OL absence changes team efficiency and pressure, not a target tree.
_NON_SKILL_CLAIMS = (
    ('EX-NS-01', 'Awosika', 'LAC', 'OL_ABSENCE',
     'including Awosika and Pipkins'),
    ('EX-NS-02', 'Pipkins', 'LAC', 'OL_ABSENCE',
     'including Awosika and Pipkins'),
)


def _digest(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _rows(p: pathlib.Path, required: tuple[str, ...]):
    if not p.exists():
        return Outcome.blocked('EXTERNAL_RESEARCH_ABSENT', f'{p.name} is not in the tree',
                       cause=Cause.DATA)
    with p.open(newline='', encoding='utf-8-sig') as fh:
        rows = [r for r in csv.DictReader(fh) if any((v or '').strip()
                                                     for v in r.values())]
    if not rows:
        return Outcome.fail('EXTERNAL_RESEARCH_EMPTY', f'{p.name} parsed to zero rows')
    missing = [c for c in required if c not in rows[0]]
    if missing:
        return Outcome.fail('EXTERNAL_RESEARCH_SCHEMA',
                    f'{p.name} lacks {missing}; columns are {sorted(rows[0])}')
    return Outcome.ok('EXTERNAL_RESEARCH_READ', rows, f'{p.name}: {len(rows)} rows',
              source=p.name, sha256=_digest(p), n_rows=len(rows))


def environment():
    """The nine games with market and implied totals, as the research recorded them."""
    return _rows(ENVIRON, ('game', 'away', 'home', 'spread', 'total',
                           'away_implied', 'home_implied'))


def master_players():
    """Predicted role / availability-detail rows. PREDICTED, never official."""
    return _rows(MASTER, ('player', 'team', 'position', 'predicted_role',
                          'availability', 'availability_detail', 'inactive_trigger',
                          'replacement_if_out', 'last_verified'))


def usage_evidence():
    """The research's own usage table. Our internal observed layer outranks it."""
    return _rows(USAGE, ('player', 'team', 'position', 'w1_targets', 'w2_targets',
                         'w1_carries', 'w2_carries', 'redzone_targets',
                         'goal_line_carries', 'fc_projection_external_only'))


def watchlist():
    """The ten branches the research flagged as unresolved at 11:32 ET."""
    return _rows(WATCH, ('player', 'current_status', 'expected_role_if_active',
                         'redistribution_if_inactive', 'players_most_affected',
                         'source', 'last_verified'))


def report_text():
    if not REPORT.exists():
        return Outcome.blocked('EXTERNAL_RESEARCH_ABSENT', 'report markdown is not in the tree',
                       cause=Cause.DATA)
    txt = REPORT.read_text(encoding='utf-8')
    if len(txt) < 4000:
        return Outcome.fail('EXTERNAL_RESEARCH_EMPTY',
                    f'report is {len(txt)} bytes, too short to be the real document')
    return Outcome.ok('EXTERNAL_RESEARCH_READ', txt, f'report: {len(txt)} bytes',
              source=REPORT.name, sha256=_digest(REPORT))


def _sentence_around(txt: str, anchor: str) -> str | None:
    i = txt.find(anchor)
    if i < 0:
        return None
    lo = max(txt.rfind('\n', 0, i), txt.rfind('. ', 0, i) + 1, 0)
    hi = txt.find('\n', i + len(anchor))
    hi = len(txt) if hi < 0 else hi
    return ' '.join(txt[lo:hi].split())[:400]


def yaml_confirmed_out():
    """Pull `confirmed_out_core` out of the report's own handoff block.

    Read from the file, not typed. The block is the research thread's structured
    statement of what it believes is already resolved.
    """
    r = report_text()
    if r.state is not State.PASS:
        return r
    m = re.search(r'^confirmed_out_core:\s*\n((?:\s*-\s*.+\n)+)', r.value, re.M)
    if not m:
        return Outcome.fail('EXTERNAL_HANDOFF_BLOCK_ABSENT',
                    'report has no confirmed_out_core block; the yaml shape changed')
    names = [ln.strip().lstrip('-').strip() for ln in m.group(1).strip().splitlines()]
    names = [n for n in names if n]
    if not names:
        return Outcome.fail('EXTERNAL_HANDOFF_BLOCK_EMPTY', 'confirmed_out_core parsed empty')
    return Outcome.ok('EXTERNAL_HANDOFF_READ', names, f'{len(names)} names', names=names)


def prose_absence_claims():
    """Every absence the report states, each verified against the preserved bytes.

    Returns claim dicts carrying the quoted sentence. A claim whose anchor is not in
    the file comes back `verified=False` with code EXTERNAL_CLAIM_NOT_FOUND_IN_SOURCE
    and must not be used -- that is the guard against a name I remembered rather than
    read.
    """
    r = report_text()
    if r.state is not State.PASS:
        return r
    txt = r.value
    out = []
    for cid, player, club, status, anchor in _PROSE_CLAIMS + _NON_SKILL_CLAIMS:
        quote = _sentence_around(txt, anchor)
        out.append({
            'claim_id': cid,
            'player_as_written': player,
            'club_hint': club,
            'external_status': status,
            'anchor': anchor,
            'verified_in_source': quote is not None,
            'source_quote': quote,
            'refusal': None if quote else 'EXTERNAL_CLAIM_NOT_FOUND_IN_SOURCE',
            'evidence_tier': 'EXTERNAL_RESEARCH_SECONDHAND',
            'source': REPORT.name,
            'source_sha256': _digest(REPORT),
            'source_timestamp_et': RETRIEVED_ET,
            'is_skill_position_claim': cid.startswith(('EX-OUT', 'EX-DBT')),
        })
    bad = [c['claim_id'] for c in out if not c['verified_in_source']]
    if bad:
        return Outcome.fail('EXTERNAL_CLAIM_NOT_FOUND_IN_SOURCE',
                    f'{len(bad)} claims do not appear in the preserved report: {bad}',
                    unverified=bad, claims=out)
    return Outcome.ok('EXTERNAL_CLAIMS_VERIFIED', out,
              f'{len(out)} absence claims, all located in the source',
              n_claims=len(out))


def provenance():
    """Digests and timestamps for every file in the package."""
    files = {}
    for p in (REPORT, MASTER, USAGE, ENVIRON, WATCH,
              PKG / 'NFL_Week3_Early_Research.xlsx'):
        files[p.name] = {'sha256': _digest(p), 'bytes': p.stat().st_size} \
            if p.exists() else {'sha256': None, 'bytes': None, 'state': 'ABSENT'}
    return {
        'package': str(PKG.relative_to(_REPO)),
        'snapshot_type': SNAPSHOT_TYPE,
        'retrieved_et': RETRIEVED_ET,
        'retrieved_utc': RETRIEVED_UTC,
        'evidence_tier': 'EXTERNAL_RESEARCH_SECONDHAND',
        'NOT_AVAILABILITY_TRUTH': NOT_AVAILABILITY_TRUTH,
        'files': files,
        'xlsx_note': (
            'two xlsx copies were supplied; they are byte-identical '
            '(sha256 5044e515...b784d), so this is one artifact, not two'),
    }


def main() -> int:
    import json
    for name, fn in (('environment', environment), ('master_players', master_players),
                     ('usage_evidence', usage_evidence), ('watchlist', watchlist),
                     ('yaml_confirmed_out', yaml_confirmed_out),
                     ('prose_absence_claims', prose_absence_claims)):
        r = fn()
        n = len(r.value) if r.state is State.PASS else 0
        print(f'{name:24s} {r.state.value:9s} {r.code:38s} n={n}')
    print(json.dumps(provenance(), indent=2)[:900])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
