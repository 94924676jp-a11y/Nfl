# IND@KC Showdown — historical slate research

These five modules were in `nfl/dfs/showdown/` until 2026-09-25. **Nothing
about them changed except their location**, plus one import rewritten to
follow them. They produce no live output and are imported by nothing outside
this directory.

They were moved because their old location asserted something false. A module
under `nfl/dfs/` reads as a generic DraftKings capability; these are the
scripts that built one decision package for one game. `build_showdown.py`
carries six `IND@KC` literals and `eval_props_indkc.py` seven.

| Module | What it did for that slate |
|---|---|
| `build_showdown.py` | the decision package, from the frozen draws; `__main__` entry |
| `dk_universe_showdown.py` | identity and salary read out of the owner's DK entry file |
| `eval_props_indkc.py` | the Hard Rock board against the frozen draws |
| `write_props_md.py` | the shortlist, rendered from the evaluation JSON |
| `write_showdown_md.py` | the markdown, rendered from the package JSON |

Claims NOT made: that any of them is correct, or reproducible today. They were
classified by reachability and content, not re-derived. If a mechanism here is
ever wanted generically, extract it into a game-parameterised module under
`nfl/dfs/` and leave this as the historical caller — do not promote the script.
