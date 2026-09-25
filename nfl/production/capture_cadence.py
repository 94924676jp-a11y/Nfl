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


class CadenceError(RuntimeError):
    """A slate was about to be forecast on a source that stopped."""


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


def assess(manifest: Path = MANIFEST, now=None) -> dict:
    now = now or dt.datetime.now(dt.timezone.utc)
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
    return {
        'spec_version': SPEC_VERSION,
        'assessed_utc': now.isoformat(),
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
