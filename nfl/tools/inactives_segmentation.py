#!/usr/bin/env python3.12
r"""Turn a delivered inactives package into the two sidecars ingestion wants.

    python3.12 nfl/tools/inactives_segmentation.py \
        --games /path/to/games.json --bytes /path/to/OFFICIAL.html \
        --out-dir /path/to/sidecars

Emits, per game, `names_<GAME>.json` ({TEAM: [name, ...]}) and
`positions_<GAME>.json` ({TEAM: {name: POSITION}}).

WHY BOTH, AND WHY THEY ARE DIFFERENT KINDS OF THING

`--names-json` supplies SEGMENTATION: which club each name belongs to. Every
name is checked back against the stored authoritative bytes, so it supplies no
information the document does not already contain -- and this tool refuses any
name it cannot find verbatim in those bytes rather than passing it on.

`--positions-json` supplies the position the SOURCE printed, and it is used for
exactly one decision downstream: whether an unresolved name could affect the
quarterback room. It never resolves an identity, never invents a roster id and
never satisfies non-QB completeness.

A trailing parenthetical such as "(emergency third QB)" is preserved as an
annotation and is NOT read as a position. An emergency third quarterback is a
quarterback whose designation carries extra meaning, and inventing status
semantics from a parenthetical is exactly the thing this project refuses to do.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import qb_allocation as QA               # noqa: E402

# The leading tokens the official reports use. Exactly the vocabulary the
# ownership verdict knows, so a position this tool emits is always one that
# classifies, and anything else is left for a human to look at.
POSITIONS = frozenset(QA.QB_POSITION_TOKENS | QA.KNOWN_NON_QB_POSITIONS)


def split_entry(entry: str):
    """'QB Taylen Green (emergency third QB)' -> ('Taylen Green', 'QB', note)"""
    ann = None
    m = re.search(r'\(([^)]*)\)\s*$', entry)
    text = entry[:m.start()].strip() if m else entry.strip()
    if m:
        ann = m.group(1)
    toks, pos = text.split(), []
    while toks and toks[0].upper() in POSITIONS:
        pos.append(toks.pop(0).upper())
    name = ' '.join(toks)
    if not pos:
        return name, None, ann
    if len(pos) > 1:
        return name, '/'.join(pos), ann          # ambiguous, and says so
    return name, pos[0], ann


def main(argv=None):
    ap = argparse.ArgumentParser(description='inactives segmentation sidecars')
    ap.add_argument('--games', required=True)
    ap.add_argument('--bytes', required=True,
                    help='the authoritative document every name is checked '
                         'against')
    ap.add_argument('--out-dir', required=True)
    a = ap.parse_args(argv)

    html = pathlib.Path(a.bytes).read_text(errors='replace')
    games = json.loads(pathlib.Path(a.games).read_text())
    out = pathlib.Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    total, problems, annotations = 0, [], {}
    for g in games:
        gid = g.get('game_id')
        names, positions = {}, {}
        for club, entries in (g.get('inactive_lists') or {}).items():
            names[club], positions[club] = [], {}
            for e in entries:
                nm, pos, ann = split_entry(e)
                if not nm or nm not in html:
                    problems.append({'game': gid, 'club': club, 'entry': e,
                                     'extracted': nm,
                                     'reason': 'NOT_VERBATIM_IN_THE_BYTES'})
                    continue
                names[club].append(nm)
                positions[club][nm] = pos
                total += 1
                if ann:
                    annotations.setdefault(gid, {}).setdefault(
                        club, {})[nm] = ann
        (out / f'names_{gid}.json').write_text(json.dumps(names, indent=1))
        (out / f'positions_{gid}.json').write_text(
            json.dumps(positions, indent=1))
        print(f'{gid}: ' + ', '.join(f'{c}={len(v)}' for c, v in names.items()))
    (out / 'annotations.json').write_text(json.dumps(annotations, indent=1))
    print(f'\n{total} name(s) verified verbatim in the authoritative bytes')
    if annotations:
        print(f'{sum(len(v) for c in annotations.values() for v in c.values())}'
              f' annotation(s) preserved, none read as a position:')
        print(' ', json.dumps(annotations))
    if problems:
        print(f'\nREFUSED {len(problems)}:')
        for p in problems:
            print('  ', json.dumps(p))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
