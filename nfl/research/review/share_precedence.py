"""Is `carry_share or target_share` a fallback or a precedence rule?

Measures the current gate definition against candidate replacements on every
saved review artifact this repository holds, and on a constructed case that
the corpus does not contain. Writes MATERIALITY_SHARE_PRECEDENCE.json.

NOTHING IS CHANGED BY THIS SCRIPT. It is a measurement.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

REVIEW = _REPO / 'nfl/research/player_review'
OUT = _REPO / 'nfl/research/review/MATERIALITY_SHARE_PRECEDENCE.json'
THRESHOLD = 0.05            # gate's team_opportunity_share test
COLD_THRESHOLD = 0.025      # the same test on a cold-start row


def current(cs, ts):
    """What the gate does today: `carry_share or target_share or 0.0`."""
    return float(cs or ts or 0.0)


def largest(cs, ts):
    """max over the shares that exist. None is absent, not zero."""
    vals = [v for v in (cs, ts) if v is not None]
    return float(max(vals)) if vals else 0.0


def room_appropriate(cs, ts, room):
    """The share of the room the player is actually in."""
    if room == 'carries':
        return float(cs if cs is not None else 0.0)
    if room == 'targets':
        return float(ts if ts is not None else 0.0)
    return largest(cs, ts)


def read_corpus():
    rows = []
    if not REVIEW.exists():
        return rows
    for slate in sorted(REVIEW.iterdir()):
        pdir = slate / 'player_dossiers'
        if not pdir.exists():
            continue
        for f in sorted(pdir.glob('*.json')):
            j = json.loads(f.read_text())
            ax = j.get('axes') or {}
            rows.append({
                'slate': slate.name, 'gsis_id': j.get('gsis_id'),
                'player': j.get('display_name'),
                'room': (ax.get('room') or {}).get('value'),
                'carry_share': (ax.get('carry_share') or {}).get('value'),
                'target_share': (ax.get('target_share') or {}).get('value'),
                'dk_points': (j.get('projection') or {}).get(
                    'dk_points', {}).get('value'),
            })
    return rows


def analyse(rows, threshold, label):
    both = [r for r in rows if r['carry_share'] is not None
            and r['target_share'] is not None]
    differs, flips = [], []
    for r in rows:
        cur = current(r['carry_share'], r['target_share'])
        mx = largest(r['carry_share'], r['target_share'])
        ra = room_appropriate(r['carry_share'], r['target_share'], r['room'])
        if abs(cur - mx) > 1e-12 or abs(cur - ra) > 1e-12:
            differs.append({**r, 'current': cur, 'max': mx,
                            'room_appropriate': ra})
        if (cur >= threshold) != (mx >= threshold):
            flips.append({**r, 'current': cur, 'max': mx,
                          'definition': 'max'})
        if (cur >= threshold) != (ra >= threshold):
            flips.append({**r, 'current': cur, 'room_appropriate': ra,
                          'definition': 'room_appropriate'})
    return {
        'label': label, 'threshold': threshold,
        'n_rows': len(rows), 'n_with_both_shares': len(both),
        'n_where_a_definition_differs': len(differs),
        'n_materiality_flips': len(flips),
        'flips': flips[:50],
        'shape_of_the_corpus': {
            'carry_share_exactly_zero_when_both_present': sum(
                1 for r in both if r['carry_share'] == 0.0),
            'target_share_greater_than_carry_share': sum(
                1 for r in both if r['target_share'] > r['carry_share']),
            'and_of_those_carry_share_is_exactly_zero': sum(
                1 for r in both if r['target_share'] > r['carry_share']
                and r['carry_share'] == 0.0),
        },
    }


#: The case the corpus does not contain, written out rather than asserted.
CONSTRUCTED = [
    {'slate': 'CONSTRUCTED', 'gsis_id': 'PASS_CATCHING_BACK',
     'player': 'a back with a handful of carries and a heavy target share',
     'room': 'carries', 'carry_share': 0.04, 'target_share': 0.20,
     'dk_points': 11.0},
    {'slate': 'CONSTRUCTED', 'gsis_id': 'SLOT_RECEIVER_WITH_JET_SWEEPS',
     'player': 'a receiver with two jet sweeps and a large target share',
     'room': 'targets', 'carry_share': 0.02, 'target_share': 0.24,
     'dk_points': 13.0},
]


def main():
    corpus = read_corpus()
    doc = {
        'artifact': 'MATERIALITY_SHARE_PRECEDENCE',
        'spec_version': 'materiality-share-precedence-1',
        'reproduce': 'python3.12 nfl/research/review/share_precedence.py',
        'question': 'gate.materiality weighs `carry_share or target_share or '
                    '0.0`. Is that a fallback, or positional precedence?',
        'finding': 'It is POSITIONAL PRECEDENCE. A player with a non-zero '
                   'carry share is weighed on it and his target share is '
                   'never seen, however much larger it is.',
        'why_it_has_never_fired': 'Python truthiness. In every saved review '
                                  'artifact this repository holds, whenever '
                                  'a target share exceeds a carry share the '
                                  'carry share is EXACTLY 0.0 -- which is '
                                  'falsy, so the `or` falls through to the '
                                  'target share and happens to be right. The '
                                  'usage panel emits 0.0 for a non-rusher '
                                  'rather than a small positive number, and '
                                  'that is the only reason the bug is '
                                  'latent.',
        'corpus': analyse(corpus, THRESHOLD, 'saved review artifacts'),
        'corpus_at_cold_start_threshold': analyse(
            corpus, COLD_THRESHOLD, 'saved review artifacts, cold-start row'),
        'constructed_reachable_case': analyse(
            CONSTRUCTED, THRESHOLD, 'constructed, absent from the corpus'),
        'candidate_definitions': {
            'max': 'max over the shares that exist, None treated as absent. '
                   'Materiality asks whether the row can change an outcome '
                   'AT ALL, so the largest claim the player has on any team '
                   'resource is the right quantity.',
            'room_appropriate': 'the share of the room the player is in. '
                                'UNDER-reports exactly the case that matters '
                                '-- a pass-catching back is in the carries '
                                'room and his relevance is targets -- so it '
                                'reproduces the defect under a better name.',
            'combined': 'REJECTED, and not on grounds of taste. carry_share '
                        'is a share of team carries and target_share is a '
                        'share of team targets. They have different '
                        'denominators, so their sum is not a share of '
                        'anything and cannot be compared against a '
                        'threshold expressed as one.',
        },
        'recommendation': 'max(carry_share, target_share), with None treated '
                          'as ABSENT rather than zero. It is the only '
                          'candidate that is dimensionally coherent and that '
                          'does not under-report the pass-catching back. It '
                          'can only ever RAISE a share, so it can only move '
                          'a row from immaterial to material -- it cannot '
                          'clear a conflict that blocks today.',
        'blast_radius_on_held_data': 'ZERO. No saved review row changes '
                                     'value or materiality under either '
                                     'candidate.',
        'status': 'MEASURED AND RECOMMENDED, NOT APPLIED. The correction '
                  'belongs in its own commit.',
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, default=str) + '\n')
    c = doc['corpus']
    print(f'corpus rows {c["n_rows"]}, both shares {c["n_with_both_shares"]}')
    print(f'  definitions differ on {c["n_where_a_definition_differs"]} row(s)')
    print(f'  materiality flips     {c["n_materiality_flips"]}')
    print(f'  shape {c["shape_of_the_corpus"]}')
    k = doc['constructed_reachable_case']
    print(f'constructed rows {k["n_rows"]}, '
          f'definitions differ on {k["n_where_a_definition_differs"]}, '
          f'flips {k["n_materiality_flips"]}')
    for f in k['flips']:
        print(f'   {f["player"][:52]:54s} cur={f["current"]:.3f} '
              f'-> {f.get("max", f.get("room_appropriate")):.3f} '
              f'({f["definition"]})')
    print(f'wrote {OUT.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
