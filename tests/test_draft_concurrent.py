from random import randint
from time import sleep
import pytest
from sqlalchemy.orm import Session, sessionmaker
import concurrent.futures
from db.connection import new_db
from games.draft_functions import new_game_draft, join_game_draft, cancel_game_draft, start_game_draft, set_game_states_draft, add_pos_to_team_draft, rand_team_draft
from tests.conftest import LEAN_SLEEP_TIME

def thread_safe_new_game(game_id, Session):
    session = Session()
    try:
        return new_game_draft(game_id, session)
    finally:
        session.close()

def thread_safe_cancel_game(game_id, Session):
    session = Session()
    try:
        return cancel_game_draft(game_id, session)
    finally:
        session.close()

def thread_safe_join_game(game_id, player_id, Session):
    session = Session()
    try:
        return join_game_draft(game_id, player_id, session)
    finally:
        session.close()

def thread_safe_start_game(game_id, Session):
    session = Session()
    try:
        return start_game_draft(game_id, session)
    finally:
        session.close()

def thread_safe_set_game_state(game_id, player_id, category, teams, formation, Session):
    session = Session()
    try:
        return set_game_states_draft(game_id, player_id, category, teams, formation, session)
    finally:
        session.close()

def thread_safe_add_pos_to_team(game_id, player_id, added_player, Session):
    session = Session()
    try:
        return add_pos_to_team_draft(game_id, player_id, added_player, session)
    finally:
        session.close()

def thread_safe_rand_team(game_id, player_id, Session):
    session = Session()
    try:
        return rand_team_draft(game_id, player_id, session)
    finally:
        session.close()

@pytest.mark.parametrize("test_input, expected", [
    ({
        "games": [11, 22, 33, 44, 55, 66, 77, 88, 99],
        "players": [111, 222, 333, 444, 555],
        "canceld": [22, 44],
        "less_that_expected_player": [33],
        "wrong_formation":[88],
        "game_data": {
            11: {
                "category":'cat 1',
                "formation":"433",
                "teams":["aa", "bb", "cc", "dd", "ee", "ff", "gg", "hh", "ii", "jj", "kk", "ll", "mm", "nn", "oo", "pp"],
            },
            55: {
                "category":'cat 5',
                "formation":"4231",
                "teams":["aa", "bb", "cc", "dd", "ee", "ff", "gg", "hh", "ii", "jj", "kk", "ll", "mm", "nn", "oo", "pp"],
            },
            66: {
                "category":'cat 6',
                "formation":"532",
                "teams":["bb", "bb", "cc", "dd", "ee", "ff", "gg", "hh", "ii", "jj", "kk", "ll", "mm", "nn", "oo", "pp"],
            },
            77: {
                "category":'cat 7',
                "formation":"442",
                "teams":["aa", "bb", "cc", "dd", "ee", "ff", "gg", "hh", "ii", "jj", "kk", "ll", "mm", "nn", "oo", "pp"],
            },
            88: {
                "category":'cat 8',
                "formation":"632",
                "teams":["aa", "bb", "cc", "dd", "ee", "ff", "gg", "hh", "ii", "jj", "kk", "ll", "mm", "nn", "oo", "pp"],
            },
            99: {
                "category":'cat 9',
                "formation":"632",
                "teams":["bb", "cc", "dd", "ff", "ee", "gg", "hh", "ii", "jj", "kk", "ll", "mm", "nn", "oo", "pp"],
            },
        }
    }, 4),
])
def test_start_game_same_players(db_session: Session, test_input: dict[str, dict[int, dict[str, str]]], expected: int):
    Session = sessionmaker(bind=db_session.bind)
    new_db()
    print("\n=====================\n", "test_start_round_same_players\n", sep="")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Create games concurrently
        create_game_futures = [executor.submit(thread_safe_new_game, i, Session) for i in test_input["games"]]

        # Ensure all games are created by checking the result of create_game_futures
        for future in concurrent.futures.as_completed(create_game_futures):
            res, err = future.result()  # This will raise an exception if game creation fails
            print("\n==========================\n", res, err, "\n==========================\n")

        # Cancel games concurrently
        cancel_game_futures = [executor.submit(thread_safe_cancel_game, game, Session) for game in test_input["canceld"]]

        # Ensure all cancel operations are complete
        for future in concurrent.futures.as_completed(cancel_game_futures):
           res, err = future.result()  # This will raise an exception if cancellation fails
           print("\n==========================\n", res, err, "\n==========================\n")

        # Join players to games concurrently
        join_futures = []
        canceld_join_futures = []
        for game in test_input["games"]:
            if game in test_input["canceld"]:
                for player in test_input["players"]:
                    canceld_join_futures.append(executor.submit(thread_safe_join_game, game, player, Session))
            elif game in test_input["less_that_expected_player"]:
                join_futures.append(executor.submit(thread_safe_join_game, game, test_input["players"][0], Session))
            else:
                for player in test_input["players"]:
                    join_futures.append(executor.submit(thread_safe_join_game, game, player, Session))

        # Verify results for joining games
        for i, future in enumerate(concurrent.futures.as_completed(join_futures)):
            res, err = future.result()
            print("\n==========================\n", i, res, err, "\n==========================\n")
            assert res is True
            assert err == ""

        for future in concurrent.futures.as_completed(canceld_join_futures):
            res, err = future.result()
            print("\n==========================\n", res, err, "\n==========================\n")
            assert res is False
            assert err == "no game"

        # Start games concurrently
        game_data = test_input["game_data"]
        num_players = len(test_input["players"])
        """
        valid_games = [
            game for game in test_input["games"]
            if (
                game not in test_input["canceld"]
                and game not in test_input["less_that_expected_player"]
                and not any(len(team) != len(set(team)) for team in test_input["game_data"][game]["teams"])
                and all(len(team) == 11 + len(test_input["players"]) for team in test_input["game_data"][game]["teams"])
            )
        ]
        """
        valid_games = []
        for game in test_input["games"]:
            if game in test_input["canceld"]:
                continue
            if game in test_input["less_that_expected_player"]:
                continue
            if game in test_input["wrong_formation"]:
                continue
            if len(game_data[game]["teams"]) != len(set(game_data[game]["teams"])):
                continue
            if len(game_data[game]["teams"]) != 11 + num_players:
                continue

            valid_games.append(game)

        print("\n==========================\n", valid_games, "\n==========================\n")
        start_game_futures = {game: executor.submit(thread_safe_start_game, game, Session) for game in valid_games}
        for game, future in start_game_futures.items():
            res, err, num_players_ = future.result()
            print("\n==========================\n", game, res, err, num_players, "\n==========================\n")
            assert res is True
            assert err == ""
            assert num_players_ == num_players

        cancel_game_futures = [executor.submit(thread_safe_cancel_game, game, Session) for game in test_input["canceld"]]
        state_set_games_futres = {}

        for game in valid_games:
            sleep(LEAN_SLEEP_TIME)
            category = game_data[game]["category"]
            formation = game_data[game]["formation"]
            teams= game_data[game]["teams"]

            state_set_games_futres[game] = executor.submit(thread_safe_set_game_state ,game, test_input["players"][0], category, teams, formation, Session)

        for game, future in state_set_games_futres.items():
            res, err, other = future.result()
            print("\n==========================\n", res, err, other, "\n==========================\n")

            category = game_data[game]["category"]
            formation = game_data[game]["formation"]
            teams= game_data[game]["teams"]

            assert res is True
            assert err == ""
            assert other[:-1] == [num_players, category, formation, " ".join([team.lower() for team in teams])]
            assert (other[-1] in test_input["players"]) is True
        
        print("=====================\n")

