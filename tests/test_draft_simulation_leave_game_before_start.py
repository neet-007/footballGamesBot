import concurrent.futures
from random import randint
from uuid import uuid4
import pytest
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import create_game_with_retry, thread_safe_add_pos_to_team, thread_safe_add_vote, thread_safe_cancel_game, thread_safe_end_game, thread_safe_end_round, thread_safe_get_vote_results, thread_safe_join_game, thread_safe_leave_game, thread_safe_make_vote, thread_safe_rand_team, thread_safe_set_game_state, thread_safe_start_game, thread_safe_transfers

POSITIONS = 11
LEAST_NUM_PLAYERS = 2

@pytest.mark.parametrize("test_input, expected", [
    ({
        "games": [11, 22, 33, 44, 55, 66, 77, 88, 99],
        "players": [111, 222, 333, 444, 555],
        "canceld": [22, 44],
        "games_player_leaving":{11:2, 55:4},
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
def test_leave_game_before_start_same_players(db_session: Session, test_input: dict[str, dict[int, dict[str, str]]], expected: int):
    Session = sessionmaker(bind=db_session.bind)
    print("\n=====================\n", "test_start_round_same_players\n", sep="")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        create_game_futures = {executor.submit(create_game_with_retry, game, Session):game for game in test_input["games"]}

        for future in concurrent.futures.as_completed(create_game_futures.keys()):
            game = create_game_futures[future]
            res, err = future.result()  

            print("\n==========================\n", game, res, err, "\n==========================\n")
            assert res is True
            assert err is ""


        cancel_game_futures = {executor.submit(thread_safe_cancel_game, game, Session):game for game in test_input["canceld"]}

        for future in concurrent.futures.as_completed(cancel_game_futures.keys()):
           game = cancel_game_futures[future]
           res, err = future.result()  

           print("\n==========================\n", game, res, err, "\n==========================\n")
           assert res is True
           assert err == ""

        join_futures = {}
        canceld_join_futures = {}
        joiners = 0
        for game in test_input["games"]:
            join_futures[game] = []
            canceld_join_futures[game] = []
            if game in test_input["canceld"]:
                for player in test_input["players"]:
                    canceld_join_futures[game].append(executor.submit(thread_safe_join_game, game, player, Session))
            elif game in test_input["less_that_expected_player"]:
                continue
            else:
                for player in test_input["players"]:
                    joiners += 1
                    join_futures[game].append(executor.submit(thread_safe_join_game, game, player, Session))

        for game, future_list in join_futures.items():
            for i, future in enumerate(concurrent.futures.as_completed(future_list)):
                res, err = future.result()
                print("\n==========================\n", i, "game: ", game, "res: ", res, "err: ", err, "\n==========================\n")
                assert res is True
                assert err == ""

        for game, future_list in canceld_join_futures.items():
            for i, future in enumerate(concurrent.futures.as_completed(future_list)):
                res, err = future.result()
                print("\n==========================\n", "game: ", game, "res: ", res, "err: ", err, "\n==========================\n")
                assert res is False
                assert err == "no game"

        game_data = test_input["game_data"]
        num_players = len(test_input["players"])

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
        games_canceld_with_leaving = [game for game in valid_games if randint(0, 2) == 2]
        
        games_leaving_futures = {}
        valid_players_after_leaving = [player_id for i, player_id in enumerate(test_input["players"]) if i <= LEAST_NUM_PLAYERS]
        for game in valid_games:
            game_data[game]["teams"] = game_data[game]["teams"][0:11 + len(valid_players_after_leaving)]

        for game in valid_games:
            if game in games_canceld_with_leaving:
                games_leaving_futures[game] = [executor.submit(thread_safe_leave_game, game, player_id, Session) for player_id in test_input["players"]]
            else:
                games_leaving_futures[game] = [executor.submit(thread_safe_leave_game, game, player_id, Session) for player_id in test_input["players"] if player_id not in valid_players_after_leaving]

        for game, future_list in games_leaving_futures.items():
            for future in concurrent.futures.as_completed(future_list):
                res, err, formation_name, curr_pos, team_name, next_player_id, non_picked_teams, _ = future.result()

                assert res is True
                assert err == ""
                assert formation_name == ""
                assert curr_pos == ""
                assert team_name == ""
                assert next_player_id == 0
                assert non_picked_teams == []
                print("\n==========================\n", game, res, err, formation_name, curr_pos, team_name, next_player_id, non_picked_teams, "\n==========================\n")

        start_game_futures = {executor.submit(thread_safe_start_game, game, Session):game  for game in valid_games}

        for future in concurrent.futures.as_completed(start_game_futures.keys()):
            game = start_game_futures[future]
            res, err, num_players_ = future.result()  
            print("\n==========================\n", game, res, err, num_players, "\n==========================\n")

            if game in games_canceld_with_leaving:
                assert res is False
                assert err == "no players associated with the game"
                valid_games.remove(game)
            else:
                assert res is True
                assert err == ""
                assert num_players_ == len(valid_players_after_leaving)

        state_set_games_futres = {}

        for game in valid_games:
            category = game_data[game]["category"]
            formation = game_data[game]["formation"]
            teams= game_data[game]["teams"]

            state_set_games_futres[executor.submit(thread_safe_set_game_state ,game, valid_players_after_leaving[0], category, teams, formation, Session)] = game

        curr_players = {}
        picking_players = {}
        for future in concurrent.futures.as_completed(state_set_games_futres.keys()):
            game = state_set_games_futres[future]
            res, err, num_players_, category_, formation_, teams_, curr_player_id_ = future.result()
            print("\n==========================\n", res, err, num_players_, category_, formation_, teams_, curr_player_id_, "\n==========================\n")

            category = game_data[game]["category"]
            formation = game_data[game]["formation"]
            teams= game_data[game]["teams"]

            assert res is True
            assert err == ""
            assert num_players_ == len(valid_players_after_leaving)
            assert category_ == category
            assert formation_ == formation
            assert teams_ == "\n".join([team.lower() for team in teams])
            assert (curr_player_id_ in test_input["players"]) is True
            picking_players[game] = curr_player_id_
            curr_players[game] = curr_player_id_

        players_teams = {}
        for game in valid_games:
            new_list = []
            for player_id in valid_players_after_leaving:
                new_list.append(tuple([player_id, {f"p{x}":"" for x in range(1, 12)}]))

            players_teams[game] = new_list

        for pos in range(POSITIONS):
            rand_teams_futures = {}
            for game, curr_player in picking_players.items():
                rand_teams_futures[executor.submit(thread_safe_rand_team, game, curr_player, Session)] = game 

            for future in concurrent.futures.as_completed(rand_teams_futures.keys()):
                game = rand_teams_futures[future]
                res, err, team_name, formation_name, curr_pos, non_picked_teams = future.result()
                
                print("\n==========================\n", game, res, err, team_name, formation_name, curr_pos, "\n==========================\n")

                teams= game_data[game]["teams"]
                formation = game_data[game]["formation"]
                assert res is True
                assert err == ""
                assert (team_name in teams) is True
                assert formation_name == formation
                assert curr_pos == f"p{pos + 1}"
                assert sorted([team.lower() for team in non_picked_teams]) == sorted([team.lower() for team in teams if team.lower() != team_name.lower()])

                game_data[game]["teams"].remove(team_name)

            added_pos_futures = {}
            for i in range(len(valid_players_after_leaving)):
                for game, curr_player in curr_players.items():
                    added_player = f"{game}{curr_player}p{pos + 1}"
                    for item in players_teams[game]:
                        if item[0] == curr_player:
                            item[1][f"p{pos + 1}"] = added_player

                    added_pos_futures[ game] = executor.submit(thread_safe_add_pos_to_team, game, curr_player, added_player, Session)

                for future in concurrent.futures.as_completed(added_pos_futures.values()):
                    game = next(game for game, fut in added_pos_futures.items() if fut == future)
                    res, err, curr_player_id, curr_pos_, formation_  = future.result()

                    print("\n==========================\n", "i: ", i, "num_players: ", num_players - 1,  game, res, err, curr_player_id, curr_pos_, formation_, "\n==========================\n")

                    if i == len(valid_players_after_leaving) - 1:
                        formation = game_data[game]["formation"]
                        assert res is True
                        assert err == "end round"
                        assert curr_player_id is None
                        assert formation_ is None
                        assert curr_pos_ is None
                        curr_players[game] = curr_player_id
                    else:
                        formation = game_data[game]["formation"]
                        assert res is True
                        assert err == "same_pos"
                        assert (curr_player_id in valid_players_after_leaving) is True
                        assert formation_ == formation
                        assert curr_pos_ == f"p{pos + 1}"
                    curr_players[game] = curr_player_id

            games_with_round_ended = {}
            for game in valid_games:
                games_with_round_ended[executor.submit(thread_safe_end_round, game, Session)] = game

            for future in concurrent.futures.as_completed(games_with_round_ended.keys()):
                game = games_with_round_ended[future]
                res, err, curr_player_id, formation_, teams = future.result()

                print("\n==========================\n", game, res, err, curr_player_id, formation_, "\n==========================\n")

                if pos == 10:
                    formation = game_data[game]["formation"]
                    assert res is True
                    assert err == "transfer_start"
                    assert (curr_player_id in valid_players_after_leaving) is True
                    assert formation_ == formation
                    assert (sorted(teams, key=lambda x: x[0]) == sorted(players_teams[game], key=lambda x: x[0]))
                else:
                    formation = game_data[game]["formation"]
                    assert res is True
                    assert err == "new_pos"
                    assert (curr_player_id in valid_players_after_leaving) is True
                    assert formation_ == formation
                curr_players[game] = curr_player_id
                picking_players[game] = curr_player_id

        for i in range(len(valid_players_after_leaving)):
            transfers_futures = {}
            added_pos_futures = {}
            games_with_round_ended = {}
            game_pos = {}
            for game, current_player in curr_players.items():
                rand_pos = f"p{randint(1, 11)}"
                game_pos[game] = rand_pos
                transfers_futures[executor.submit(thread_safe_transfers, game, current_player, rand_pos, Session)] = game
                added_player = f"{game}{current_player}{rand_pos}"
        
            # add check for skipping
            for future in concurrent.futures.as_completed(transfers_futures.keys()):
                game = transfers_futures[future]
                res, err, team_name, formation_name, curr_pos, curr_player_id, teams, non_picked_teams = future.result()

                print("\n==========================\n", game, res, err, team_name, formation_name, curr_pos, curr_player_id, teams, non_picked_teams, "\n==========================\n")

                teams= game_data[game]["teams"]
                formation = game_data[game]["formation"]
                assert res is True
                assert err == ""
                assert curr_pos == game_pos[game]
                assert (team_name in teams) is True
                assert formation_name == formation
                assert sorted([team.lower() for team in non_picked_teams]) == sorted([team.lower() for team in teams if team.lower() != team_name.lower()])

                game_data[game]["teams"].remove(team_name)

            for game, curr_player in curr_players.items():
                added_player = f"{game}{curr_player}transfer"
                for item in players_teams[game]:
                    if item[0] == curr_player:
                        item[1][game_pos[game]] = added_player
                added_pos_futures[executor.submit(thread_safe_add_pos_to_team, game, curr_player, added_player, Session)] = game

            for future in concurrent.futures.as_completed(added_pos_futures.keys()):
                game = added_pos_futures[future]
                res, err, curr_player_id, curr_pos_, formation_  = future.result()

                print("\n==========================\n", game, res, err, curr_player_id, curr_pos_, formation_, "\n==========================\n")

                formation = game_data[game]["formation"]
                assert res is True
                assert err == "end round"
                assert curr_player_id is None
                assert formation_ is None
                assert curr_pos_ is None

            games_with_round_ended = {executor.submit(thread_safe_end_round, game, Session):game for game in valid_games}

            for future in concurrent.futures.as_completed(games_with_round_ended.keys()):
                game = games_with_round_ended[future]
                res, err, curr_player_id, formation_, teams = future.result()

                print("\n==========================\n", game, res, err, curr_player_id, formation_, "\n==========================\n")

                if i == len(valid_players_after_leaving) - 1:
                    formation = game_data[game]["formation"]
                    assert res is True
                    assert err == "end_game"
                    assert (curr_player_id in valid_players_after_leaving) is True
                    assert formation_ == formation
                else:
                    formation = game_data[game]["formation"]
                    assert res is True
                    assert err == "new_transfer"
                    assert (curr_player_id in valid_players_after_leaving) is True
                    assert formation_ == formation
                    curr_players[game] = curr_player_id
                    picking_players[game] = curr_player_id

        games_votes = {}
        games_votes_futures = {}
        players_options = {}
        games_polls = {}
        game_vote_count = {}
        for game in valid_games:
            players_vote_list = [[], []]
            for option, id in enumerate(valid_players_after_leaving):
                players_vote_list[0].append([id])
                players_vote_list[1].append(f"player_{game}_{id}")

                players_options[option] = id

            message_id = uuid4()
            poll_id = uuid4()

            games_votes[game] = {
                "options": players_vote_list[1],
                "message_id": message_id.hex,
                "poll_id": poll_id.hex
            }

            game_vote_count[game] = {player_id:0 for player_id in valid_players_after_leaving} 
            games_polls[game] = poll_id.hex
            games_votes_futures[executor.submit(thread_safe_make_vote, game, players_vote_list[0], message_id.hex, poll_id.hex, Session)] = game

        for future in concurrent.futures.as_completed(games_votes_futures.keys()):
            game = games_votes_futures[future]
            res, err = future.result()
            
            print("\n==========================\n", game, res, err, "\n==========================\n")

            assert res is True
            assert err == ""
                
        games_add_votes_futures = {}
        for game, poll_id in games_polls.items():
            games_add_votes_futures[game] = []
            for player_id in valid_players_after_leaving:
                # should change and be per game
                rand_option = randint(0, len(valid_players_after_leaving) - 1)
                game_vote_count[game][players_options[rand_option]] += 1
                games_add_votes_futures[game].append(executor.submit(thread_safe_add_vote, poll_id, rand_option, Session))

        games_players_voting_count = {}
        for i, (game, future_list) in enumerate(games_add_votes_futures.items()):
            games_players_voting_count[game] = 0
            for future in concurrent.futures.as_completed(future_list):
                res, err, game_id = future.result()

                print("\n==========================\n", game, res, err, game_id, "\n==========================\n")

                games_players_voting_count[game] += 1
                if err == "end vote":
                    assert res is True
                    assert game_id == game
                else:
                    assert res is True
                    assert err == "continue"
                    assert game_id == game

            assert games_players_voting_count[game] == len(valid_players_after_leaving)

        games_vote_end = {executor.submit(thread_safe_get_vote_results, game, Session):game for game in valid_games}

        for future in concurrent.futures.as_completed(games_vote_end.keys()):
            game = games_vote_end[future]
            res, err, message_id, votes = future.result()

            print("\n==========================\n", game, res, err, message_id, votes, "\n==========================\n")

            assert res is True
            assert err == ""
            assert games_votes[game]["message_id"] == message_id
            assert votes == game_vote_count[game]

        end_games_futures = {executor.submit(thread_safe_end_game, game, Session):game for game in valid_games}

        for future in concurrent.futures.as_completed(end_games_futures.keys()):
            game = end_games_futures[future]
            res, err, teams, formation = future.result()
            print("\n==========================\n", game, res, err, formation, "\n==========================\n")

            formation_name = game_data[game]["formation"]
            assert res is True
            assert err == ""
            assert formation == formation_name
            assert teams is not None
            assert (sorted(teams, key=lambda x: x[0]) == sorted(players_teams[game], key=lambda x: x[0]))

        print("=====================\n")






