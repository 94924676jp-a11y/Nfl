"""Run A2's measurement and write its artifact. Reads only."""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import artifact_claim as AC             # noqa: E402
from sportsplatform.governance.outcome import State                    # noqa: E402
from nfl.research.assumptions import a2_redistribution as A2           # noqa: E402

OUT = _REPO / 'nfl/research/assumptions/A2_REDISTRIBUTION.json'


def main() -> int:
    o = A2.run(verbose=True)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        return 1
    OUT.write_text(json.dumps(
        {'spec_version': A2.SPEC_VERSION, 'detail': o.detail,
         'evidence': {k: v for k, v in o.evidence.items() if k != 'cause'},
         'rooms': o.value}, indent=1, sort_keys=True, default=str))
    print(f"general limb fires in : {o.evidence['falsifier_limb_general_departure']}")
    print(f"specific limb fires in: "
          f"{o.evidence['falsifier_limb_nearest_neighbour_absorbs_more']}")
    print(f"falsifies A2          : {o.evidence['falsifies_a2']}")
    c = AC.claim(OUT, schema=['rooms', 'evidence'], label=OUT.name)
    return 0 if c.state is State.PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())
