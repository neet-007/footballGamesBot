from random import randint
from time import sleep
import pytest
from sqlalchemy.orm import Session, sessionmaker
import concurrent.futures
from db.models import GuessThePlayer
from tests.conftest import LEAN_SLEEP_TIME, create_game_with_retry_guess_the_player, thread_safe_cancel_game_guess_the_player, thread_safe_end_game_guess_the_player, thread_safe_end_round, thread_safe_end_round_guess_the_player, thread_safe_join_game_guess_the_player, thread_safe_proccess_answer_guess_the_player, thread_safe_start_game_guess_the_player, thread_safe_start_round_guess_the_player

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
def test_end_round_same_players(db_session: Session, test_input: dict[str, list[int]], expected: int):
    Session = sessionmaker(bind=db_session.bind)

    print("\n=====================\n", "test_start_round_same_players\n", sep="")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Create games concurrently
        create_game_futures = [executor.submit(create_game_with_retry_guess_the_player, i, 1, Session) for i in test_input["games"]]

        # Ensure all games are created by checking the result of create_game_futures
        for future in concurrent.futures.as_completed(create_game_futures):
            res, err = future.result()  # This will raise an exception if game creation fails
            print("\n==========================\n", res, err, "\n==========================\n")

        # Cancel games concurrently
        cancel_game_futures = [executor.submit(thread_safe_cancel_game_guess_the_player, game, Session) for game in test_input["canceld"]]

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
                    canceld_join_futures.append(executor.submit(thread_safe_join_game_guess_the_player, game, player, Session))
            elif game in test_input["less_that_expected_player"]:
                join_futures.append(executor.submit(thread_safe_join_game_guess_the_player, game, test_input["players"][0], Session))
            else:
                for player in test_input["players"]:
                    join_futures.append(executor.submit(thread_safe_join_game_guess_the_player, game, player, Session))

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
        start_game_futures = {}
        for game in valid_games:
            sleep(2)
            start_game_futures[game] = executor.submit(thread_safe_start_game_guess_the_player, game, Session)

        # start_game_futures = {game: executor.submit(thread_safe_start_game_guess_the_player, game, Session) for game in valid_games}
        curr_players = {}
        for game, future in start_game_futures.items():
            res, err, curr_player = future.result()
            print("\n==========================\n", game, res, err, curr_player, "\n==========================\n")
            assert res is True
            assert err == ""
            assert isinstance(curr_player, int) is True

            curr_players[game] = curr_player

        cancel_game_futures = [executor.submit(thread_safe_cancel_game_guess_the_player, game, Session) for game in test_input["canceld"]]
        started_round_games_futres = {}
        game_data = test_input["game_data"]
        
        for game, curr_player in curr_players.items():
            sleep(LEAN_SLEEP_TIME)
            curr_hints = game_data[game]["curr_hints"]
            curr_answer = game_data[game]["curr_answer"]

            started_round_games_futres[game] = executor.submit(thread_safe_start_round_guess_the_player, curr_player, curr_hints, curr_answer, Session)

        game_started = []
        valid_games = []
        for game, future in started_round_games_futres.items():
            res, err , _, game_id = future.result()
            print("\n==========================\n", res, err, game_id, "\n==========================\n")

            assert res is True
            assert err == ""
            assert game == game_id
            valid_games.append(game)
            game_started.append(game_id)
        
        assert sorted(game_started) == sorted(valid_games)

        answers_futures = {}
        for game in valid_games:
            answers_futures[game] = {}
            for player in test_input["players"]:
                if player == curr_players[game]:
                    continue

                answers_futures[game][player] = []
                for _ in range(3):
                    sleep(0.1)
                    answers_futures[game][player].append(executor.submit(thread_safe_proccess_answer_guess_the_player, game, player, "wrong", Session))

        for i, (game, player_dict) in enumerate(answers_futures.items()):
            len_players = len(player_dict.keys())
            for j, (player, future_list) in enumerate(player_dict.items()):
                for k, future in enumerate(future_list):
                    res, err= future.result()
                    print("\n==========================\n", "i", i, "j", j, "k", k, game, player, res, err, "\n==========================\n")

                    if j == len_players - 1:
                        if k == 0:
                            assert res is True
                            assert err == "false"
                        elif k == 1:
                            assert res is True
                            assert err == "all players muted"
                        else:
                            assert res is False
                            assert err == "state error"
                    else:
                        if k == 2:
                            assert res is False
                            assert err == "muted player"
                        else:
                            assert res is True
                            assert err == "false"

        ended_round_games_futures = []
        for game in curr_players.keys():
            ended_round_games_futures.append(executor.submit(thread_safe_end_round_guess_the_player, game, Session))

        for future in ended_round_games_futures:
            res, err, next_player = future.result()
            print("\n==========================\n", res, err, next_player, "\n==========================\n")

            assert res is True
            assert err == "round end"
            assert (next_player in test_input["players"]) is True

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
def test_end_game_curr_player_win_same_players(db_session: Session, test_input: dict[str, list[int]], expected: int):
    Session = sessionmaker(bind=db_session.bind)

    print("\n=====================\n", "test_start_round_same_players\n", sep="")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Create games concurrently
        create_game_futures = [executor.submit(create_game_with_retry_guess_the_player, i, 1, Session) for i in test_input["games"]]

        # Ensure all games are created by checking the result of create_game_futures
        for future in concurrent.futures.as_completed(create_game_futures):
            res, err = future.result()  # This will raise an exception if game creation fails
            print("\n==========================\n", res, err, "\n==========================\n")

        # Cancel games concurrently
        cancel_game_futures = [executor.submit(thread_safe_cancel_game_guess_the_player, game, Session) for game in test_input["canceld"]]

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
                    canceld_join_futures.append(executor.submit(thread_safe_join_game_guess_the_player, game, player, Session))
            elif game in test_input["less_that_expected_player"]:
                join_futures.append(executor.submit(thread_safe_join_game_guess_the_player, game, test_input["players"][0], Session))
            else:
                for player in test_input["players"]:
                    join_futures.append(executor.submit(thread_safe_join_game_guess_the_player, game, player, Session))

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
        start_game_futures = {}
        for game in valid_games:
            sleep(2)
            start_game_futures[game] = executor.submit(thread_safe_start_game_guess_the_player, game, Session)
        curr_players = {}
        for game, future in start_game_futures.items():
            res, err, curr_player = future.result()
            print("\n==========================\n", game, res, err, curr_player, "\n==========================\n")
            assert res is True
            assert err == ""
            assert isinstance(curr_player, int) is True

            curr_players[game] = curr_player


        cancel_game_futures = [executor.submit(thread_safe_cancel_game_guess_the_player, game, Session) for game in test_input["canceld"]]
        started_round_games_futres = {}
        game_data = test_input["game_data"]

        num_players = len(test_input["players"])
        for tries in range(num_players):
            for game, curr_player in curr_players.items():
                sleep(LEAN_SLEEP_TIME)
                curr_hints = game_data[game]["curr_hints"]
                curr_answer = game_data[game]["curr_answer"]

                started_round_games_futres[game] = executor.submit(thread_safe_start_round_guess_the_player, curr_player, curr_hints, curr_answer, Session)

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

            answers_futures = {}
            for game in valid_games:
                answers_futures[game] = {}
                for player in test_input["players"]:
                    if player == curr_players[game]:
                        continue

                    answers_futures[game][player] = []
                    for _ in range(3):
                        sleep(LEAN_SLEEP_TIME)
                        answers_futures[game][player].append(executor.submit(thread_safe_proccess_answer_guess_the_player, game, player, "wrong", Session))

            for i, (game, player_dict) in enumerate(answers_futures.items()):
                len_players = len(player_dict.keys())
                for j, (player, future_list) in enumerate(player_dict.items()):
                    for k, future in enumerate(future_list):
                        res, err= future.result()
                        print("\n==========================\n", "i", i, "j", j, "k", k, game, player, res, err, "\n==========================\n")

                        if j == len_players - 1:
                            if k == 0:
                                assert res is True
                                assert err == "false"
                            elif k == 1:
                                assert res is True
                                assert err == "all players muted"
                            else:
                                assert res is False
                                assert err == "state error"
                        else:
                            if k == 2:
                                assert res is False
                                assert err == "muted player"
                            else:
                                assert res is True
                                assert err == "false"

            ended_round_games_futures = {}
            for game in curr_players.keys():
                ended_round_games_futures[game] = executor.submit(thread_safe_end_round_guess_the_player, game, Session)

            for game, future in ended_round_games_futures.items():
                res, err, next_player = future.result()
                print("\n==========================\n", res, err, next_player, "\n==========================\n")

                if tries == num_players - 1:
                    assert res is True
                    assert err == "game end"
                    assert next_player == -1
                else:
                    assert res is True
                    assert err == "round end"
                    assert (next_player in test_input["players"]) is True
                    curr_players[game] = next_player

        scores = {game:{player_id:1 for player_id in test_input["players"]} for game in curr_players.keys()}
        winners = {game: test_input["players"].copy() for game in curr_players.keys()}

        end_games_futures = {}
        for game in curr_players.keys():
            end_games_futures[game] = executor.submit(thread_safe_end_game_guess_the_player, game, Session)

        for game, future in end_games_futures.items():
            res, err, scores_, winners_ = future.result()
            curr_scores = scores[game]
            curr_winners = winners[game]

            assert res is True
            assert err == ""
            assert scores_ == curr_scores
            assert sorted(winners_) == sorted(curr_winners)

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
def test_end_game_other_players_win_same_players(db_session: Session, test_input: dict[str, list[int]], expected: int):
    Session = sessionmaker(bind=db_session.bind)

    print("\n=====================\n", "test_start_round_same_players\n", sep="")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Create games concurrently
        create_game_futures = [executor.submit(create_game_with_retry_guess_the_player, i, 1, Session) for i in test_input["games"]]

        # Ensure all games are created by checking the result of create_game_futures
        for future in concurrent.futures.as_completed(create_game_futures):
            res, err = future.result()  # This will raise an exception if game creation fails
            print("\n==========================\n", res, err, "\n==========================\n")

        # Cancel games concurrently
        cancel_game_futures = [executor.submit(thread_safe_cancel_game_guess_the_player, game, Session) for game in test_input["canceld"]]

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
                    canceld_join_futures.append(executor.submit(thread_safe_join_game_guess_the_player, game, player, Session))
            elif game in test_input["less_that_expected_player"]:
                join_futures.append(executor.submit(thread_safe_join_game_guess_the_player, game, test_input["players"][0], Session))
            else:
                for player in test_input["players"]:
                    join_futures.append(executor.submit(thread_safe_join_game_guess_the_player, game, player, Session))

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
        start_game_futures = {}
        for game in valid_games:
            sleep(2)
            start_game_futures[game] = executor.submit(thread_safe_start_game_guess_the_player, game, Session)
        curr_players = {}
        for game, future in start_game_futures.items():
            res, err, curr_player = future.result()
            print("\n==========================\n", game, res, err, curr_player, "\n==========================\n")
            assert res is True
            assert err == ""
            assert isinstance(curr_player, int) is True

            curr_players[game] = curr_player


        cancel_game_futures = [executor.submit(thread_safe_cancel_game_guess_the_player, game, Session) for game in test_input["canceld"]]
        started_round_games_futres = {}
        game_data = test_input["game_data"]

        num_players = len(test_input["players"])
        games_winners = {game:[] for game in valid_games}
        for tries in range(num_players):
            for game, curr_player in curr_players.items():
                sleep(LEAN_SLEEP_TIME)
                curr_hints = game_data[game]["curr_hints"]
                curr_answer = game_data[game]["curr_answer"]
                print("\n==========================\n", game, curr_answer, "\n==========================\n")
                started_round_games_futres[game] = executor.submit(thread_safe_start_round_guess_the_player, curr_player, curr_hints, curr_answer, Session)

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

            answers_dict = {}
            with Session() as s:
                result = s.query(GuessThePlayer.chat_id, GuessThePlayer.curr_answer).all()
            
                for chat_id, curr_answer in result:
                    answers_dict[chat_id] = curr_answer

            answers_futures = {}
            winning_players = {}
            for game in valid_games:
                winning_player = [player for player in test_input["players"] if player != curr_players[game]][randint(0, num_players - 2)]
                winning_players[game] = winning_player
                games_winners[game].append(winning_player)
                answers_futures[game] = {}
                for player in test_input["players"]:
                    if player == curr_players[game]:
                        continue

                    answers_futures[game][player] = []
                    if player == winning_player:
                        for _ in range(2):
                            sleep(LEAN_SLEEP_TIME)
                            answers_futures[game][player].append(executor.submit(thread_safe_proccess_answer_guess_the_player, game, player, answers_dict[game].strip().lower(), Session))
                    else:
                        for _ in range(2):
                            sleep(LEAN_SLEEP_TIME)
                            answers_futures[game][player].append(executor.submit(thread_safe_proccess_answer_guess_the_player, game, player, "wrong", Session))

            for i, (game, player_dict) in enumerate(answers_futures.items()):
                for j, (player, future_list) in enumerate(player_dict.items()):
                    for k, future in enumerate(future_list):
                        res, err= future.result()
                        print("\n==========================\n", "i", i, "j", j, "k", k, game, player, res, err, "\n==========================\n")

                        if player == winning_players[game]:
                            if k == 0:
                                assert res is True
                                assert err == "correct"
                            else:
                                assert res is False
                                assert err == "state error"
                        else:
                            if err == "state error":
                                assert res is False
                            elif err == "false":
                                assert res is True
                            elif err == "muted player":
                                assert res is False
                            else:
                                assert True is False

            ended_round_games_futures = {}
            for game in curr_players.keys():
                ended_round_games_futures[game] = executor.submit(thread_safe_end_round_guess_the_player, game, Session)

            for game, future in ended_round_games_futures.items():
                res, err, next_player = future.result()
                print("\n==========================\n", res, err, next_player, "\n==========================\n")

                if tries == num_players - 1:
                    assert res is True
                    assert err == "game end"
                    assert next_player == -1
                else:
                    assert res is True
                    assert err == "round end"
                    assert (next_player in test_input["players"]) is True
                    curr_players[game] = next_player

        scores = {game:{player_id:games_winners[game].count(player_id) for player_id in test_input["players"]} for game in curr_players.keys()}
        winners = {
            game: [
                player_id for player_id, score in player_scores.items() 
                if score == max(player_scores.values())
            ]
            for game, player_scores in scores.items()
        }

        end_games_futures = {}
        for game in curr_players.keys():
            end_games_futures[game] = executor.submit(thread_safe_end_game_guess_the_player, game, Session)

        for game, future in end_games_futures.items():
            res, err, scores_, winners_ = future.result()
            curr_scores = scores[game]
            curr_winners = winners[game]

            assert res is True
            assert err == ""
            assert scores_ == curr_scores
            assert sorted(winners_) == sorted(curr_winners)

        print("=====================\n")

