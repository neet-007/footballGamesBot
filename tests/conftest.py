from time import sleep
import pytest
from os import getenv

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base
from games.draft_functions import add_pos_to_team_draft, add_vote, cancel_game_draft, end_game_draft, end_round_draft, get_vote_data, get_vote_results, join_game_draft, leave_game_draft, make_vote, new_game_draft, rand_team_draft, set_game_states_draft, start_game_draft, transfers

LEAN_SLEEP_TIME = 0.2
HARSH_SLEEP_TIME = 0.1

TURSO_DATABASE_URL = getenv("TURSO_DATABASE_URL", "sqlite+libsql://127.0.0.1:8080") 
print("db url: ", TURSO_DATABASE_URL)

engine = create_engine(TURSO_DATABASE_URL, connect_args={'check_same_thread': False}, echo=False)

def new_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

def drop_db():
    Base.metadata.drop_all(engine)

def get_session() -> Session:
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()

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

def thread_safe_leave_game(game_id, player_id, Session):
    session = Session()
    try:
        return leave_game_draft(game_id, player_id, session)
    finally:
        session.close()



@pytest.fixture(scope="function")
def db_session():
    new_db()
    session = get_session()   
    try:
        yield session  
    finally:
        if session.is_active:
            print("\n===================================\n", "session is active", "\n===================================\n")
            session.rollback()
        else:
            print("\n===================================\n", "session is active", "\n===================================\n")

        session.close()
       # drop_db()
