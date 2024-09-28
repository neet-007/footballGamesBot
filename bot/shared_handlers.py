from os import getenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, BaseHandler
from db.connection import get_session
from db.shared_queries import check_rate_limit
import traceback
from json import dumps
from html import escape

def check_rate_limit_function(player_id):
        with get_session() as session:
            res, err = check_rate_limit(player_id, session)
            if not res:
               print(err)
               return False

        return True

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    DEVELOPER_CHAT_ID = getenv("DEVELOPER_CHAT_ID")
    if not DEVELOPER_CHAT_ID:
        return

    tb_list = traceback .format_exception(None, context.error, context.error.__traceback__) # type: ignore
    tb_string = "".join(tb_list)

    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        "An exception was raised while handling an update\n"
        f"<pre>update = {escape(dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{escape(tb_string)}</pre>"
    )

    await context.bot.send_message(
        chat_id=DEVELOPER_CHAT_ID, text=message, parse_mode=ParseMode.HTML
    )

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

