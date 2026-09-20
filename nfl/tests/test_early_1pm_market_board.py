"""The owner-delivered Hard Rock Early Only board: is it what it says it is?

WHAT THESE TESTS ARE FOR

Not to restate the delivered capture report. A count quoted from a report is a
claim; a count recomputed from the bytes is evidence. Every number the report
asserts is recomputed here from the CSV, and every CSV row is reconciled
against the raw API bytes by odds id.

THE TWO CHECKS THAT MATTER MOST, AND WHY A ROW COUNT IS NOT ONE OF THEM

1. CONSERVATION AGAINST THE RAW BYTES. Two files can agree on a total and
   disagree on every row. So each odds id in the CSV must exist in the raw
   responses with the same price, the same line and the same is_main flag, and
   no raw record may be left unreferenced. 11,764 records, both directions.

2. BOOK SEPARATION AT THE BYTES. The bundle carries a secondary DraftKings
   touchdown probe because Hard Rock lists no anytime-TD Over 0.5 anywhere in
   these eight games. The `book` column saying "Hard Rock Bet" proves nothing
   -- a column can be mislabelled. The sportsbook field of all 12,379 odds
   records across all 48 raw responses is read instead.

AND THE ONE THAT KEEPS THE WALL STANDING

The market must not be reachable from a forecast stage. `test_no_forecast_
stage_imports_this` walks the import graph rather than trusting a docstring.

A NOTE ON THE LINE CHECK. Lines are compared as STRINGS, not floats. 247.5
parsed and reprinted comes back 247.5 -- and so does a 4.5 that was rounded to
5 somewhere upstream. Only the string's fractional part can show that nothing
was rounded.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.market import early_1pm_hardrock as M                     # noqa: E402
from sportsplatform.governance.outcome import State                # noqa: E402

_P, _F = 0, 0
_CACHE = {}


def ok(cond, what):
    global _P, _F
    if cond:
        _P += 1
        print(f'  ok     {what}')
    else:
        _F += 1
        print(f'  FAIL   {what}')


def V():
    if 'v' not in _CACHE:
        _CACHE['v'] = M.validate()
    return _CACHE['v']


def test_delivered_bytes_are_unchanged():
    o = M.delivered_files()
    ok(o.state is State.PASS,
       f'all three owner files present and hashing to their pins '
       f'({o.code})')
    for name, rec in (o.value or {}).items():
        ok(rec['matches_pin'],
           f'{name}: {rec["bytes"]} bytes, sha256 {rec["sha256"][:16]}... '
           f'matches the pin')


def test_bundle_checksums():
    """74 of 74 real files. The 75th entry is the manifest naming itself."""
    b = V()['bundle_integrity']
    ok(b.get('verified') == 74,
       f'74 evidence files verify against SHA256SUMS.txt (got '
       f'{b.get("verified")})')
    ok(b.get('mismatched') == [],
       'no evidence file disagrees with its recorded hash')
    ok(b.get('listed_but_absent') == [] and b.get('in_zip_but_unlisted') == [],
       'the manifest and the archive name exactly the same files -- nothing '
       'listed is missing, nothing present is unlisted')
    sr = b.get('self_referential_entry') or {}
    ok(sr.get('listed') and sr.get('actual')
       and sr['listed'] != sr['actual'],
       'the 75th entry is SHA256SUMS.txt listing itself, which no file can '
       'satisfy. Named rather than reported as a corrupt file, and rather '
       'than hidden by counting only the other 74')
    ok(sr.get('reconstruction_succeeded') is False,
       'and what that listed hash covers is NOT established: it matches '
       'neither the file, nor the file without its own line, nor that '
       'sorted, and neither delivered script generates the manifest')


def test_every_call_returned_data_with_its_provenance():
    r = V()['raw_calls']
    ok(r['n_primary_calls'] == 40 and r['http_status'] == {'200': 40},
       f'all 40 primary calls returned HTTP 200 ({r["http_status"]})')
    ok(r['n_fixtures_returned'] == 40,
       f'and every one returned a fixture: {r["n_fixtures_returned"]}/40. '
       'A 200 carrying no data is the empty-success defect this project '
       'pays for most often, so it is counted separately')
    ok(r['n_calls_with_a_provenance_block'] == 40,
       'and all 40 preserved the connector provenance block, which is kept '
       'rather than stripped')


def test_book_separation_at_the_bytes():
    b = V()['book_separation']
    ok(b['primary_sportsbooks'] == {'Hard Rock': 11764},
       f'every one of the 11,764 primary odds records reads '
       f'sportsbook="Hard Rock": {b["primary_sportsbooks"]}')
    ok(b['secondary_sportsbooks'] == {'DraftKings': 615},
       f'every one of the 615 secondary records reads "DraftKings": '
       f'{b["secondary_sportsbooks"]}')
    ok(b['no_overlap'] and b['verdict'] == 'SEPARATE',
       'the two books do not mix, established from the records and not from '
       'the CSV book column')


def test_the_slate_is_exactly_the_eight_1pm_games():
    s = V()['slate_membership']
    ok(s['exact_match'],
       f'exactly the eight Early Only games, none missing and none extra: '
       f'{s["observed"]}')
    ok(s['all_kickoffs_are_the_early_window'],
       f'and every row carries the 1PM ET kickoff: {s["kickoffs_observed"]}')


def test_every_claimed_count_recomputes():
    c = V()['completeness']
    for field, want in (('n_rows', 7081),
                        ('n_player_prop_rows', 4560),
                        ('n_game_or_team_rows', 2521),
                        ('n_main_player_markets', 591),
                        ('n_alternate_player_rows', 3969),
                        ('n_unique_players_main', 133),
                        ('n_main_two_sided', 505),
                        ('n_main_one_sided', 86)):
        ok(c[field] == want,
           f'{field} recomputes to {c[field]}, report claims {want}')
    ok(c['books'] == {'Hard Rock Bet': 7081},
       f'and every row is labelled one book: {c["books"]}')


def test_rows_conserve_against_the_raw_bytes():
    """The check a matching row count cannot make."""
    r = V()['reconciliation_against_raw_bytes']
    ok(r['n_raw_odds_records'] == r['n_csv_odds_references'] == 11764,
       f'11,764 raw odds records and 11,764 CSV references: '
       f'{r["n_raw_odds_records"]} / {r["n_csv_odds_references"]}')
    ok(r['n_referenced_but_absent_from_raw'] == 0,
       'no CSV row cites an odds id the raw bytes do not carry')
    ok(r['n_raw_never_referenced_by_csv'] == 0,
       'and no raw odds record was dropped on the way into the CSV')
    ok(r['n_field_mismatches'] == 0,
       f'price, line and is_main agree on every one of them: '
       f'{r["n_field_mismatches"]} mismatches')
    ok(r['conserves'], 'so the board is the raw bytes, reshaped, and nothing '
                       'else')


def test_lines_are_exact_and_prices_well_formed():
    s = V()['structural']
    ok(s['malformed_lines'] == [],
       'every line is a plain number, exactly as the book printed it')
    ok(set(s['line_fractional_parts']) <= {'5', '<integer>'},
       f'and every fractional part is .5 or absent: '
       f'{s["line_fractional_parts"]} -- checked on the STRING, because a '
       f'rounded line parses as cleanly as an exact one')
    ok(s['n_malformed_prices'] == 0,
       'every price is an American integer price')
    ok(s['n_duplicate_keys'] == 0,
       'no (game, market, selection, line, main) key appears twice')


def test_market_status_predicts_which_prices_exist():
    s = V()['structural']
    ok(s['status_inconsistent_with_prices'] == {},
       f'market_status determines exactly which price columns are populated, '
       f'with no exceptions: {s["status_to_populated_price_columns"]}. A '
       f'status column that did not would be decoration')


def test_no_price_predates_its_own_retrieval():
    s = V()['structural']
    ok(s['n_rows_retrieved_before_book_last_change'] == 0,
       'no row was retrieved before the book last changed that price, so the '
       'retrieval clock and the feed clock are consistent on all 7,081 rows')


def test_identity_is_deterministic_and_refusals_are_named():
    i = V()['identity']
    ok(i['state'] == 'PASS' and i['n_distinct_market_players'] == 133,
       f'133 distinct priced players, joined against our canonical roster '
       f'({i["by_status"]})')
    ok(i['by_status'].get('MATCHED_CANONICAL') == 130,
       f'130 matched: {i["by_status"]}')
    ok(i['by_status'].get('AMBIGUOUS', 0) == 0,
       'no name answers to two canonical players')
    ok(len(i['unresolved']) == 3,
       f'and the 3 that do not match are NAMED, not dropped: '
       f'{[u["market_name"] for u in i["unresolved"]]}')
    for u in i['unresolved']:
        ok(u['gsis_id'] is None and u['status'] == 'UNMATCHED' and u['note'],
           f'{u["market_name"]} ({u["market_team"]} {u["market_position"]}) '
           f'carries no guessed id and says why')


def test_kickers_absent_from_dk_are_not_reported_as_a_gap():
    o = V()['dk_universe_overlap']
    ok(o['state'] == 'PASS',
       f'the DK Early Only universe is readable ({o.get("dk_universe_rows")} '
       f'rows)')
    ok(o['counts'].get('PRICED_BUT_NOT_ON_THE_DK_BOARD') == 18
       and o['n_of_those_who_are_kickers'] == 16,
       f'18 priced players are not on the DK board and 16 of them are '
       f'kickers, which DraftKings Classic does not roster at all: '
       f'{o["counts"]}')
    ok(len(o['non_kickers_absent']) == 2,
       f'leaving 2 non-kickers, both of them the UNMATCHED names above: '
       f'{[a["market_name"] for a in o["non_kickers_absent"]]}')


def test_gaps_are_measured_not_quoted():
    g = V()['gaps']
    ok(g['anytime_td_over_0_5_present'] is False,
       f'Hard Rock lists no anytime-TD Over 0.5 anywhere in these eight '
       f'games; its Player Touchdowns lines are '
       f'{g["player_touchdown_lines_offered"]}')
    ok(g['receiving_targets_present'] is False,
       'and no receiving-targets market at all')
    ok(g['n_main_rushing_attempts'] == 28 and g['n_main_longest_rush'] == 36,
       f'rushing attempts {g["n_main_rushing_attempts"]} and longest rush '
       f'{g["n_main_longest_rush"]} main rows -- a subset of backs, not all '
       f'of them')


def test_the_source_is_registered_as_delivered_not_captured():
    from nfl.capture import registry as REG
    d = REG.DELIVERED_BY_NAME.get('hardrock_early_1pm_market_board')
    ok(d is not None, 'the board is declared in registry.DELIVERED')
    ok('hardrock_early_1pm_market_board' not in REG.BY_NAME,
       'and NOT in registry.REGISTRY, so owner-delivered bytes create no '
       'recurring capture obligation -- this project holds no endpoint, '
       'credential or schedule for them')
    ok(d and d.forecast_eligible is False and d.why_not,
       'it is forecast_eligible=False with a stated reason')
    note = (d.note if d else '').lower()
    ok(d and 'redistribution' in note and 'not a direct scrape' in note,
       'and its note preserves the redistribution-vs-first-party '
       'distinction rather than flattening it')


def test_no_forecast_stage_imports_this():
    """The wall, walked rather than asserted."""
    import ast
    import collections

    edges = collections.defaultdict(set)
    for p in (_REPO / 'nfl').rglob('*.py'):
        if '__pycache__' in p.parts:
            continue
        try:
            tree = ast.parse(p.read_text())
        except SyntaxError:
            continue
        mod = str(p.relative_to(_REPO)).replace('/', '.')[:-3]
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    edges[mod].add(a.name)
            elif isinstance(n, ast.ImportFrom) and n.module:
                for a in n.names:
                    edges[mod].add(f'{n.module}.{a.name}')
                    edges[mod].add(n.module)

    target = 'nfl.market.early_1pm_hardrock'
    importers = sorted(m for m, deps in edges.items()
                       if target in deps or f'{target}' in
                       {d.rsplit('.', 1)[0] for d in deps if '.' in d})
    forecast = [m for m in importers
                if m.startswith('nfl.production') or m.startswith('nfl.product')
                or m.startswith('nfl.prospective')]
    ok(not forecast,
       f'no module under nfl/production, nfl/product or nfl/prospective '
       f'imports the market board: {forecast or "none"}')
    ok(all(m.startswith('nfl.tests') or m.startswith('nfl.market')
           or m.startswith('nfl.research') or m.startswith('nfl.tools')
           for m in importers),
       f'its only importers are tests, research and tooling: {importers}')


def test_it_is_not_compared_to_a_model_yet():
    v = V()
    ok(v['compared_against_a_model'] is False and v['why_no_comparison_yet'],
       'the artifact states that nothing has been compared and why: there is '
       'no sealed Early Only forecast to compare against, and the 229 '
       'rehearsal distributions are not one')


def main():
    for t in (test_delivered_bytes_are_unchanged,
              test_bundle_checksums,
              test_every_call_returned_data_with_its_provenance,
              test_book_separation_at_the_bytes,
              test_the_slate_is_exactly_the_eight_1pm_games,
              test_every_claimed_count_recomputes,
              test_rows_conserve_against_the_raw_bytes,
              test_lines_are_exact_and_prices_well_formed,
              test_market_status_predicts_which_prices_exist,
              test_no_price_predates_its_own_retrieval,
              test_identity_is_deterministic_and_refusals_are_named,
              test_kickers_absent_from_dk_are_not_reported_as_a_gap,
              test_gaps_are_measured_not_quoted,
              test_the_source_is_registered_as_delivered_not_captured,
              test_no_forecast_stage_imports_this,
              test_it_is_not_compared_to_a_model_yet):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {_P} FAILED {_F}')
    return 1 if _F else 0


if __name__ == '__main__':
    sys.exit(main())
