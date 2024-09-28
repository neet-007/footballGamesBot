from datetime import datetime, timedelta
from sqlalchemy import exists
from sqlalchemy.orm import Session

from db.models import RateLimits

def check_user_message_freq(player_id:int, limit:int, time_window:int=60):
    pass

def check_rate_limit(player_id:int, session:Session):
    try:
        with session.begin():
            if session.query(exists().where(RateLimits.player_id == player_id)).scalar():
                return False, "rate limited"
            
            return True, ""
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "expection"

def clear_rate_limits(session:Session):
    try:
        with session.begin():
            session.query(RateLimits).filter(RateLimits.time_created <=  datetime.now() - timedelta(minutes=1)).delete()

            return True, "" 
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "expection"
