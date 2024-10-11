import concurrent.futures
from random import randint
from time import sleep
from uuid import uuid4
import pytest
from sqlalchemy.orm import Session, sessionmaker
from games.draft_functions import add_pos_to_team_draft, add_vote, cancel_game_draft, end_game_draft, end_round_draft, get_vote_data, get_vote_results, join_game_draft, make_vote, new_game_draft, rand_team_draft, set_game_states_draft, start_game_draft, transfers

POSITIONS = 11

def thread_safe_new_game(game_id, Session):
    session = Session()
    try:
        return new_game_draft(game_id, session)
    finally:
        session.close()

def create_game_with_retry(game, Session, max_retries=3):
    for attempt in range(max_retries):
        res, err = thread_safe_new_game(game, Session)
        if err != "exception":
            return res, err

        sleep(0.1 * (attempt + 1))  
    return False, "Max retries reached"

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

def thread_safe_end_round(game_id, Session):
    session = Session()
    try:
        return end_round_draft(game_id, session)
    finally:
        session.close()

def thread_safe_transfers(game_id, player_id, position, Session):
    session = Session()
    try:
        return transfers(game_id, player_id, position, session)
    finally:
        session.close()

def thread_safe_get_vote_data(game_id, Session):
    session = Session()
    try:
        return get_vote_data(game_id, session)
    finally:
        session.close()

def thread_safe_make_vote(game_id, players, message_id, poll_id, Session):
    session = Session()
    try:
        return make_vote(game_id, players, message_id, poll_id, session)
    finally:
        session.close()

def thread_safe_add_vote(poll_id, option_id, Session):
    session = Session()
    try:
        return add_vote(poll_id, option_id, session)
    finally:
        session.close()

def thread_safe_get_vote_results(game_id, Session):
    session = Session()
    try:
        return get_vote_results(game_id, session)
    finally:
        session.close()

def thread_safe_end_game(game_id, Session):
    session = Session()
    try:
        return end_game_draft(game_id, session)
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
def test_end_game_same_players(db_session: Session, test_input: dict[str, dict[int, dict[str, str]]], expected: int):
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
        
        start_game_futures = {executor.submit(thread_safe_start_game, game, Session):game  for game in valid_games}

        for future in concurrent.futures.as_completed(start_game_futures.keys()):
            game = start_game_futures[future]
            res, err, num_players_ = future.result()  
            print("\n==========================\n", game, res, err, num_players, "\n==========================\n")

            assert res is True
            assert err == ""
            assert num_players_ == num_players

        state_set_games_futres = {}

        for game in valid_games:
            category = game_data[game]["category"]
            formation = game_data[game]["formation"]
            teams= game_data[game]["teams"]

            state_set_games_futres[executor.submit(thread_safe_set_game_state ,game, test_input["players"][0], category, teams, formation, Session)] = game

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
            assert num_players_ == num_players
            assert category_ == category
            assert formation_ == formation
            assert teams_ == "\n".join([team.lower() for team in teams])
            assert (curr_player_id_ in test_input["players"]) is True
            picking_players[game] = curr_player_id_
            curr_players[game] = curr_player_id_

        players_teams = {}
        for game in valid_games:
            new_list = []
            for player_id in test_input["players"]:
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

                teams = game_data[game]["teams"]
                formation = game_data[game]["formation"]
                assert res is True
                assert err == ""
                assert (team_name in teams) is True
                assert formation_name == formation
                assert curr_pos == f"p{pos + 1}"
                assert sorted([team.lower() for team in non_picked_teams]) == sorted([team.lower() for team in teams if team.lower() != team_name.lower()])

                game_data[game]["teams"].remove(team_name)

            added_pos_futures = {}
            for i in range(num_players):
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

                    if i == num_players - 1:
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
                        assert (curr_player_id in test_input["players"]) is True
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
                    assert (curr_player_id in test_input["players"]) is True
                    assert formation_ == formation
                    assert (sorted(teams, key=lambda x: x[0]) == sorted(players_teams[game], key=lambda x: x[0]))
                else:
                    formation = game_data[game]["formation"]
                    assert res is True
                    assert err == "new_pos"
                    assert (curr_player_id in test_input["players"]) is True
                    assert formation_ == formation
                curr_players[game] = curr_player_id
                picking_players[game] = curr_player_id

        for i in range(num_players):
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

                teams = game_data[game]["teams"]
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

                if i == num_players - 1:
                    formation = game_data[game]["formation"]
                    assert res is True
                    assert err == "end_game"
                    assert (curr_player_id in test_input["players"]) is True
                    assert formation_ == formation
                else:
                    formation = game_data[game]["formation"]
                    assert res is True
                    assert err == "new_transfer"
                    assert (curr_player_id in test_input["players"]) is True
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
            for option, id in enumerate(test_input["players"]):
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

            game_vote_count[game] = {player_id:0 for player_id in test_input["players"]} 
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
            for player_id in test_input["players"]:
                # should change and be per game
                rand_option = randint(0, num_players - 1)
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

            assert games_players_voting_count[game] == num_players

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






