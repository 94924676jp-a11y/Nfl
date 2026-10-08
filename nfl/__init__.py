# Point-in-time backstop (nfl/warehouse/point_in_time.py). When NFL_PIT_MANIFEST names a sealed manifest, every
# process that imports anything from `nfl` arms the read guard before any of its code runs, so a reader that was never
# wired to the contract is refused rather than silently reading a post-cutoff capture. Unset (live): nothing happens.
import os as _os

if _os.environ.get('NFL_PIT_MANIFEST'):
    from nfl.warehouse import point_in_time as _pit
    _pit.active()
