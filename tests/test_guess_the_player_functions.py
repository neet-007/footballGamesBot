import pytest
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import func  
from db.models import Game, GuessThePlayer
from games.guess_the_player_functions import cancel_game_guess_the_player, join_game_guess_the_player, new_game_guess_the_player, start_game_guess_the_player, start_round_guess_the_player
import concurrent.futures
from .conftest import new_db, drop_db
from time import sleep

@pytest.mark.parametrize("test_input, expected", [
    ([11, 22, 33], 3),
])
def test_create_different_games(db_session: Session, test_input: list[int], expected: int):
    new_db()
    print("\n=====================\n", "test_create_different_games\n", sep="")
    Session = sessionmaker(bind=db_session.bind)
    for i in test_input:
        print(f"making game num: {i}")
        new_game_guess_the_player(i, Session())

    actual_gtp_count = db_session.query(func.count(GuessThePlayer.chat_id)).scalar() 
    actual_game_count = db_session.query(func.count(Game.chat_id)).scalar() 

    print(f"actual guess the player count vs expected : {actual_gtp_count} vs {expected}")
    print(f"actual game count vs expected : {actual_game_count} vs {expected}")

    assert actual_gtp_count == expected
    assert actual_game_count == expected
    drop_db()
    print("=====================\n")

@pytest.mark.parametrize("test_input, expected", [
    ([11, 22, 22, 11], 2),
])
def test_create_different_games_some_the_same(db_session: Session, test_input: list[int], expected: int):
    new_db()
    print("\n=====================\n", "test_create_different_games_some_the_same\n", sep="")
    Session = sessionmaker(bind=db_session.bind)
    for i in test_input:
        new_game_guess_the_player(i, Session())

    actual_gtp_count = db_session.query(func.count(GuessThePlayer.chat_id)).scalar() 
    actual_game_count = db_session.query(func.count(Game.chat_id)).scalar() 

    print(f"actual guess the player count vs expected : {actual_gtp_count} vs {expected}")
    print(f"actual game count vs expected : {actual_game_count} vs {expected}")

    assert actual_gtp_count == expected
    assert actual_game_count == expected
    drop_db()
    print("=====================\n")

@pytest.mark.parametrize("test_input, expected", [
    ([11, 22, 33, 44], 2),
])
def test_create_different_games_cancel_some(db_session: Session, test_input: list[int], expected: int):
    new_db()
    print("\n=====================\n", "test_create_different_games_cancel_some\n", sep="")
    Session = sessionmaker(bind=db_session.bind)
    for i in test_input:
        new_game_guess_the_player(i, Session())

    for game in test_input[::-1][:len(test_input) // 2]:
        cancel_game_guess_the_player(game, Session())

    actual_gtp_count = db_session.query(func.count(GuessThePlayer.chat_id)).scalar() 
    actual_game_count = db_session.query(func.count(Game.chat_id)).scalar() 

    print(f"actual guess the player count vs expected : {actual_gtp_count} vs {expected}")
    print(f"actual game count vs expected : {actual_game_count} vs {expected}")

    assert actual_gtp_count == expected
    assert actual_game_count == expected
    drop_db()
    print("=====================\n")

@pytest.mark.parametrize("test_input, expected", [
    ([11, 22, 33, 44], 2),
])
def test_join_game_after_cancling(db_session: Session, test_input: list[int], expected: int):
    new_db()
    print("\n=====================\n", "test_join_game_after_cancling\n", sep="")
    Session = sessionmaker(bind=db_session.bind)
    for i in test_input:
        new_game_guess_the_player(i, Session())

    canceld_games = [id for i, id in enumerate(test_input) if i % 2 == 0]

    for game in canceld_games:
        cancel_game_guess_the_player(game, Session())

    for i, game in enumerate(canceld_games):
        res, err = join_game_guess_the_player(game, i, Session())
        assert res is False
        assert err == "no game"

    actual_gtp_count = db_session.query(func.count(GuessThePlayer.chat_id)).scalar() 
    actual_game_count = db_session.query(func.count(Game.chat_id)).scalar() 

    print(f"actual guess the player count vs expected : {actual_gtp_count} vs {expected}")
    print(f"actual game count vs expected : {actual_game_count} vs {expected}")

    assert actual_gtp_count == expected
    assert actual_game_count == expected
    drop_db()
    print("=====================\n")

@pytest.mark.parametrize("test_input, expected", [
    ({
        "games":[11, 22, 33, 44],
        "players":[111, 222, 333, 444],
        "canceld":[22, 44],
        "less_that_expected_player":[33],
    }, 1),
])
def test_start_game_same_players(db_session: Session, test_input: dict[str, list[int]], expected: int):
    new_db()
    print("\n=====================\n", "test_start_game_same_players\n", sep="")
    Session = sessionmaker(bind=db_session.bind)
    for i in test_input["games"]:
        new_game_guess_the_player(i, Session())

    canceld_games = test_input["canceld"]
    less_that_expected_player = test_input["less_that_expected_player"]

    for game in canceld_games:
        cancel_game_guess_the_player(game, Session())

    for game in test_input["games"]:
        if game in less_that_expected_player:
            res, err = join_game_guess_the_player(game, test_input["players"][0], Session())
            assert res is True
            assert err == ""
        else:   
            for player in test_input["players"]:
                res, err = join_game_guess_the_player(game, player, Session())
                if game in canceld_games:
                    assert res is False
                    assert err == "no game"
                else:
                    assert res is True
                    assert err == ""
                
    for game in test_input["games"]:
        res, err, _ = start_game_guess_the_player(game, Session())
        if game in canceld_games:
            assert res is False
            assert err == "no game error"
        elif game in less_that_expected_player:
            assert res is False
            assert err == "number of players is less than 2 or not as expected"
        else:
            assert res is True
            assert err == ""

    actual_gtp_count = db_session.query(func.count(GuessThePlayer.chat_id)).scalar() 
    actual_game_count = db_session.query(func.count(Game.chat_id)).scalar() 

    print(f"actual guess the player count vs expected : {actual_gtp_count} vs {expected}")
    print(f"actual game count vs expected : {actual_game_count} vs {expected}")

    assert actual_gtp_count == expected
    assert actual_game_count == expected
    drop_db()
    print("=====================\n")

@pytest.mark.parametrize("test_input, expected", [
    ({
        "games": [11, 22, 33, 44, 55, 66, 77],
        "players": [111, 222, 333, 444, 555],
        "canceld": [22, 44],
        "less_that_expected_player": [33],
        "game_data": {
            11: {
                "curr_hints": ["h111", "h222", "h333"],
                "curr_answer": "ans11"
            },
            55: {
                "curr_hints": ["h551", "h552", "h553"],
                "curr_answer": "ans55"
            },
            66: {
                "curr_hints": ["h661", "h662", "h663"],
                "curr_answer": "ans66"
            },
            77: {
                "curr_hints": ["h771", "h772", "h773"],
                "curr_answer": "ans77"
            },
        }
    }, 4),
])
def test_start_round_same_players(db_session: Session, test_input: dict[str, list[int]], expected: int):
    Session = sessionmaker(bind=db_session.bind)

    def thread_safe_new_game(game_id):
        session = Session()
        try:
            return new_game_guess_the_player(game_id, session)
        finally:
            session.close()

    def thread_safe_cancel_game(game_id):
        session = Session()
        try:
            return cancel_game_guess_the_player(game_id, session)
        finally:
            session.close()

    def thread_safe_join_game(game_id, player_id):
        session = Session()
        try:
            return join_game_guess_the_player(game_id, player_id, session)
        finally:
            session.close()

    def thread_safe_start_game(game_id):
        session = Session()
        try:
            return start_game_guess_the_player(game_id, session)
        finally:
            session.close()

    def thread_safe_start_round(player, hints, answer):
        session = Session()
        try:
            return start_round_guess_the_player(player, hints, answer, session)
        finally:
            session.close()

    new_db()
    print("\n=====================\n", "test_start_round_same_players\n", sep="")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Create games concurrently
        create_game_futures = [executor.submit(thread_safe_new_game, i) for i in test_input["games"]]

        # Ensure all games are created by checking the result of create_game_futures
        for future in concurrent.futures.as_completed(create_game_futures):
            res, err = future.result()  # This will raise an exception if game creation fails
            print("\n==========================\n", res, err, "\n==========================\n")

        # Cancel games concurrently
        cancel_game_futures = [executor.submit(thread_safe_cancel_game, game) for game in test_input["canceld"]]

        # Ensure all cancel operations are complete
        for future in concurrent.futures.as_completed(cancel_game_futures):
           res, err = future.result()  # This will raise an exception if cancellation fails
           print("\n==========================\n", res, err, "\n==========================\n")

        """
        with Session() as session:
            games = session.query(GuessThePlayer).all()
            for game in games:
                print("\n==========================\n", game, "\n==========================\n")
        """

        # Join players to games concurrently
        join_futures = []
        canceld_join_futures = []
        for game in test_input["games"]:
            if game in test_input["canceld"]:
                for player in test_input["players"]:
                    canceld_join_futures.append(executor.submit(thread_safe_join_game, game, player))
            elif game in test_input["less_that_expected_player"]:
                join_futures.append(executor.submit(thread_safe_join_game, game, test_input["players"][0]))
            else:
                for player in test_input["players"]:
                    join_futures.append(executor.submit(thread_safe_join_game, game, player))

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
        valid_games = [game for game in test_input["games"] if (game not in test_input["canceld"] and game not in test_input["less_that_expected_player"])]
        print("\n==========================\n", valid_games, "\n==========================\n")
        start_game_futures = {game: executor.submit(thread_safe_start_game, game) for game in valid_games}
        curr_players = {}
        for game, future in start_game_futures.items():
            res, err, curr_player = future.result()
            print("\n==========================\n", game, res, err, curr_player, "\n==========================\n")
            assert res is True
            assert err == ""
            assert isinstance(curr_player, int) is True

            curr_players[game] = curr_player


        cancel_game_futures = [executor.submit(thread_safe_cancel_game, game) for game in test_input["canceld"]]
        started_round_games_futres = {}
        game_data = test_input["game_data"]

        
        for game, curr_player in curr_players.items():
            sleep(0.2)
            curr_hints = game_data[game]["curr_hints"]
            curr_answer = game_data[game]["curr_answer"]

            started_round_games_futres[game] = executor.submit(thread_safe_start_round, curr_player, curr_hints, curr_answer)

        game_started = []
        valid_games = []
        for game, future in started_round_games_futres.items():
            res, err , _, game_id = future.result()
            print("\n==========================\n", res, err, game_id, "\n==========================\n")

            assert res is True
            assert err == ""
            valid_games.append(game)
            game_started.append(game_id)
        
        assert sorted(game_started) == sorted(valid_games)

