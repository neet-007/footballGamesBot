from telegram import Update
from telegram.ext import ContextTypes, BaseHandler
from db.connection import get_session
from db.shared_queries import check_rate_limit

def check_rate_limit_function(player_id):
        with get_session() as session:
            res, err = check_rate_limit(player_id, session)
            if not res:
               print(err)
               return False

        return True

async def chack_rate_limit_handler(update: Update, context:ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_chat:
        return
        
    await context.bot.send_message(chat_id=update.effective_chat.id, text="you are rate limited")

class RateLimitHandler(BaseHandler):
    def __init__(self, callback):
        super().__init__(callback)

    def check_update(self, update: object) -> bool:
        if isinstance(update, Update) and update.effective_user:
            return not check_rate_limit_function(update.effective_user.id)   

        return False

