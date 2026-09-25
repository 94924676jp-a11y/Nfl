"""A source that stops looks exactly like a source with nothing to say.

WHY CAPTURE-RESULT LOGGING WAS NOT ENOUGH

On 2026-09-24 the capture layer recorded, honestly and by name, that
`official_inactives` was returning `BLOCKED / NO_EGRESS` with the URL attached.
Nothing was hidden. And nobody noticed, because noticing required comparing that
source against its peers, and no code did that. The forecast ran, the board's
authoritative-inactive gate read INSUFFICIENT_EVIDENCE, and the inactive list
reached the product as text relayed by the owner.

Owner ruling 2026-09-25: an honest NO_EGRESS record is not enough if nobody
notices a normally-active source has stopped while peer feeds remain current. So
this module adds the expectation that was missing -- not "did the capture
succeed" but **"is this source behaving the way this source behaves"**.

THREE VERDICTS THAT ARE DIFFERENT INCIDENTS

  CADENCE_VIOLATION    this source is far past its own normal gap. One feed
                       broke.
  ASYMMETRIC_SILENCE   this source is far behind its PEERS, which are current.
                       The sharpest signal, and the one that was available on
                       2026-09-24 and unused.
  GLOBAL_CAPTURE_STALL every source is behind. The scheduler or the runner
                       stopped, not a website.

Collapsing these would be a mistake. One dark feed is a source problem; all of
them dark is our problem; and a dark feed among current peers is the case where
a slate can be forecast on stale availability without anything looking wrong.

  NEVER_SUCCEEDED      the source has no row-bearing capture, ever.
                       `official_transactions` has 684 attempts and zero
                       successes. That is not staleness, it is a source family
                       the truth layer does not have, and it must not be patched
                       with more inactive-list logic.

WHERE THE NUMBERS COME FROM, BECAUSE A SILENT CONSTANT IS A BUG

Measured 2026-09-25 over `nfl/vintage_manifest.jsonl`: six sources with 594-690
row-bearing captures each show a **median inter-capture gap of 0.5 h and a p90
of 0.6 h**. The cadence is a half-hourly poll. `MAX_AGE_H = 6.0` is twelve times
that median, chosen to survive ordinary maintenance and jitter while still
catching the 25 h stall present in the manifest today. It is a declared
tolerance, not a fitted one, and it is wrong in the safe direction.
"""
from __future__ import annotations

import datetime as dt
import json
import statistics
from pathlib import Path

SPEC_VERSION = 'capture-cadence/1.0.0'

_REPO = Path(__file__).resolve().parents[2]
MANIFEST = _REPO / 'nfl/vintage_manifest.jsonl'

CURRENT = 'CURRENT'
CADENCE_VIOLATION = 'EXPECTED_CAPTURE_CADENCE_VIOLATION'
ASYMMETRIC_SILENCE = 'ASYMMETRIC_SOURCE_SILENCE'
GLOBAL_STALL = 'GLOBAL_CAPTURE_STALL'
NEVER_SUCCEEDED = 'NEVER_SUCCEEDED'
NOT_ESTABLISHED = 'NOT_ESTABLISHED'

#: Derived from the measurement in this module's docstring: a half-hourly poll,
#: given a 12x tolerance.
MAX_AGE_H = 6.0

#: Sources on the half-hourly poll. A source absent from here reads
#: NOT_ESTABLISHED rather than being assumed fine, because a cadence nobody
#: declared is a cadence nobody can violate.
POLLED_SOURCES = frozenset({
    'official_inactives', 'injuries', 'depth_charts', 'schedules',
    'weekly_rosters', 'official_injury_report', 'espn_injuries_json',
})

#: How far behind the peer median counts as asymmetric. Peers poll every 0.5 h,
#: so being a full day behind them while they are current is not jitter.
ASYMMETRY_H = 12.0

#: Fraction of polled sources that must be stale before this is our outage
#: rather than a website's.
GLOBAL_FRACTION = 0.8


#: The branch captures actually write to. Measured 2026-09-25: the repository
#: carries three lineages of this manifest -- `capture-prod` (live),
#: `main` (4,311 rows, last capture 2026-09-15T17:05Z) and the development
#: branch (6,757 rows). They are not versions of one file; they diverge in both
#: directions.
CAPTURE_BRANCH = 'capture-prod'

LINEAGE_NOT_ESTABLISHED = 'LINEAGE_NOT_ESTABLISHED'


class CadenceError(RuntimeError):
    """A slate was about to be forecast on a source that stopped."""


class LineageError(RuntimeError):
    """Staleness was about to be measured against the wrong copy of the file."""


def current_branch(repo: Path = _REPO) -> str | None:
    """The checked-out branch, or None when it cannot be determined."""
    head = Path(repo) / '.git' / 'HEAD'
    try:
        txt = head.read_text().strip()
    except OSError:
        return None
    if txt.startswith('ref: refs/heads/'):
        return txt.split('refs/heads/', 1)[1]
    return None


def lineage_ok(manifest: Path = MANIFEST, repo: Path = _REPO) -> tuple:
    """(is_live_lineage, why).

    THE MISTAKE THIS EXISTS TO PREVENT, MADE BY THIS MODULE ON THE DAY IT WAS
    WRITTEN.

    `assess()` read the manifest in the working copy and reported
    GLOBAL_CAPTURE_STALL: every source 25-31 h behind a half-hourly cadence, so
    the capture runner must have stopped. The runner had not stopped. `NFL
    vintage capture` had succeeded eleven minutes earlier and was running every
    thirty minutes. What was stale was THE CHECKOUT -- captures commit to
    `capture-prod`, and this branch had never pulled them.

    A liveness check that reads a git working copy measures the working copy.
    That is the same defect this whole audit is about: a local artifact read as
    if it were the world. So the lineage is established first, and when it
    cannot be, staleness is reported as NOT ESTABLISHED rather than as an
    outage.
    """
    br = current_branch(repo)
    if str(Path(manifest).resolve()) != str((Path(repo) / 'nfl'
                                             / 'vintage_manifest.jsonl')
                                            .resolve()):
        return True, 'an explicit manifest path was supplied'
    if br is None:
        return False, 'the checked-out branch could not be determined'
    if br != CAPTURE_BRANCH:
        return False, (f'the working copy is on {br!r}, and captures are '
                       f'written to {CAPTURE_BRANCH!r}, so this file\'s age '
                       f'is the age of this checkout and not of the system')
    return True, f'on {CAPTURE_BRANCH}'


def assert_live_lineage(manifest: Path = MANIFEST, repo: Path = _REPO) -> None:
    ok, why = lineage_ok(manifest, repo)
    if not ok:
        raise LineageError(
            f'{LINEAGE_NOT_ESTABLISHED}: {why}. Read the manifest from '
            f'{CAPTURE_BRANCH} (git show {CAPTURE_BRANCH}:nfl/'
            f'vintage_manifest.jsonl) and pass that path explicitly.')


def _ts(capture_id: str):
    c = (capture_id or '').split('.')[0].rstrip('Z')
    try:
        return dt.datetime.strptime(c, '%Y%m%dT%H%M%S').replace(
            tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def observations(manifest: Path = MANIFEST) -> dict:
    """source -> {'row_bearing': [...], 'attempts': [...]} as timestamps."""
    out = {}
    if not Path(manifest).exists():
        return out
    for line in Path(manifest).open():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        t = _ts(r.get('capture_id', ''))
        if t is None:
            continue
        src = r.get('source', '?')
        rec = out.setdefault(src, {'row_bearing': [], 'attempts': []})
        rec['attempts'].append(t)
        v = r.get('value')
        if (r.get('state') == 'PASS' and isinstance(v, dict)
                and isinstance(v.get('n_data_rows'), int)):
            rec['row_bearing'].append(t)
    return out


def assess(manifest: Path = MANIFEST, now=None, repo: Path = _REPO) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
    live, why = lineage_ok(manifest, repo)
    obs = observations(manifest)
    rows = {}
    for src, rec in sorted(obs.items()):
        rb = sorted(rec['row_bearing'])
        at = sorted(rec['attempts'])
        gaps = [(rb[i] - rb[i - 1]).total_seconds() / 3600
                for i in range(1, len(rb))]
        rows[src] = {
            'n_row_bearing': len(rb),
            'n_attempts': len(at),
            'median_gap_h': round(statistics.median(gaps), 2) if gaps else None,
            'last_row_bearing_utc': rb[-1].isoformat() if rb else None,
            'last_attempt_utc': at[-1].isoformat() if at else None,
            'age_h': (round((now - rb[-1]).total_seconds() / 3600, 1)
                      if rb else None),
            'attempt_age_h': round((now - at[-1]).total_seconds() / 3600, 1),
            'polled': src in POLLED_SOURCES,
            'verdicts': [],
        }
    polled = [s for s in rows if rows[s]['polled']]
    ages = [rows[s]['age_h'] for s in polled if rows[s]['age_h'] is not None]
    peer_median = statistics.median(ages) if ages else None
    stale = 0
    for src in polled:
        r = rows[src]
        if r['n_row_bearing'] == 0:
            r['verdicts'].append(NEVER_SUCCEEDED)
            continue
        if r['age_h'] is not None and r['age_h'] > MAX_AGE_H:
            r['verdicts'].append(CADENCE_VIOLATION)
            stale += 1
        if (peer_median is not None and r['age_h'] is not None
                and r['age_h'] - peer_median > ASYMMETRY_H):
            r['verdicts'].append(ASYMMETRIC_SILENCE)
    for src in rows:
        if not rows[src]['polled']:
            rows[src]['verdicts'].append(NOT_ESTABLISHED)
        elif not rows[src]['verdicts']:
            rows[src]['verdicts'].append(CURRENT)
    for src, r in rows.items():
        if r['n_row_bearing'] == 0 and NEVER_SUCCEEDED not in r['verdicts']:
            r['verdicts'].append(NEVER_SUCCEEDED)
    global_stall = bool(polled) and stale >= GLOBAL_FRACTION * len(polled)
    if not live:
        # Age against the wrong copy of the file is not evidence of an outage.
        for r in rows.values():
            r['verdicts'] = [LINEAGE_NOT_ESTABLISHED] + [
                v for v in r['verdicts']
                if v in (NEVER_SUCCEEDED, NOT_ESTABLISHED)]
        global_stall = None
    return {
        'spec_version': SPEC_VERSION,
        'assessed_utc': now.isoformat(),
        'lineage_live': live,
        'lineage_note': why,
        'max_age_h': MAX_AGE_H,
        'peer_median_age_h': peer_median,
        'global_stall': global_stall,
        'sources': rows,
        'reading': (
            'GLOBAL_CAPTURE_STALL means our runner stopped, not a website. One '
            'source behind current peers is ASYMMETRIC_SOURCE_SILENCE and is '
            'the case that lets a slate be forecast on stale availability with '
            'nothing looking wrong.'),
    }


def assert_ready_for_slate(required, report=None, now=None) -> dict:
    """Refuse before an expensive simulation if a required source stopped.

    `required` is named explicitly. Defaulting it to "every source" would make
    this refuse forever; defaulting it to "whatever is current" would make it
    never refuse.
    """
    rep = report or assess(now=now)
    if rep.get('lineage_live') is False:
        raise LineageError(
            f"{LINEAGE_NOT_ESTABLISHED}: {rep.get('lineage_note')}. Refusing "
            f"to clear or block a slate on a manifest whose lineage is "
            f"unknown.")
    bad = {}
    for src in required:
        r = rep['sources'].get(src)
        if r is None:
            bad[src] = ['ABSENT_FROM_CAPTURE_RECORD']
            continue
        v = [x for x in r['verdicts'] if x != CURRENT]
        if v:
            bad[src] = v
    if bad:
        if rep['global_stall']:
            raise CadenceError(
                f'{GLOBAL_STALL}: {len(bad)} required source(s) stale and most '
                f'polled sources are behind, so the capture runner stopped '
                f'rather than any one feed. '
                + '; '.join(f'{k} {v}' for k, v in sorted(bad.items())))
        raise CadenceError(
            'required source(s) are not behaving: '
            + '; '.join(
                f"{k} {v} (age {rep['sources'].get(k, {}).get('age_h')}h vs "
                f"peer median {rep['peer_median_age_h']}h)"
                for k, v in sorted(bad.items())))
    return rep
