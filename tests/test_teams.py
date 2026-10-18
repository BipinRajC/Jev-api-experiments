from __future__ import annotations

from collections import Counter
from datetime import date

from src.data.teams import MatchIndex, vote_names


def idx(*rows: tuple[date, int, int, str, str]) -> MatchIndex:
    index: MatchIndex = {}
    for day, hg, ag, home, away in rows:
        index.setdefault((day, hg, ag), []).append((home, away))
    return index


def test_vote_names_links_unique_matches_across_sources() -> None:
    d1, d2 = date(2024, 8, 16), date(2024, 8, 17)
    fotmob = idx((d1, 1, 0, "10", "20"), (d2, 2, 2, "30", "10"))
    football_data = idx((d1, 1, 0, "Man United", "Fulham"), (d2, 2, 2, "Chelsea", "Man United"))
    votes = vote_names(fotmob, football_data)
    assert votes["10"] == Counter({"Man United": 2})
    assert votes["20"] == Counter({"Fulham": 1})
    assert votes["30"] == Counter({"Chelsea": 1})


def test_vote_names_skips_ambiguous_date_and_score() -> None:
    d = date(2024, 8, 17)
    fotmob = idx((d, 1, 1, "1", "2"), (d, 1, 1, "3", "4"))  # two 1-1 draws on one day
    other = idx((d, 1, 1, "A", "B"), (d, 1, 1, "C", "D"))
    assert vote_names(fotmob, other) == {}


def test_vote_names_ignores_matches_missing_from_other_source() -> None:
    fotmob = idx((date(2024, 8, 16), 1, 0, "10", "20"))
    assert vote_names(fotmob, idx((date(2024, 8, 17), 1, 0, "X", "Y"))) == {}


def test_resolve_aliases_drops_stray_votes_and_gives_clashing_alias_to_top_team() -> None:
    from src.data.teams import resolve_aliases

    votes = {
        "tottenham": Counter({"Tottenham": 38, "Stoke": 1}),  # one coincidental (date, score) match
        "stoke": Counter({"Stoke": 36}),
        "parma": Counter({"Parma": 38, "Parma Calcio 1913": 120}),  # a genuine rename keeps both names
    }
    aliases = resolve_aliases(votes)
    assert aliases["tottenham"] == ("Tottenham",)
    assert aliases["stoke"] == ("Stoke",)
    assert aliases["parma"] == ("Parma", "Parma Calcio 1913")


def test_resolve_aliases_alias_claimed_by_two_teams_goes_to_the_one_with_more_votes() -> None:
    from src.data.teams import resolve_aliases

    aliases = resolve_aliases({"a": Counter({"X": 5}), "b": Counter({"X": 9})})
    assert aliases == {"a": (), "b": ("X",)}
