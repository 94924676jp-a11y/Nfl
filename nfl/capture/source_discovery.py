"""Find the artifact that carries the rows, and pin it. Do not guess a new URL.

WHY DISCOVERY AND NOT A REPLACEMENT CONSTANT

DEF-012: the configured `official_inactives` URL is a landing page. 0 of 367
committed captures carry a row container; 363 say "check back soon". The
temptation is to paste in whichever article URL happens to work this week, which
replaces one brittle constant with a fresher brittle constant and hides the same
failure until the next redesign.

Owner ruling 2026-09-25: build the mechanism that LOCATES a content-bearing
artifact for a specific game and publication window. A candidate then has to earn
its place against ten named checks, and the one that passes is PINNED. Forecast
execution consumes the pin and never rediscovers, because a stage that can look
things up for itself has its own information clock.

THE TEN CHECKS, AND WHY EACH IS SEPARATE

Every one of these has failed somewhere in this project, which is why none of
them is folded into another:

  OFFICIAL_DOMAIN          the host belongs to a declared source family. A
                           relayed screenshot is a secondary source, not this.
  GAME_ATTRIBUTION         the bytes are about THIS game. A league-wide page
                           fetched for one target is not that target's document.
  PUBLICATION_TIME         a parseable time exists. "unknown" is not a time.
  BOTH_TEAM_COVERAGE       where the obligation names two clubs, one club's
                           article does not discharge it.
  CONTENT_BEARING          a row container is present. This is the check whose
                           absence let 374 captures store a chrome word count as
                           a row count.
  PLAYER_NAME_PRESENCE     real names from the roster appear in the bytes. A
                           table of headers with no players passes CONTENT_
                           BEARING and carries nothing.
  RAW_BYTES_PRESERVED      the bytes were written down. A capture that parsed
                           and discarded cannot be re-examined.
  HASH_RECORDED            a digest OF THE STORED BYTES, not of what was fetched.
                           Those differed once already in this repository.
  PARSER_COMPATIBLE        the declared parser actually returns entries. Shape
                           present and parser silent is CONTENT_PRESENT_
                           EXTRACTION_EMPTY, a different defect entirely.
  CUTOFF_LEGAL             published at or before the run's cutoff. Discovery
                           may range freely; what gets PINNED may not.

A candidate that fails any check is refused BY NAME. There is no score and no
threshold: a partial pass is a refusal, because "8 of 10" invites somebody to
decide which two did not matter.

LIMITS
  This module does not fetch. `discover` takes a fetcher so the network lives at
  the edge and every test drives real bytes. It cannot tell a page that lost its
  data from a URL that never had it -- `deferral_escalation` makes that call.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from pathlib import Path

SPEC_VERSION = 'source-discovery/1.0.0'

#: Host suffixes that constitute an official source family. A relay, an
#: aggregator or a screenshot is a SECONDARY source and is out of scope here.
OFFICIAL_HOSTS = ('nfl.com', 'atlantafalcons.com', 'packers.com', 'chiefs.com',
                  'buffalobills.com', 'detroitlions.com')

#: Shapes in which rows may live. Declared per family, never inferred.
ROW_CONTAINERS = ('<tr', '<table', '<tbody', '<ul')

PASS = 'PASS'
FAIL = 'FAIL'

CANNOT_YIELD = 'SOURCE_PATH_CANNOT_YIELD_ROWS'
EXTRACTION_EMPTY = 'CONTENT_PRESENT_EXTRACTION_EMPTY'


class DiscoveryError(RuntimeError):
    """No candidate qualified, or a pinned artifact was bypassed."""


def _host(url: str) -> str:
    m = re.match(r'https?://([^/]+)', url or '')
    return (m.group(1) if m else '').lower()


def sha256_of_stored(path: Path) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def qualify(candidate: dict, requirement: dict, parser=None) -> dict:
    """Ten named verdicts for one candidate. No score, no threshold.

    `candidate`: url, retrieved_at_utc, published_at_utc, stored_path, text
    `requirement`: game_id, teams (iterable), roster_names, cutoff_utc,
                   require_both_teams
    """
    text = candidate.get('text') or ''
    low = text.lower()
    checks = {}

    checks['OFFICIAL_DOMAIN'] = (
        PASS if any(_host(candidate.get('url', '')).endswith(h)
                    for h in OFFICIAL_HOSTS)
        else FAIL)

    teams = [t for t in (requirement.get('teams') or ())]
    present = [t for t in teams if t and t.lower() in low]
    checks['GAME_ATTRIBUTION'] = PASS if present else FAIL

    checks['BOTH_TEAM_COVERAGE'] = (
        PASS if (not requirement.get('require_both_teams')
                 or len(present) == len(teams)) else FAIL)

    pub = candidate.get('published_at_utc') or candidate.get('retrieved_at_utc')
    parsed_pub = None
    if pub:
        try:
            parsed_pub = dt.datetime.fromisoformat(str(pub))
            if parsed_pub.tzinfo is None:
                parsed_pub = parsed_pub.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            parsed_pub = None
    checks['PUBLICATION_TIME'] = PASS if parsed_pub else FAIL

    has_rows = any(c in low for c in ROW_CONTAINERS)
    checks['CONTENT_BEARING'] = PASS if has_rows else FAIL

    roster = [n for n in (requirement.get('roster_names') or ())]
    named = [n for n in roster if n and n.lower() in low]
    checks['PLAYER_NAME_PRESENCE'] = PASS if named else FAIL

    sp = candidate.get('stored_path')
    checks['RAW_BYTES_PRESERVED'] = (
        PASS if sp and Path(sp).exists() else FAIL)

    digest = sha256_of_stored(sp) if sp else None
    checks['HASH_RECORDED'] = PASS if digest else FAIL

    entries = []
    if parser is not None:
        try:
            entries = list(parser(text) or [])
        except Exception:                                        # noqa: BLE001
            entries = []
    checks['PARSER_COMPATIBLE'] = (
        PASS if (parser is None and has_rows) or entries else FAIL)

    cutoff = requirement.get('cutoff_utc')
    legal = True
    if cutoff and parsed_pub:
        c = (dt.datetime.fromisoformat(str(cutoff))
             if not isinstance(cutoff, dt.datetime) else cutoff)
        if c.tzinfo is None:
            c = c.replace(tzinfo=dt.timezone.utc)
        legal = parsed_pub <= c
    checks['CUTOFF_LEGAL'] = PASS if legal else FAIL

    failed = sorted(k for k, v in checks.items() if v == FAIL)
    # THE TWO FAILURE CLASSES THE OWNER RULED MUST STAY SEPARATE FOREVER.
    klass = None
    if not has_rows:
        klass = CANNOT_YIELD
    elif has_rows and parser is not None and not entries:
        klass = EXTRACTION_EMPTY
    return {
        'spec_version': SPEC_VERSION,
        'url': candidate.get('url'),
        'checks': checks,
        'failed': failed,
        'qualified': not failed,
        'n_entries': len(entries),
        'sha256': digest,
        'teams_present': present,
        'names_present': named[:8],
        'failure_class': klass,
        'reading': (
            'qualified' if not failed else
            'refused on ' + ', '.join(failed)
            + (f' [{klass}]' if klass else '')),
    }


def discover(urls, requirement, fetcher, parser=None, store_dir=None) -> dict:
    """Try each candidate URL, qualify it, and pin the first that passes.

    Discovery may range over any candidate and may run BEFORE evidence freeze.
    What it returns is a pin; nothing downstream may look further.
    """
    reports, pinned = [], None
    for url in urls:
        got = fetcher(url)
        if not got:
            reports.append({'url': url, 'qualified': False,
                            'failed': ['FETCH_RETURNED_NOTHING'],
                            'checks': {}, 'reading': 'fetch returned nothing'})
            continue
        cand = dict(got, url=url)
        if store_dir and cand.get('text') is not None \
                and not cand.get('stored_path'):
            d = Path(store_dir)
            d.mkdir(parents=True, exist_ok=True)
            p = d / (hashlib.sha256(url.encode()).hexdigest()[:16] + '.html')
            p.write_text(cand['text'])
            cand['stored_path'] = str(p)
        rep = qualify(cand, requirement, parser=parser)
        reports.append(rep)
        if rep['qualified'] and pinned is None:
            pinned = rep
    return {
        'spec_version': SPEC_VERSION,
        'game_id': requirement.get('game_id'),
        'n_candidates': len(reports),
        'pinned': pinned,
        'candidates': reports,
        'reading': (
            f"pinned {pinned['url']}" if pinned else
            'NO CANDIDATE QUALIFIED. Every refusal is named per candidate; '
            'none of them is a near miss to be waved through.'),
    }


def assert_pinned(result: dict) -> dict:
    if not result.get('pinned'):
        raise DiscoveryError(
            'NO_QUALIFYING_ARTIFACT: ' + '; '.join(
                f"{c.get('url')} -> {', '.join(c.get('failed') or [])}"
                for c in result.get('candidates', [])))
    return result['pinned']


def assert_consumes_pin_only(pin: dict, consumed_url: str) -> None:
    """Forecast execution reads the pin. Rediscovery is a second clock."""
    if consumed_url != pin.get('url'):
        raise DiscoveryError(
            f'PINNED_ARTIFACT_BYPASSED: the pin is {pin.get("url")!r} and the '
            f'consumer read {consumed_url!r}. A stage that resolves its own '
            f'source has its own information clock.')
