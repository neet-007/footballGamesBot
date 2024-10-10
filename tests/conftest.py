import pytest
from os import getenv

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base

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
        drop_db()
