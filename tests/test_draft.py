import pytest
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import func  
from db.models import Draft, Game
from games.draft_functions import cancel_game_draft, join_game_draft, new_game_draft, start_game_draft
from .conftest import new_db, drop_db

@pytest.mark.parametrize("test_input, expected", [
    ([11, 22, 33], 3),
])
def test_new_db(test_input, expected):
    new_db()

@pytest.mark.parametrize("test_input, expected", [
    ([11, 22, 33], 3),
])
def test_create_different_games(db_session: Session, test_input: list[int], expected: int):
    new_db()
    print("\n=====================\n", "test_create_different_games\n", sep="")
    Session = sessionmaker(bind=db_session.bind)
    for i in test_input:
        print(f"making game num: {i}")
        new_game_draft(i, Session())

    actual_draft_count = db_session.query(func.count(Draft.chat_id)).scalar() 
    actual_game_count = db_session.query(func.count(Game.chat_id)).scalar() 

    print(f"actual guess the player count vs expected : {actual_draft_count} vs {expected}")
    print(f"actual game count vs expected : {actual_game_count} vs {expected}")

    assert actual_draft_count == expected
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
        new_game_draft(i, Session())

    actual_draft_count = db_session.query(func.count(Draft.chat_id)).scalar() 
    actual_game_count = db_session.query(func.count(Game.chat_id)).scalar() 

    print(f"actual guess the player count vs expected : {actual_draft_count} vs {expected}")
    print(f"actual game count vs expected : {actual_game_count} vs {expected}")

    assert actual_draft_count == expected
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
        new_game_draft(i, Session())

    for game in test_input[::-1][:len(test_input) // 2]:
        cancel_game_draft(game, Session())

    actual_draft_count = db_session.query(func.count(Draft.chat_id)).scalar() 
    actual_game_count = db_session.query(func.count(Game.chat_id)).scalar() 

    print(f"actual guess the player count vs expected : {actual_draft_count} vs {expected}")
    print(f"actual game count vs expected : {actual_game_count} vs {expected}")

    assert actual_draft_count == expected
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
        new_game_draft(i, Session())

    canceld_games = [id for i, id in enumerate(test_input) if i % 2 == 0]

    for game in canceld_games:
        cancel_game_draft(game, Session())

    for i, game in enumerate(canceld_games):
        res, err = join_game_draft(game, i, Session())
        assert res is False
        assert err == "no game"

    actual_draft_count = db_session.query(func.count(Draft.chat_id)).scalar() 
    actual_game_count = db_session.query(func.count(Game.chat_id)).scalar() 

    print(f"actual guess the player count vs expected : {actual_draft_count} vs {expected}")
    print(f"actual game count vs expected : {actual_game_count} vs {expected}")

    assert actual_draft_count== expected
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
        new_game_draft(i, Session())

    canceld_games = test_input["canceld"]
    less_that_expected_player = test_input["less_that_expected_player"]

    for game in canceld_games:
        cancel_game_draft(game, Session())

    for game in test_input["games"]:
        if game in less_that_expected_player:
            res, err = join_game_draft(game, test_input["players"][0], Session())
            assert res is True
            assert err == ""
        else:   
            for player in test_input["players"]:
                res, err = join_game_draft(game, player, Session())
                if game in canceld_games:
                    assert res is False
                    assert err == "no game"
                else:
                    assert res is True
                    assert err == ""
                
    for game in test_input["games"]:
        res, err, _ = start_game_draft(game, Session())
        if game in canceld_games:
            assert res is False
            assert err == "no game"
        elif game in less_that_expected_player:
            assert res is False
            assert err == "number of players is less than 2 or not as expected"
        else:
            assert res is True
            assert err == ""

    actual_draft_count = db_session.query(func.count(Draft.chat_id)).scalar() 
    actual_game_count = db_session.query(func.count(Game.chat_id)).scalar() 

    print(f"actual guess the player count vs expected : {actual_draft_count} vs {expected}")
    print(f"actual game count vs expected : {actual_game_count} vs {expected}")

    assert actual_draft_count == expected
    assert actual_game_count == expected
    drop_db()
    print("=====================\n")
