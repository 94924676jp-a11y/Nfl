"""Validate the owner-delivered Hard Rock board for the 1PM Early Only slate.

WHAT THIS IS AND IS NOT

This is an EXTERNAL COMPARATOR. A sportsbook price may never enter the
football model, and the reason is not what it would do to the numbers: a model
that has seen the line is no longer independent evidence about the line. So
nothing in this module is importable by a forecast stage, and the artifact it
writes carries that statement on its face.

It is also not permission to compare anything yet. The Early Only universe has
`CURRENT_PROJECTION_AVAILABLE = 0` (DK_EARLY_ONLY_PROJECTION_AUDIT). There is
no sealed forecast to hold this board against, and holding it against the 229
rehearsal distributions would be comparing a market to numbers whose input
validation passed on a placeholder hash. This module validates and preserves.
It compares nothing.

SOURCE QUALIFICATION, AND IT MUST NOT BE FLATTENED

These are Hard Rock Bet prices carried by the OpticOdds v3 `/fixtures/odds`
feed with `sportsbook=Hard Rock`. That is a structured REDISTRIBUTION of the
book's board, not a direct scrape of app.hardrockbet.com. "Hard Rock Bet" names
the book whose prices these are; it does not name who served the bytes. Both
facts travel together in every artifact this writes, because relabelling a
redistribution feed as first-party raw bytes is exactly the provenance defect
this project audits itself for.

BOOK SEPARATION IS CHECKED AT THE BYTES, NOT AT THE LABEL

The bundle also carries a secondary DraftKings touchdown probe, because Hard
Rock's feed exposes no anytime-TD (Over 0.5) market for any player in any of
the eight games. `book_separation()` opens all 48 raw responses and reads the
`sportsbook` field out of every odds record rather than trusting the `book`
column. A column can be mislabelled; 11,764 records cannot be mislabelled
quietly.

WHAT "VALIDATED" MEANS HERE

Every count the delivered report claims is RECOMPUTED from the CSV, and every
CSV row is reconciled against the raw API bytes by `odds_id`: price, line and
`is_main` must agree, every referenced id must exist in the raw, and every raw
id must be referenced. A row count that merely matches is not a check -- two
files can agree on a total and disagree on every row.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
import pathlib
import re
import sys
import zipfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'early-1pm-hardrock-market-1'

DIR = _REPO / 'nfl' / 'research' / 'market' / 'EARLY_1PM_2026W2'
RAW = DIR / 'raw'

#: The owner's bytes, pinned by hash. A file whose hash moved is a different
#: file and this module refuses it rather than validating whatever is there.
BOARD_CSV = RAW / 'NFL_wk2_1pm_hardrock_markets_2026-09-20T0452Z.csv'
BOARD_SHA = '1c097f532fbd81bc0b82bc2c4aa43453b021252a555610dd479d3cd0fb684ec6'
REPORT_MD = RAW / 'CAPTURE_REPORT_AND_COMPLETENESS.md'
REPORT_SHA = '506ead2892b1d8aa30d563ccbfedbd3c02bdb82a5872567abb1df81eedcf2bfe'
BUNDLE_ZIP = RAW / 'NFL_wk2_1pm_hardrock_raw_evidence_2026-09-20.zip'
BUNDLE_SHA = 'bed4b4d9b5845d9bd8cd054996760dbe53cd25f0ea607c8f5b450ae4017ed669'

BOOK = 'Hard Rock Bet'
FEED_SPORTSBOOK = 'Hard Rock'
SECONDARY_SPORTSBOOK = 'DraftKings'

#: The eight 1PM ET games, as DraftKings' own Early Only export resolves them.
#: Membership is CHECKED against this, not inferred from whatever the board
#: happens to contain.
EARLY_GAMES = ('CAR@ATL', 'CIN@HOU', 'CLE@TB', 'GB@NYJ',
               'MIN@CHI', 'NO@BAL', 'PHI@TEN', 'PIT@NE')
EARLY_KICKOFF_UTC = '2026-09-20T17:00:00Z'

#: Raw responses are the connector's full output: one JSON object, the literal
#: separator below, then a connector provenance block. Splitting on it keeps
#: the provenance block instead of discarding it -- dropping a provenance block
#: and then reporting provenance missing is a defect this project has already
#: paid for once.
STDERR_SEP = '<<STDERR>>'


def _sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def delivered_files() -> Outcome:
    """The three owner files, each hash recomputed against its pin."""
    want = ((BOARD_CSV, BOARD_SHA), (REPORT_MD, REPORT_SHA),
            (BUNDLE_ZIP, BUNDLE_SHA))
    got, bad = {}, []
    for p, pin in want:
        if not p.exists():
            bad.append(f'{p.name}: ABSENT')
            continue
        h = _sha256(p)
        got[p.name] = {'sha256': h, 'bytes': p.stat().st_size,
                       'pinned': pin, 'matches_pin': h == pin,
                       'path': str(p.relative_to(_REPO))}
        if h != pin:
            bad.append(f'{p.name}: {h} != pinned {pin}')
    if bad:
        return Outcome.fail('DELIVERED_FILE_HASH_MISMATCH', Cause.DATA,
                            '; '.join(bad), files=got)
    return Outcome.ok('DELIVERED_FILES_VERIFIED', value=got)


def bundle_integrity() -> Outcome:
    """Verify SHA256SUMS.txt inside the zip, without extracting to a tree.

    ONE ENTRY IN THAT MANIFEST CANNOT BE SATISFIED AND IT IS NOT A DEFECT IN
    THE EVIDENCE. `SHA256SUMS.txt` lists itself, and a file cannot contain its
    own hash. Reporting "74 of 75 checksums verified" would read as one corrupt
    file; reporting 74 of 74 silently would hide a line that is there. So the
    self-reference is separated out and named.

    What is NOT explained: the hash the manifest lists for itself matches
    neither the file, nor the file with its own line removed, nor that sorted.
    Neither delivered script generates the manifest, so how it was produced is
    not established by this bundle. Recorded as unverifiable rather than
    guessed at.
    """
    if not BUNDLE_ZIP.exists():
        return Outcome.fail('BUNDLE_ABSENT', Cause.DATA,
                            f'{BUNDLE_ZIP} does not exist')
    with zipfile.ZipFile(BUNDLE_ZIP) as z:
        names = z.namelist()
        root = 'ev/'
        sums = [n for n in names if n.endswith('SHA256SUMS.txt')]
        if not sums:
            return Outcome.fail('BUNDLE_MANIFEST_ABSENT', Cause.DATA,
                                'the bundle carries no SHA256SUMS.txt')
        man = z.read(sums[0]).decode()
        listed = {}
        for ln in man.splitlines():
            m = re.match(r'([0-9a-f]{64})\s+\*?\./?(.+)$', ln.strip())
            if m:
                listed[m.group(2)] = m.group(1)
        ok_, bad, absent, self_ref = [], [], [], None
        for rel, want in sorted(listed.items()):
            arc = root + rel
            if arc not in names:
                absent.append(rel)
                continue
            h = hashlib.sha256(z.read(arc)).hexdigest()
            if rel.endswith('SHA256SUMS.txt'):
                self_ref = {'listed': want, 'actual': h,
                            'why': 'a file cannot contain its own hash; this '
                                   'entry is self-referential and was never '
                                   'satisfiable',
                            'reconstruction_attempted': True,
                            'reconstruction_succeeded': False}
                continue
            (ok_ if h == want else bad).append(rel)
        files_in_zip = [n for n in names if not n.endswith('/')]
        unlisted = sorted(set(n[len(root):] for n in files_in_zip
                              if n.startswith(root))
                          - set(listed))
        res = {
            'manifest_entries': len(listed),
            'files_in_zip': len(files_in_zip),
            'verified': len(ok_),
            'mismatched': bad,
            'listed_but_absent': absent,
            'in_zip_but_unlisted': unlisted,
            'self_referential_entry': self_ref,
        }
        if bad or absent or unlisted:
            return Outcome.fail('BUNDLE_INTEGRITY_FAILED', Cause.DATA,
                                f'{len(bad)} mismatched, {len(absent)} '
                                f'listed-but-absent, {len(unlisted)} '
                                f'unlisted', **res)
        return Outcome.ok('BUNDLE_INTEGRITY_VERIFIED', value=res)


def _raw_objects(z: zipfile.ZipFile, arc: str):
    """The response object and the connector provenance block, both kept."""
    txt = z.read(arc).decode()
    head, sep, tail = txt.partition(STDERR_SEP)
    body = json.loads(head)
    meta = None
    tail = tail.strip()
    if tail:
        try:
            meta = json.loads(tail)
        except ValueError:
            meta = {'unparsed_bytes': len(tail)}
    return body, meta, bool(sep)


def raw_odds_index() -> Outcome:
    """odds_id -> (price, points, is_main, market), read out of the raw bytes.

    Also the http status of every call and the sportsbook on every record, so
    "40/40 returned data" and "these are Hard Rock prices" are measured rather
    than quoted.
    """
    with zipfile.ZipFile(BUNDLE_ZIP) as z:
        names = [n for n in z.namelist() if n.startswith('ev/raw/')
                 and n.endswith('.json')]
        sec = [n for n in z.namelist() if n.startswith('ev/raw_secondary/')
               and n.endswith('.json')]
        idx, status, books, prov = {}, collections.Counter(), \
            collections.Counter(), 0
        fixtures = 0
        for n in sorted(names):
            body, meta, had_sep = _raw_objects(z, n)
            if had_sep and meta:
                prov += 1
            status[body.get('result', {}).get('status_code')] += 1
            for fx in body['result']['data']['data']:
                fixtures += 1
                for o in fx.get('odds', []):
                    books[o.get('sportsbook')] += 1
                    idx[o['id']] = {
                        'price': o.get('price'), 'points': o.get('points'),
                        'is_main': bool(o.get('is_main')),
                        'market': o.get('market'), 'raw_file': n,
                        'timestamp': o.get('timestamp'),
                    }
        sbooks = collections.Counter()
        for n in sorted(sec):
            body, _m, _s = _raw_objects(z, n)
            for fx in body['result']['data']['data']:
                for o in fx.get('odds', []):
                    sbooks[o.get('sportsbook')] += 1
    return Outcome.ok('RAW_ODDS_INDEXED', value={
        'index': idx,
        'n_primary_calls': len(names),
        'n_secondary_calls': len(sec),
        'n_calls_with_a_provenance_block': prov,
        'http_status': {str(k): v for k, v in status.items()},
        'n_fixtures_returned': fixtures,
        'primary_sportsbooks': dict(books),
        'secondary_sportsbooks': dict(sbooks),
    })


def book_separation(raw) -> dict:
    """Are the two books kept apart IN THE BYTES? Checked, not assumed."""
    p, s = raw['primary_sportsbooks'], raw['secondary_sportsbooks']
    return {
        'primary_sportsbooks': p,
        'secondary_sportsbooks': s,
        'primary_is_single_book': list(p) == [FEED_SPORTSBOOK],
        'secondary_is_single_book': list(s) == [SECONDARY_SPORTSBOOK],
        'no_overlap': not (set(p) & set(s)),
        'verdict': ('SEPARATE' if list(p) == [FEED_SPORTSBOOK]
                    and list(s) == [SECONDARY_SPORTSBOOK]
                    and not (set(p) & set(s)) else 'NOT_SEPARATE'),
        'note': ('read from the sportsbook field of every odds record in all '
                 f'{raw["n_primary_calls"] + raw["n_secondary_calls"]} raw '
                 'responses, not from the CSV book column'),
    }


def board_rows() -> list:
    with open(BOARD_CSV, newline='') as f:
        return list(csv.DictReader(f))


def completeness(rows) -> dict:
    """Recompute every count the delivered report claims."""
    pp = [r for r in rows if r['market_class'] == 'player_prop']
    gt = [r for r in rows if r['market_class'] == 'game_or_team']
    mainpp = [r for r in pp if r['is_main_line'] == 'True']
    st = collections.Counter(r['market_status'] for r in mainpp)
    return {
        'n_rows': len(rows),
        'n_player_prop_rows': len(pp),
        'n_game_or_team_rows': len(gt),
        'n_main_player_markets': len(mainpp),
        'n_alternate_player_rows': len(pp) - len(mainpp),
        'n_unique_players_main': len({r['player'] for r in mainpp}),
        'n_main_two_sided': st['open_two_sided'],
        'n_main_one_sided': sum(v for k, v in st.items()
                                if k.startswith('open_one_sided')),
        'market_status_all': dict(collections.Counter(
            r['market_status'] for r in rows)),
        'games': sorted({r['game'] for r in rows}),
        'books': dict(collections.Counter(r['book'] for r in rows)),
        'retrieved_at_min': min(r['retrieved_at_utc'] for r in rows),
        'retrieved_at_max': max(r['retrieved_at_utc'] for r in rows),
        'book_line_timestamp_min': min(r['book_line_timestamp_utc']
                                       for r in rows if
                                       r['book_line_timestamp_utc']),
        'book_line_timestamp_max': max(r['book_line_timestamp_utc']
                                       for r in rows if
                                       r['book_line_timestamp_utc']),
        'kickoffs': dict(collections.Counter(r['kickoff_utc'] for r in rows)),
    }


def slate_membership(rows) -> dict:
    """Exactly the eight 1PM games, and every kickoff agreeing."""
    got = sorted({r['game'] for r in rows})
    ko = sorted({r['kickoff_utc'] for r in rows})
    return {
        'expected': list(EARLY_GAMES),
        'observed': got,
        'missing': [g for g in EARLY_GAMES if g not in got],
        'unexpected': [g for g in got if g not in EARLY_GAMES],
        'exact_match': got == sorted(EARLY_GAMES),
        'kickoffs_observed': ko,
        'all_kickoffs_are_the_early_window': ko == [EARLY_KICKOFF_UTC],
    }


def structural_checks(rows) -> dict:
    """Duplicates, exact lines, price form, status/price agreement, clocks."""
    key = (lambda r: (r['game_id'], r['market_id'],
                      r['displayed_selection'], r['line'], r['is_main_line']))
    c = collections.Counter(key(r) for r in rows)
    dups = [list(k) for k, v in c.items() if v > 1]

    # EXACT LINES. A line is kept as the book printed it. This checks the
    # string, not a float: 247.5 parsed and reprinted can come back 247.5 while
    # a rounded 4.5 -> 5 also parses cleanly. Only the fractional part of the
    # STRING can show that nothing was rounded.
    fracs = collections.Counter(
        (r['line'].split('.')[1] if '.' in r['line'] else '<integer>')
        for r in rows if r['line'])
    malformed = sorted({r['line'] for r in rows
                        if r['line'] and not re.fullmatch(r'-?\d+(\.\d+)?',
                                                          r['line'])})

    def price_ok(p):
        return p == '' or bool(re.fullmatch(r'[+-]?\d+', p))
    badprice = [r['odds_id_over'] or r['odds_id_under'] for r in rows
                if not (price_ok(r['over_price']) and price_ok(r['under_price'])
                        and price_ok(r['selection_price']))]

    # market_status must PREDICT which price columns are populated. If it does
    # not, the status column is decoration.
    shape = collections.defaultdict(collections.Counter)
    for r in rows:
        shape[r['market_status']][
            (bool(r['over_price']), bool(r['under_price']),
             bool(r['selection_price']))] += 1
    pairing = {k: {'|'.join('OUS'[i] for i, b in enumerate(sh) if b) or 'NONE':
                   n for sh, n in v.items()} for k, v in shape.items()}
    inconsistent = {k: v for k, v in pairing.items() if len(v) > 1}

    # A price retrieved BEFORE the book last changed it is a chronology error.
    early = [r['odds_id_over'] or r['odds_id_under'] for r in rows
             if r['book_line_timestamp_utc']
             and r['retrieved_at_utc'] < r['book_line_timestamp_utc'][:19] + 'Z']
    return {
        'n_duplicate_keys': len(dups),
        'duplicate_keys': dups[:20],
        'line_fractional_parts': dict(fracs),
        'malformed_lines': malformed,
        'n_malformed_prices': len(badprice),
        'status_to_populated_price_columns': pairing,
        'status_inconsistent_with_prices': inconsistent,
        'n_rows_retrieved_before_book_last_change': len(early),
    }


def reconcile_against_raw(rows, idx) -> dict:
    """Every CSV row back to the raw bytes by odds_id. Both directions.

    A row count that matches proves nothing; two files can agree on a total and
    disagree on every row. So each id must EXIST in the raw with the same
    price, the same line and the same is_main flag, and no raw id may be left
    unreferenced.

    Point spreads are signed from the perspective of `displayed_selection`
    while the feed's `points` carries the book's own sign, so the line is
    compared on magnitude and the sign is reported separately rather than
    treated as a mismatch.
    """
    used, missing, mismatched, signflip = set(), [], [], 0

    def chk(oid, price, line, is_main):
        nonlocal signflip
        if not oid:
            return
        used.add(oid)
        e = idx.get(oid)
        if e is None:
            missing.append(oid)
            return
        if str(e['price']) != str(price):
            mismatched.append({'odds_id': oid, 'field': 'price',
                               'raw': e['price'], 'csv': price})
        if line != '' and e['points'] is not None:
            lv, pv = float(line), float(e['points'])
            if abs(lv) != abs(pv):
                mismatched.append({'odds_id': oid, 'field': 'line',
                                   'raw': e['points'], 'csv': line})
            elif lv != pv:
                signflip += 1
        if e['is_main'] != (is_main == 'True'):
            mismatched.append({'odds_id': oid, 'field': 'is_main',
                               'raw': e['is_main'], 'csv': is_main})

    for r in rows:
        if r['market_status'] == 'open_single_selection':
            chk(r['odds_id_over'] or r['odds_id_under'], r['selection_price'],
                r['line'], r['is_main_line'])
        else:
            chk(r['odds_id_over'], r['over_price'], r['line'],
                r['is_main_line'])
            chk(r['odds_id_under'], r['under_price'], r['line'],
                r['is_main_line'])
    unref = sorted(set(idx) - used)
    return {
        'n_raw_odds_records': len(idx),
        'n_csv_odds_references': len(used),
        'n_referenced_but_absent_from_raw': len(missing),
        'referenced_but_absent': missing[:20],
        'n_raw_never_referenced_by_csv': len(unref),
        'raw_never_referenced': unref[:20],
        'n_field_mismatches': len(mismatched),
        'field_mismatches': mismatched[:20],
        'n_spread_sign_reoriented': signflip,
        'conserves': (not missing and not unref and not mismatched),
    }


def identity(rows) -> dict:
    """Hard Rock player names -> our canonical ids. Deterministic, three passes.

    Same rule as the DK universe: exact (name, team), then normalised
    (name, team), then normalised name with the team disagreeing and RECORDED.
    No edit distance anywhere. A market name our roster vintage does not carry
    is UNMATCHED, which is a coverage gap in OUR roster, not licence to guess.
    """
    from nfl.dfs.salaries import dk_universe as DK
    from nfl.dfs.salaries import identity as ID

    o = ID.canonical_roster(2026, 2)
    if o.state is not State.PASS:
        return {'state': 'BLOCKED', 'code': o.code, 'detail': o.detail}
    by_exact, by_norm, by_nn = (collections.defaultdict(list),
                                collections.defaultdict(list),
                                collections.defaultdict(list))
    for r in o.value:
        nm = (r.get('full_name') or '').strip()
        tm = (r.get('team') or '').strip()
        if not nm:
            continue
        by_exact[(nm, tm)].append(r)
        by_norm[(DK._norm_name(nm), tm)].append(r)
        by_nn[DK._norm_name(nm)].append(r)

    pp = [r for r in rows if r['market_class'] == 'player_prop']
    seen = sorted({(r['player'], r['team'], r['position'], r['game'])
                   for r in pp})
    out, counts = [], collections.Counter()
    for nm, tm, pos, game in seen:
        n = DK._norm_name(nm)
        rec = {'market_name': nm, 'market_team': tm, 'market_position': pos,
               'game': game, 'gsis_id': None, 'canonical_name': None,
               'canonical_team': None, 'match_method': None, 'status': None,
               'note': None}
        if len(by_exact.get((nm, tm), [])) == 1:
            hit, rec['match_method'] = by_exact[(nm, tm)][0], 'EXACT_NAME_TEAM'
        elif len(by_norm.get((n, tm), [])) == 1:
            hit, rec['match_method'] = by_norm[(n, tm)][0], 'NORMALISED_NAME_TEAM'
        elif len(by_nn.get(n, [])) == 1:
            hit, rec['match_method'] = by_nn[n][0], 'NORMALISED_NAME_TEAM_DISAGREES'
            rec['note'] = (f'the board says {tm}; our roster vintage says '
                           f'{by_nn[n][0].get("team")}. Recorded, not '
                           f'corrected.')
        elif len(by_nn.get(n, [])) > 1:
            hit, rec['match_method'] = None, 'MORE_THAN_ONE_CANONICAL_PLAYER'
            rec['status'] = 'AMBIGUOUS'
        else:
            hit, rec['match_method'] = None, 'NO_CANONICAL_ROW_ANSWERS'
            rec['status'] = 'UNMATCHED'
            rec['note'] = ('absent from our 2026 week-2 roster vintage under '
                           'this name on ANY team, so the board\'s team '
                           'attribution for him is unverified here. A '
                           'coverage gap in our roster, not a reason to '
                           'guess an identity.')
        if hit is not None:
            rec['status'] = 'MATCHED_CANONICAL'
            rec['gsis_id'] = hit.get('gsis_id')
            rec['canonical_name'] = hit.get('full_name')
            rec['canonical_team'] = hit.get('team')
        counts[rec['status']] += 1
        out.append(rec)
    lookup = {(r['market_name'], r['market_team']): r['status'] for r in out}
    n_rows_by_status = collections.Counter(
        lookup.get((r['player'], r['team']), 'NOT_IN_LOOKUP') for r in pp)
    return {
        'state': 'PASS',
        'roster_source': o.code,
        'n_distinct_market_players': len(seen),
        'by_status': dict(counts),
        'n_player_prop_rows_by_status': dict(n_rows_by_status),
        'unresolved': [r for r in out
                       if r['status'] in ('UNMATCHED', 'AMBIGUOUS')],
        'rows': out,
    }


DK_AUDIT = (_REPO / 'nfl' / 'dfs' / 'salaries'
            / 'DK_EARLY_ONLY_PROJECTION_AUDIT.json')


def dk_universe_overlap(ident) -> dict:
    """Which priced players are also DraftKings-rosterable, and which are not.

    THE ASYMMETRY IS THE POINT AND IT RUNS BOTH WAYS. A player the book prices
    who is not on the DK Early Only board is not a DK coverage gap -- most are
    kickers, and DraftKings Classic does not roster a kicker at all. A player
    on the DK board the book does not price is not a market gap either. Two
    different products select two different populations, and reporting one
    difference as a defect of the other is how a count becomes a finding it
    never was.
    """
    if not DK_AUDIT.exists():
        return {'state': 'BLOCKED', 'code': 'DK_AUDIT_ABSENT',
                'detail': f'{DK_AUDIT} does not exist'}
    from nfl.dfs.salaries import dk_universe as DK
    doc = json.loads(DK_AUDIT.read_text())
    by_key = {(DK._norm_name(r['dk_name']), r['team']) for r in doc['rows']}
    by_gsis = {r['gsis_id'] for r in doc['rows'] if r.get('gsis_id')}
    counts, absent = collections.Counter(), []
    for r in ident['rows']:
        k = (DK._norm_name(r['market_name']), r['market_team'])
        if k in by_key:
            counts['PRICED_AND_DK_ROSTERABLE'] += 1
        elif r['gsis_id'] and r['gsis_id'] in by_gsis:
            counts['PRICED_AND_DK_ROSTERABLE_BY_GSIS_ONLY'] += 1
        else:
            counts['PRICED_BUT_NOT_ON_THE_DK_BOARD'] += 1
            absent.append({'market_name': r['market_name'],
                           'market_team': r['market_team'],
                           'position': r['market_position'],
                           'identity_status': r['status']})
    pk = [a for a in absent if a['position'] == 'PK']
    return {
        'state': 'PASS',
        'dk_universe_rows': len(doc['rows']),
        'counts': dict(counts),
        'priced_but_not_on_dk_board': absent,
        'n_of_those_who_are_kickers': len(pk),
        'why_kickers_are_absent': ('DraftKings Classic rosters QB/RB/WR/TE/'
                                   'FLEX/DST and no kicker, so a priced '
                                   'kicker missing from the DK board is the '
                                   'two products differing, not a gap in '
                                   'either.'),
        'non_kickers_absent': [a for a in absent if a['position'] != 'PK'],
    }


def gaps(rows) -> dict:
    """What the book did NOT list. Absence recorded, never filled.

    The delivered report names six gaps. Each is checked against the CSV here
    rather than repeated, because a gap list that is quoted is a claim and a
    gap list that is measured is evidence.
    """
    pp = [r for r in rows if r['market_class'] == 'player_prop']
    mkts = collections.Counter(r['market'] for r in pp
                               if r['is_main_line'] == 'True')
    td_lines = sorted({r['line'] for r in pp
                       if r['market'] == 'Player Touchdowns'},
                      key=lambda s: float(s))
    return {
        'main_market_counts': dict(sorted(mkts.items())),
        'anytime_td_over_0_5_present': '0.5' in td_lines,
        'player_touchdown_lines_offered': td_lines,
        'receiving_targets_present': any('Target' in m for m in mkts),
        'n_main_rushing_attempts': mkts.get('Player Rushing Attempts', 0),
        'n_main_longest_rush': mkts.get('Player Longest Rush', 0),
        'note': ('every entry here is an ABSENCE in the book\'s board. '
                 'Nothing was substituted from another book, another market '
                 'or another line. The secondary DraftKings touchdown probe '
                 'exists precisely because Hard Rock offers no Over 0.5, and '
                 'it is a DIFFERENT BOOK, not a fill for this gap.'),
    }


def validate() -> dict:
    """Every check, one artifact. Nothing here compares a model to a price."""
    files = delivered_files()
    if files.state is not State.PASS:
        return {'state': 'FAIL', 'code': files.code, 'detail': files.detail}
    integ = bundle_integrity()
    raw = raw_odds_index()
    rows = board_rows()
    idx = raw.value['index']
    _ident = identity(rows)
    return {
        'spec_version': SPEC_VERSION,
        'artifact': 'EARLY_1PM_2026W2_HARDROCK_MARKET_BOARD',
        'role': 'EXTERNAL_COMPARATOR_ONLY',
        'forecast_eligible': False,
        'why_not': ('A sportsbook price is forbidden as a predictive input. A '
                    'model that has seen the line is no longer independent '
                    'evidence about the line.'),
        'compared_against_a_model': False,
        'why_no_comparison_yet': (
            'CURRENT_PROJECTION_AVAILABLE = 0 for the Early Only universe. '
            'There is no sealed forecast to hold this board against, and the '
            '229 rehearsal distributions are dry_run/prospective_eligible='
            'false with capture_validation satisfied by a placeholder hash.'),
        'source_qualification': {
            'book': BOOK,
            'delivery_path': 'OpticOdds API v3 GET /fixtures/odds'
                             f' (sportsbook={FEED_SPORTSBOOK!r})',
            'is_first_party_scrape': False,
            'statement': ('Hard Rock Bet prices carried by a structured '
                          'redistribution feed. "Hard Rock Bet" names the '
                          'book whose prices these are; it does not name who '
                          'served the bytes. These are not a direct scrape of '
                          'app.hardrockbet.com and must not be relabelled as '
                          'first-party raw bytes.'),
        },
        'delivered_files': files.value,
        'bundle_integrity': (integ.value if integ.state is State.PASS
                             else {'state': integ.state.name,
                                   'code': integ.code,
                                   'detail': integ.detail,
                                   **(integ.evidence or {})}),
        'raw_calls': {k: v for k, v in raw.value.items() if k != 'index'},
        'book_separation': book_separation(raw.value),
        'slate_membership': slate_membership(rows),
        'completeness': completeness(rows),
        'structural': structural_checks(rows),
        'reconciliation_against_raw_bytes': reconcile_against_raw(rows, idx),
        'identity': _ident,
        'dk_universe_overlap': dk_universe_overlap(_ident),
        'gaps': gaps(rows),
    }
