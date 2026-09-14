"""Three guards on postgame ingestion: FINALITY, UNIT OF EVIDENCE, REVISION.

WHAT THESE TESTS PROTECT.

  * COMPLETION MEANS FINAL, NOT KICKOFF-PASSED. The first version scored any
    sealed game whose kickoff clock had passed. A game in progress, suspended,
    postponed, or published with only part of its play-by-play would have been
    scored against a part-played realisation and the shortfall would have read
    as forecast error. The regression test here is exactly that case: kickoff
    in the past, partial play-by-play present, game not final. It must produce
    ZERO scoring rows.

  * ROWS ARE NOT A SAMPLE SIZE. Nineteen sealed forecasts across two completed
    games make thousands of rows and two games of evidence. Five candidate
    variants of one game must count as one game, and a floor must say which
    unit it counts in.

  * AN OUTCOME CAN BE REVISED. Only one version per forecast x metric x
    subject may be CURRENT. The superseded version stays in the file and is
    never deleted, and aggregates must not count it twice.

EVERY SYNTHETIC CASE RUNS IN A TEMPORARY STORE. Nothing here writes into the
live ledger or the live postgame directory.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import pathlib
import shutil
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.research import postgame as PG                              # noqa: E402
from nfl.research import sealed_index as SI                          # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


# ------------------------------------------------------------- fixtures
def _real_blob():
    """A stored play-by-play blob that this repository has SEALED FORECASTS for.

    This used to be `sorted(...)[0]`, which silently assumed the store held
    exactly one season. Once historical seasons were fetched for the QB
    participation audit the alphabetically-first blob became pbp_2021, a season
    with no sealed forecasts at all -- so the partial-PBP regression picked a
    game nothing had forecast, `games_not_final` came back empty, and the test
    raised IndexError instead of checking anything. The fixture now asks for
    what it actually needs rather than trusting file order.
    """
    hits = sorted(PG.STORE.glob('pbp_*.csv.gz'))
    if not hits:
        return None
    seal_seasons = {str(s.get('game_id', ''))[:4]
                    for s in PG.completed_with_seals()}
    for b in reversed(hits):
        if b.name.split('_')[1][:4] in seal_seasons:
            return b
    return hits[-1]


def _real_rows():
    b = _real_blob()
    return PG._rows(b) if b else []


def _by_game(rows):
    out = {}
    for r in rows:
        out.setdefault(r.get('game_id'), []).append(r)
    return out


def _write_blob(d: pathlib.Path, rows, games, name='pbp_synth.csv.gz'):
    """A stored outcome artifact plus its provenance, inside a sandbox."""
    d.mkdir(parents=True, exist_ok=True)
    blob = d / name
    cols = list(rows[0].keys()) if rows else ['game_id']
    buf = gzip.open(blob, 'wt', newline='')
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    buf.close()
    digest = hashlib.sha256(blob.read_bytes()).hexdigest()
    blob.with_suffix('.provenance.json').write_text(json.dumps({
        'artifact': 'NFL_POSTGAME_OUTCOME_PROVENANCE',
        'spec_version': PG.SPEC_VERSION, 'source_name': 'nflverse_pbp',
        'source_rank': 1, 'source_url': 'synthetic://test',
        'retrieved_at': '2026-09-11T00:00:00+00:00', 'sha256': digest,
        'n_bytes': blob.stat().st_size, 'blob': str(blob),
        'games': sorted(games), 'season': 2026, 'already_present': False,
    }, indent=1) + '\n')
    return blob


class _Sandbox:
    """Redirect the module's ledger and store at once, and put them back."""

    def __enter__(self):
        self.d = pathlib.Path(tempfile.mkdtemp(prefix='pg_guard_'))
        self._ledger, self._store = PG.LEDGER, PG.STORE
        PG.STORE = self.d
        PG.LEDGER = self.d / 'PROSPECTIVE_LEDGER.jsonl'
        return self.d

    def __exit__(self, *a):
        PG.LEDGER, PG.STORE = self._ledger, self._store
        shutil.rmtree(self.d, ignore_errors=True)
        return False


def _row(admissible=True, **kw):
    """A scoring row, with its ADMISSIBILITY STATE stated explicitly.

    `accounting` counts only rows that `score_game` stamped
    `currently_admissible` under the contract in force at scoring time. A
    fixture therefore has to say which it represents:

      admissible=True   a row scored under the CURRENT contract. Use for
                        tests about counting arithmetic, so they measure the
                        arithmetic rather than the gate.
      admissible=False  a row written before the stamp existed -- the shape
                        of the 3,230 rows already on the ledger. Use to
                        assert that such rows count toward nothing.

    The stamp is NOT applied blanket-wise: `test_l_...` below asserts that the
    unstamped shape contributes zero, which would be vacuous if every fixture
    were admissible.
    """
    base = {'forecast_id': 'FC-a', 'game_id': 'G1', 'entity': 'player',
            'metric': 'qb/pyds', 'player_id': 'P1', 'team': None,
            'outcome_hash': 'h1', 'candidate': 'V1', 'cutoff_utc': 'T0'}
    if admissible:
        base['currently_admissible'] = True
    base.update(kw)
    return base


# =================================================== GUARD 1 -- FINALITY
def test_a_finality_is_proven_from_the_bytes_not_from_a_clock():
    by = _by_game(_real_rows())
    if not by:
        check('a stored outcome artifact exists to test finality against',
              False, 'no pbp_*.csv.gz in the postgame store')
        return
    for gid, rows in sorted(by.items()):
        v = PG.game_finality(rows)
        check(f'{gid} is FINAL and says so', v['final'] and
              v['code'] == 'POSTGAME_FINAL', str(v['unmet']))
    check('a game with no play rows is NOT final',
          PG.game_finality([])['unmet'] == ['NO_PLAY_ROWS'])
    check('  and it is named, not reported as a 0-0 result',
          'postponed' in PG.game_finality([])['detail'])
    check('every required signal carries an explanation',
          all(len(note) > 30 for _, note in PG.FINALITY_SIGNALS),
          f'{len(PG.FINALITY_SIGNALS)} signals')
    check('the named state is POSTGAME_NOT_FINAL', PG.NOT_FINAL ==
          'POSTGAME_NOT_FINAL')


def test_b_each_unfinished_shape_is_refused_by_its_own_name():
    by = _by_game(_real_rows())
    gid = sorted(by)[0] if by else None
    if not gid:
        check('a real game is available to truncate', False)
        return
    rows = by[gid]

    partial = rows[:len(rows) // 2]
    v = PG.game_finality(partial)
    check('partial play-by-play is NOT final', not v['final'], v['code'])
    check('  and the missing END GAME marker is named',
          'END_GAME_MARKER_PRESENT' in v['unmet'], str(v['unmet']))

    in_progress = [dict(r) for r in rows[:20]]
    for r in in_progress:
        r['qtr'] = '2'
        r['game_seconds_remaining'] = '1400'
    v = PG.game_finality(in_progress)
    check('an in-progress game is NOT final', not v['final'])
    check('  the unexpired clock is named',
          'GAME_CLOCK_EXPIRED' in v['unmet'], str(v['unmet']))
    check('  the incomplete regulation is named',
          'REGULATION_OR_LATER_COMPLETE' in v['unmet'], str(v['unmet']))

    blank = [dict(r) for r in rows]
    for r in blank:
        r['result'] = ''
    v = PG.game_finality(blank)
    check('an unpopulated result is NOT final', not v['final'])
    check('  and is named', 'FINAL_RESULT_POPULATED' in v['unmet'],
          str(v['unmet']))

    bad = [dict(r) for r in rows]
    bad[-1]['result'] = str(float(bad[-1]['result']) + 7)
    v = PG.game_finality(bad)
    check('a scoreboard disagreeing with its own result is NOT final',
          not v['final'])
    check('  and is named',
          'SCOREBOARD_AGREES_WITH_RESULT' in v['unmet'], str(v['unmet']))
    check('the refusal detail states that kickoff-passed is not enough',
          'eligible for checking' in v['detail'])


def test_c_kickoff_in_the_past_with_partial_pbp_scores_zero_rows():
    """THE REGRESSION TEST THE GUARD EXISTS FOR.

    A game whose kickoff is long past, whose play-by-play is present but
    partial, and which is therefore not final. Expected: zero scoring rows,
    and the reason recorded by name in the emitted artifact.
    """
    by = _by_game(_real_rows())
    if not by:
        check('a real game is available for the partial-PBP regression',
              False)
        return
    # A GAME THIS REPOSITORY ACTUALLY FORECAST. `games_not_final` only records
    # games that have sealed forecasts, so picking one without any made the
    # assertions below vacuous.
    _with_seals = {s['game_id'] for s in PG.completed_with_seals()}
    _usable = sorted(g for g in by if g in _with_seals)
    if not _usable:
        check('a real game WITH sealed forecasts is available for the '
              'partial-PBP regression', False, f'{len(by)} game(s) in blob')
        return
    gid = _usable[0]
    partial = by[gid][:len(by[gid]) // 2]

    seals = [s for s in PG.completed_with_seals() if s['game_id'] == gid]
    check('the game has sealed forecasts and a kickoff already past',
          bool(seals), f'{len(seals)} sealed for {gid}')

    with _Sandbox() as d:
        blob = _write_blob(d, partial, [gid])
        o = PG.run(out_dir=d, blob=str(blob))
        check('the run still completes', o.state is State.PASS,
              f'{o.state.name}[{o.code}]')
        st = json.loads((d / 'POSTGAME_STATUS.json').read_text())
        check('ZERO scoring rows were added', st['scoring_rows_added'] == 0,
              str(st['scoring_rows_added']))
        check('  and no game was scored', st['n_games_scored'] == 0,
              str(st['n_games_scored']))
        check('  the ledger stayed empty', not PG.LEDGER.exists() or
              PG.LEDGER.read_text().strip() == '')
        nf = st['games_not_final']
        check('the game is recorded as NOT FINAL', len(nf) == 1 and
              nf[0]['game_id'] == gid, str([n['game_id'] for n in nf]))
        check('  under the named state POSTGAME_NOT_FINAL',
              nf[0]['code'] == 'POSTGAME_NOT_FINAL', nf[0]['code'])
        check('  naming the missing END GAME marker',
              'END_GAME_MARKER_PRESENT' in nf[0]['unmet'],
              str(nf[0]['unmet']))
        check('  and saying how many seals it skipped',
              nf[0]['n_sealed_forecasts_skipped'] == len(seals),
              str(nf[0]['n_sealed_forecasts_skipped']))

        # The gate is inside score_game too, so a direct caller cannot
        # route around the run-level check.
        if seals:
            o2 = PG.score_game(seals[0], partial, 'd' * 64)
            check('score_game itself refuses a non-final game',
                  o2.state is State.BLOCKED and o2.code == 'POSTGAME_NOT_FINAL',
                  f'{o2.state.name}[{o2.code}]')
            check('  and reports zero scored', o2.evidence['n_scored'] == 0)


# ========================================== GUARD 2 -- UNIT OF EVIDENCE
def test_d_five_candidates_on_one_game_are_one_game():
    rows = [_row(forecast_id=f'FC-{i}', candidate=f'R{i}') for i in range(5)]
    a = PG.accounting(rows)
    check('distinct_games is 1, not 5', a['distinct_games'] == 1,
          str(a['distinct_games']))
    check('distinct_candidate_forecasts is 5', 
          a['distinct_candidate_forecasts'] == 5,
          str(a['distinct_candidate_forecasts']))
    check('scoring_rows is 5 and is kept separate', a['scoring_rows'] == 5)
    check('distinct_player_games is 1', a['distinct_player_games'] == 1,
          str(a['distinct_player_games']))
    check('the prospective sample size is the GAME count',
          a['prospective_sample_size']['value'] == 1 and
          a['prospective_sample_size']['unit'] == 'GAME',
          str(a['prospective_sample_size']))
    check('  and it says rows are not that number',
          'not this number' in a['prospective_sample_size']['note'])
    check('candidate variants are declared PAIRED, not independent',
          'paired' in a['paired_note'].lower() and
          'not independent games' in a['paired_note'].lower())


def test_e_every_count_declares_its_unit_and_floors_declare_theirs():
    a = PG.accounting([_row()])
    for k in ('scoring_rows', 'graded_metrics', 'distinct_games',
              'distinct_player_games', 'distinct_candidate_forecasts'):
        check(f'{k} is reported and has a declared unit',
              k in a and k in a['units'] and len(a['units'][k]) > 20)
    check('the row unit says explicitly that it is NOT a sample size',
          'NEVER a prospective sample size' in a['units']['scoring_rows'])
    check('a floor counts in games, and says so',
          a['floor_unit'] == 'distinct_games' and
          PG.FLOOR_UNIT == 'distinct_games', a['floor_unit'])
    check('two player-games across two games count as two',
          PG.accounting([_row(game_id='G1'), _row(game_id='G2')]
                        )['distinct_player_games'] == 2)
    check('two players in one game are one game',
          PG.accounting([_row(player_id='P1'), _row(player_id='P2')]
                        )['distinct_games'] == 1)


def test_f_the_live_ledger_carries_the_unit_of_evidence_on_every_row():
    rows = PG.load_ledger()
    if not rows:
        check('the live ledger has rows to inspect', False)
        return
    need = ('game_id', 'forecast_id', 'candidate', 'cutoff_utc', 'metric',
            'outcome_hash')
    for f in need:
        n = sum(1 for r in rows if f in r)
        check(f'every row carries {f}', n == len(rows), f'{n}/{len(rows)}')
    check('every player row carries player_id',
          all('player_id' in r for r in rows if r.get('entity') == 'player'))
    check('the full outcome hash is stored, not only its prefix',
          all(len(str(r.get('outcome_hash', ''))) == 64 for r in rows))
    check('a row with no declared cutoff names that fact rather than '
          'omitting the field',
          all(r.get('cutoff_basis') for r in rows),
          str({r.get('cutoff_basis') for r in rows}))
    check('sealed_dir is repository-relative, not machine-specific',
          not any(str(r.get('sealed_dir', '')).startswith('/')
                  for r in rows))


def test_g_the_emitted_status_artifact_reports_units_separately():
    p = PG.STORE / 'POSTGAME_STATUS.json'
    if not p.exists():
        check('a status artifact exists to inspect', False)
        return
    st = json.loads(p.read_text())
    ev = st.get('evidence') or {}
    check('the artifact carries an evidence block', bool(ev))
    # THE POINT IS THAT ROWS ARE NOT A SAMPLE SIZE, AND THERE ARE TWO WAYS
    # THE ARTIFACT CAN DEMONSTRATE IT.
    #
    # This used to require counted evidence -- more forecasts than games, rows
    # unequal to games -- which held only while the ledger carried rows the
    # contract still counts. It now carries 3,230 rows that predate the
    # admissibility stamp and therefore count toward NOTHING, and the checks
    # read that as a defect. It is the opposite: an evidence block reporting
    # zero games beside a ledger of 3,230 rows is the strongest statement of
    # "a row is not a game" this artifact can make. What must be true either
    # way is that the units are reported SEPARATELY and that excluded rows are
    # NAMED rather than silently dropped.
    on_ledger = ev.get('rows_on_ledger')
    unstamped = ev.get('rows_without_admissibility_verdict')
    if ev.get('scoring_rows'):
        check('  with games and rows as separate numbers',
              ev.get('distinct_games') != ev.get('scoring_rows'),
              f"{ev.get('distinct_games')} games / {ev.get('scoring_rows')} "
              f"rows")
        check('  nineteen sealed forecasts are not nineteen games',
              ev.get('distinct_candidate_forecasts', 0) >
              ev.get('distinct_games', 0),
              f"{ev.get('distinct_candidate_forecasts')} forecasts / "
              f"{ev.get('distinct_games')} games")
    else:
        check('  counted evidence is zero, so the artifact must say WHY',
              on_ledger is not None and unstamped is not None,
              f'rows_on_ledger={on_ledger} unstamped={unstamped}')
        check('  and the rows that count for nothing are NAMED, not dropped',
              bool(on_ledger) and unstamped == on_ledger,
              f'{unstamped} of {on_ledger} carry no admissibility verdict')
        check('  and the artifact explains what the stamp means',
              'admissib' in str(ev.get('admissibility_note', '')).lower())
    check('  and a sample size declared in GAME units',
          (ev.get('prospective_sample_size') or {}).get('unit') == 'GAME')
    check('the finality signals required are published in the artifact',
          len(st.get('finality_signals_required') or []) ==
          len(PG.FINALITY_SIGNALS))


# ============================================== GUARD 3 -- SUPERSESSION
def test_h_a_revised_outcome_supersedes_without_deleting():
    old = _row(outcome_hash='a' * 64)
    new = _row(outcome_hash='b' * 64)
    v = PG.versioned([old, new])
    check('both versions survive', len(v) == 2)
    check('the later version is CURRENT',
          v[1]['version_status'] == 'CURRENT', v[1]['version_status'])
    check('the earlier version is SUPERSEDED',
          v[0]['version_status'] == 'SUPERSEDED', v[0]['version_status'])
    check('  and names the hash that superseded it',
          v[0]['superseded_by_outcome_hash'] == 'b' * 64,
          str(v[0]['superseded_by_outcome_hash'])[:8])
    check('the current version is superseded by nothing',
          v[1]['superseded_by_outcome_hash'] is None)
    check('both rows know how many versions exist',
          all(r['n_outcome_versions'] == 2 for r in v))
    cur = PG.current_rows([old, new])
    check('calibration reads the CURRENT version only', len(cur) == 1 and
          cur[0]['outcome_hash'] == 'b' * 64)
    check('an audit can read every version',
          len(PG.all_versions([old, new])) == 2)
    check('a revision does NOT inflate the game count',
          PG.accounting(cur)['distinct_games'] == 1 and
          PG.accounting(cur)['scoring_rows'] == 1)


def test_i_supersession_is_per_forecast_metric_and_subject():
    a = _row(outcome_hash='a' * 64)
    b = _row(outcome_hash='b' * 64, metric='qb/att')
    c = _row(outcome_hash='c' * 64, player_id='P2')
    d = _row(outcome_hash='d' * 64, forecast_id='FC-b')
    v = PG.versioned([a, b, c, d])
    check('a different metric is not a revision',
          all(r['version_status'] == 'CURRENT' for r in v),
          str([r['version_status'] for r in v]))
    check('the identity is named in full',
          set(PG.VERSION_IDENTITY) == {'forecast_id', 'game_id', 'entity',
                                       'metric', 'player_id', 'team', 'arm'},
          str(PG.VERSION_IDENTITY))
    # `arm` JOINED THE IDENTITY BECAUSE LEAVING IT OUT LOST AN ARM. Two arms
    # of one side-by-side forecast share forecast_id, game, entity, metric,
    # player and team, so without `arm` the second arm was read as a revision
    # of the first and marked SUPERSEDED.
    two_arms = PG.versioned([_row(arm='R8_PRODUCTION'),
                             _row(arm='Q9_HURDLE')])
    check('two arms of one forecast are not revisions of each other',
          all(r['version_status'] == 'CURRENT' for r in two_arms),
          str([r['version_status'] for r in two_arms]))
    revised = PG.versioned([_row(arm='R8_PRODUCTION'),
                            _row(arm='R8_PRODUCTION',
                                 outcome_hash='e' * 64)])
    check('  but a restated outcome for ONE arm still supersedes',
          [r['version_status'] for r in revised]
          == ['SUPERSEDED', 'CURRENT'],
          str([r['version_status'] for r in revised]))
    legacy = PG.versioned([_row(), _row(outcome_hash='e' * 64)])
    check('  and a row with no arm key keeps the identity it always had',
          [r['version_status'] for r in legacy] == ['SUPERSEDED', 'CURRENT'])
    idx = PG.supersession_index([a, _row(outcome_hash='z' * 64)])
    check('the index counts revised identities', idx['n_identities_revised'] == 1,
          str(idx['n_identities_revised']))
    check('  and records the superseded hashes',
          list(idx['revised'].values())[0]['superseded_outcome_hashes'] ==
          ['a' * 64])
    check('the rule states nothing is deleted',
          'never deleted' in idx['rule'])


def test_j_the_live_ledger_has_exactly_one_current_version_per_identity():
    rows = PG.load_ledger()
    if not rows:
        check('the live ledger has rows to inspect', False)
        return
    v = PG.versioned(rows)
    seen = {}
    for r in v:
        if r['version_status'] == 'CURRENT':
            k = PG._version_identity(r)
            seen[k] = seen.get(k, 0) + 1
    check('no identity has two CURRENT versions',
          all(n == 1 for n in seen.values()),
          str(sum(1 for n in seen.values() if n > 1)))
    check('every row is labelled one way or the other',
          all(r['version_status'] in ('CURRENT', 'SUPERSEDED') for r in v))


# =========================================== GUARD 4 -- REPRODUCTION
def test_k_the_two_completed_games_are_now_refused_as_inadmissible():
    """The reproduction property, under the CURRENT admissibility contract.

    THIS TEST WAS INVERTED, DELIBERATELY, AND NOT WEAKENED.

    It used to assert `n_games_scored == 2`. That expectation was written when
    `score_game` gated on FINALITY ALONE. It now also re-evaluates current
    admissibility, and the two completed games -- 2026_01_NE_SEA and
    2026_01_SF_LA -- fail it: their artifacts carry no `seal_path`, are
    PARTIAL_PLAYER_COVERAGE, and declare `prospective_eligible: false` on
    themselves.

    So the correct current assertion is that both are REFUSED BY NAME, that
    the refusal is the admissibility one rather than the finality one, and
    that ZERO rows are written. Restoring the old number would mean removing
    the gate, which is the opposite of what the audit established.
    """
    blob = _real_blob()
    if not blob:
        check('a stored authoritative outcome exists', False)
        return
    with _Sandbox() as d:
        first = PG.run(out_dir=d, blob=str(blob))
        e1 = first.evidence
        check('the run completes rather than raising',
              first.state in (State.PASS, State.BLOCKED),
              f'{first.state.name}[{first.code}]')
        check('ZERO games are scored -- both are inadmissible today',
              e1['n_games_scored'] == 0, str(e1['n_games_scored']))
        check('  and ZERO rows are written',
              e1['scoring_rows_added'] == 0, str(e1['scoring_rows_added']))

        # THE REFUSAL IS THE ADMISSIBILITY ONE, NOT FINALITY. Both games ARE
        # final; asserting only "zero scored" would pass for the wrong reason.
        sealed = [r for r in PG.completed_with_seals()
                  if r.get('game_id') in ('2026_01_NE_SEA', '2026_01_SF_LA')]
        check('the two completed games still have sealed forecasts',
              len(sealed) >= 2, f'{len(sealed)} sealed record(s)')
        rows = PG._rows(blob)
        by = _by_game(rows)
        codes, finals = set(), set()
        for rec in sealed[:6]:
            gid = rec.get('game_id')
            if gid not in by:
                continue
            fin = PG.game_finality(by[gid])
            finals.add(bool(fin['final']))
            o = PG.score_game(rec, by[gid], 'a' * 64, finality=fin)
            codes.add(o.code)
        check('  the games ARE final -- so this is not a finality refusal',
              finals == {True}, str(finals))
        check('  and every one refuses as NOT CURRENTLY ADMISSIBLE',
              codes == {PG.POSTGAME_INADMISSIBLE}, str(sorted(codes)))
        check('  which is a different code from the finality refusal',
              PG.POSTGAME_INADMISSIBLE != PG.NOT_FINAL)

    # THE HISTORICAL LEDGER IS PRESERVED AND COUNTS ZERO.
    #
    # OUTSIDE the sandbox on purpose: `_Sandbox` redirects PG.LEDGER to a temp
    # directory, so these assertions read the real committed ledger rather
    # than the empty one the sandbox created.
    on_disk = len(PG.LEDGER.read_text().splitlines()) if \
        PG.LEDGER.exists() else 0
    check('the historical ledger rows are still physically on disk',
          on_disk >= 3230, str(on_disk))
    acc = PG.accounting(PG.load_ledger())
    check('  and every one lacks an admissibility verdict',
          acc['rows_without_admissibility_verdict'] == acc['rows_on_ledger'],
          f"{acc['rows_without_admissibility_verdict']} of "
          f"{acc['rows_on_ledger']}")
    check('  so the counted prospective sample is ZERO games',
          acc['distinct_games'] == 0
          and acc['prospective_sample_size']['value'] == 0,
          str(acc['prospective_sample_size']['value']))
    check('  NOT by deletion -- nothing was removed',
          acc['rows_on_ledger'] == on_disk)

    # NON-VACUOUS: the counter still counts a row that IS stamped.
    stamped = [dict(r, currently_admissible=True)
               for r in PG.load_ledger()[:20]]
    acc2 = PG.accounting(stamped)
    check('  and the counter is not vacuous: stamped rows DO count',
          acc2['scoring_rows'] == 20, str(acc2['scoring_rows']))


def test_l_the_migration_to_the_unit_of_evidence_was_lossless():
    p = PG.STORE / 'LEDGER_MIGRATION.json'
    if not p.exists():
        check('the migration report exists', False, str(p))
        return
    m = json.loads(p.read_text())
    check('every predecessor row was reproduced',
          m['n_v1_rows_not_reproduced'] == 0,
          str(m['n_v1_rows_not_reproduced']))
    check('no reproduced value changed',
          m['n_v1_rows_whose_values_changed'] == 0,
          str(m['n_v1_rows_whose_values_changed']))
    check('the migration declares itself lossless', m['lossless'] is True)
    pred = PG.STORE / pathlib.Path(m['predecessor_preserved']).name
    check('the predecessor ledger is preserved on disk', pred.exists(),
          str(pred))
    check('  with the same number of rows it had',
          len(pred.read_text().splitlines()) == m['predecessor_rows'],
          str(m['predecessor_rows']))
    check('the one deliberate field change is named',
          'sealed_dir' in m['deliberate_field_changes'])


def test_m_sealed_forecasts_carry_the_identity_the_ledger_needs():
    recs = SI.discover_all()
    check('sealed artifacts are discoverable', bool(recs), str(len(recs)))
    for f in ('forecast_id', 'candidate', 'cutoff_utc', 'cutoff_basis',
              'cutoff_regime', 'run_id', 'rel_dir'):
        check(f'every sealed record carries {f}',
              all(f in r for r in recs))
    ids = [r['forecast_id'] for r in recs]
    check('forecast ids are unique per sealed directory',
          len(set(ids)) == len(ids), f'{len(set(ids))} of {len(ids)}')
    check('a pre-inactives and a post-inactives board differ in forecast id',
          len({r['forecast_id'] for r in recs
               if r['cutoff_regime'] == 'PRE_INACTIVES'} &
              {r['forecast_id'] for r in recs
               if r['cutoff_regime'] == 'POST_INACTIVES'}) == 0)
    check('no record silently defaults its cutoff basis',
          all(r['cutoff_basis'] for r in recs))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
