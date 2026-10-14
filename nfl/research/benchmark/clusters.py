"""Game clusters for the prospective benchmark (BENCH-D4).

A slate's `per_game` block is keyed by game id (season_week_AWAY_HOME) and carries no away/home fields, so the clubs
are read from the id. A club that maps to no game is an error: it is never allowed to become a cluster of its own,
which is what made 8 Classic games score as 16 independent clusters."""


def club_to_game(per_game):
    out = {}
    for gid, v in (per_game or {}).items():
        v = v or {}
        for c in (v.get('away'), v.get('home'), *gid.split('_')[2:4]):
            if c:
                if c in out and out[c] != gid:
                    raise ValueError(f'CLUB_IN_TWO_GAMES {c} {out[c]} {gid}')
                out[c] = gid
    return out


def game_of(club2game, club):
    try:
        return club2game[club]
    except KeyError:
        raise KeyError(f'CLUB_WITHOUT_GAME {club!r}: refusing a club-sized cluster (BENCH-D4)') from None
