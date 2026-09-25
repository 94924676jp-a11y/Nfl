"""Is the remote-tracking ref this test is about to trust actually current?

`git fetch origin main` updates FETCH_HEAD and NOT `origin/main`. That single
fact has now cost this project three times, and the third time was the worst,
because by then there were tests whose whole job was to report deployment
state. They read a stale `origin/main`, found no heartbeat on it, and reported
DEPLOYMENT_PENDING with complete confidence -- minutes after the heartbeat had
been deployed, registered by GitHub and observed to run.

A test that reads a stale ref does not merely miss something. It manufactures
a false finding in the one direction nobody double-checks, because "not
deployed yet" is the answer you expect while you are deploying.

So any test asserting what is on a remote branch establishes first that its
copy of that branch is current, and says NOT_ESTABLISHED when it cannot tell
rather than treating an unverified ref as fresh. The remedy is a real fetch
refspec: `git fetch origin '+refs/heads/*:refs/remotes/origin/*'`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

FRESH = 'FRESH'
STALE = 'STALE'
NOT_ESTABLISHED = 'NOT_ESTABLISHED'


def _git(*args, timeout=30):
    try:
        r = subprocess.run(('git',) + args, cwd=_REPO, capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ''
    except Exception:                                            # noqa: BLE001
        return ''


def remote_ref_state(branch='main', remote='origin') -> tuple:
    """(state, detail). Never raises: a freshness check that blows up would
    take down the test it exists to protect."""
    local = _git('rev-parse', f'{remote}/{branch}')
    if not local:
        return NOT_ESTABLISHED, f'no local ref for {remote}/{branch}'
    ls = _git('ls-remote', remote, f'refs/heads/{branch}', timeout=60)
    if not ls:
        # Offline, or the remote refused. Unknown is not the same as fresh,
        # and must not be reported as fresh.
        return (NOT_ESTABLISHED,
                f'cannot reach {remote}; {remote}/{branch} is at {local[:12]} '
                f'and may be stale. Anything read from it is unverified.')
    upstream = ls.split()[0]
    if upstream == local:
        return FRESH, f'{remote}/{branch} == {upstream[:12]}'
    return (STALE,
            f'{remote}/{branch} is {local[:12]} but the remote is at '
            f'{upstream[:12]}. `git fetch {remote} {branch}` moves FETCH_HEAD '
            f'ONLY -- use `git fetch {remote} '
            f"'+refs/heads/*:refs/remotes/{remote}/*'`. Every claim this test "
            f'makes about {branch} is being read from the older tree.')


def check_freshness(check, branch='main', remote='origin') -> str:
    """Report freshness through the caller's own `check`, and return the state
    so a test can decide whether its other assertions mean anything."""
    state, detail = remote_ref_state(branch, remote)
    check(f'{remote}/{branch} is current before asserting what is deployed',
          state == FRESH, f'{state}: {detail}')
    return state
