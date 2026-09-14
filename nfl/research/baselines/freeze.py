"""Build the panel, derive the constants, and WRITE THE FROZEN SPEC.

Run this once. `evaluate.py` then reads what this wrote and refuses to run if
any hash in it has moved. Re-running this after an evaluation would destroy the
only property the freeze exists to provide, so it refuses to overwrite an
existing spec unless `--refreeze` is passed and says so out loud.

    python3.12 -m nfl.research.baselines.freeze
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

from nfl.research.baselines import frame as F        # noqa: E402
from nfl.research.baselines import panel as P        # noqa: E402
from nfl.research.baselines import specs as S        # noqa: E402


def all_frames(idx):
    """quantity -> season -> FRAME_A rows, for every lawful season."""
    out = {}
    for q in F.QUANTITY_POSITIONS:
        out[q] = {s: idx.frame_a(q, (s,)) for s in P.LAWFUL_SEASONS}
    for q in F.TEAM_QUANTITIES:
        out[q] = {s: idx.team_frame(q, (s,)) for s in P.LAWFUL_SEASONS}
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if os.path.exists(S.SPEC_PATH) and '--refreeze' not in argv:
        print(f'BASELINE_SPEC_ALREADY_FROZEN {S.SPEC_PATH}\n'
              f'  Refusing to overwrite. A spec rewritten after an evaluation '
              f'is not frozen.\n  Pass --refreeze only if no evaluation has '
              f'been published against it.')
        return 1
    pan = P.build_panel()
    idx = F.Index(pan)
    frames = all_frames(idx)
    constants = S.derive_constants(idx)
    windows = S.select_windows(idx, constants, frames)
    doc = S.build_document(idx, constants, windows)
    doc['panel_audit'] = pan['audit']
    doc['document_sha256'] = S.sha256_of_obj(
        {k: v for k, v in doc.items() if k != 'document_sha256'})
    bad = S.verify(doc)
    if bad:
        raise SystemExit(f'BASELINE_SELF_VERIFY_FAILED: {bad}')
    with open(S.SPEC_PATH, 'w', encoding='utf-8') as fh:
        json.dump(doc, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write('\n')
    print(f'FROZEN {S.SPEC_PATH}')
    print(f'  document_sha256 {doc["document_sha256"]}')
    for name in sorted(doc['baselines']):
        print(f'  {name:28s} {doc["baselines"][name]["spec_sha256"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
