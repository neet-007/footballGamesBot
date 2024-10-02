from os import getenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, BaseHandler
from db.connection import get_session
from db.shared_queries import check_rate_limit
import traceback
from json import dumps
from html import escape

from games.draft_handlers import DRAFT_ADD_POS_COMMAND, DRAFT_CANCEL_GAME_COMMAND, DRAFT_END_VOTE_COMMAND, DRAFT_JOIN_COMMAND, DRAFT_NEW_COMMAND, DRAFT_SET_STATE_COMMAND, DRAFT_START_COMMAND, DRAFT_START_VOTE_COMMAND
from games.guess_the_player_handlers import GUESS_THE_PLAYER_ANSWER, GUESS_THE_PLAYER_ANSWER_Q, GUESS_THE_PLAYER_ASK_Q, GUESS_THE_PLAYER_CANCEL_GAME, GUESS_THE_PLAYER_GET_QUESTIONS, GUESS_THE_PLAYER_JOIN, GUESS_THE_PLAYER_LEAVE_GAME, GUESS_THE_PLAYER_NEW, GUESS_THE_PLAYER_START 

async def handle_start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    await update.message.reply_text(f"""
<strong>**Welcome to Football Games Bot** ⚽️</strong>

<b>Essential commands:</b>
- /start to start the bot
- /help to see available games and there ruies

<b>to report any bugs or to give me any suggestion join this group and send them</b>
<strong>support the bot by giving it a start on github <a>https://github.com/neet-007/footballGamesBot</a> its free </strong>

<b>draft commands 📝</b>
- /{DRAFT_NEW_COMMAND} start a draft game
- /{DRAFT_JOIN_COMMAND} to join a draft game
- /{DRAFT_START_COMMAND} to start the draft game
- /{DRAFT_SET_STATE_COMMAND} to set the draft game states category, formation and teams
- /{DRAFT_ADD_POS_COMMAND} to add a player to the position
- /{DRAFT_START_VOTE_COMMAND} to get the voting for teams
- /{DRAFT_END_VOTE_COMMAND} to end the current vote
- /{DRAFT_END_VOTE_COMMAND} to leave draft game
- /{DRAFT_CANCEL_GAME_COMMAND} to cancel the draft game

<b>guess the player commands 🤔</b>
- /{GUESS_THE_PLAYER_NEW} to start a guess the player game
- /{GUESS_THE_PLAYER_JOIN} to join a guess the player game
- /{GUESS_THE_PLAYER_START} to start a guess the player game
- /{GUESS_THE_PLAYER_ASK_Q} to ask a questino in guess the player game
- /{GUESS_THE_PLAYER_ANSWER_Q} to answer a questino asked in guess the player game
- /{GUESS_THE_PLAYER_ANSWER} to give your answer to the player
- /{GUESS_THE_PLAYER_GET_QUESTIONS} to get the asked question in guess the player game
- /{GUESS_THE_PLAYER_LEAVE_GAME} to leave guess the player game
- /{GUESS_THE_PLAYER_CANCEL_GAME} to cancel guess the player game

""", parse_mode=ParseMode.HTML)

async def handle_help(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    await update.message.reply_text(f"""
<strong>**Welcome to Football Games Bot** ⚽️</strong>

The games are inspired by SDS Podcast.

<strong>**Available Games:**</strong>

<b>**Draft** 📝</b>
<b>**Guess the Player** 🤔</b>

<b>**How to Play Guess the Player:**</b>

- Start a new game with `/{GUESS_THE_PLAYER_NEW}[num rounds]`. The game has 2 rounds by default. You can have any number of rounds by adding it after the start command.

- After the round starts, the current player should send the hints and answer to the bot like this: `answer, hint1-hint2-hint3`.

- Every player has 2 tries and 3 questions for each player guess.

- If no one gets the answer right, the current player gets the point.

- To answer the question, prefix the answer with `the answer is [answer]`.

- To ask a question, use the command `/{GUESS_THE_PLAYER_ASK_Q}`. The current player must reply to the question message with their answer.

- There can be only one asked question at a time.

<b>**How to Play Draft:**</b>

- Start a new game with `/{DRAFT_NEW_COMMAND}`.

- After the game starts, you must decide the category, formation, and teams for the round.

- After deciding, set the round using `/{DRAFT_SET_STATE_COMMAND} [category], [team1-team2-team3...], formation`.

- The teams must be 11 + num players and with no duplicates.

- The supported formations are 433, 4231, 442, 532, 352.

- Each player will get a chance to pick a random team then pick the first player from it.

- Every player gets one pick from each team.

- No duplicates are allowed.

- At the end of the round, each player will get a free transfer from one of the teams that didn't get picked, but only the player will get to pick from it.

- At the end of the round, the teams will be displayed, and you must decide the best team to vote for.
    """, parse_mode=ParseMode.HTML)

"""
async def message_dispatcher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.effective_user or not update.message or not update.message.text:
        return

    if update.effective_chat.type == "private":
        return await handle_guess_the_player_start_round(update, context)

    message_text = update.message.text.strip().lower()
    if update.message.reply_to_message:
        return await handle_guess_the_player_answer_question(update, context)
    if message_text.startswith("answer is"):
        return await handle_guess_the_player_proccess_answer_command(update, context)
    if message_text.startswith("player"):
        return await handle_draft_add_pos(update, context)
    else:
        await update.message.reply_text("if you are in guess the player game start answer with 'answer is'\nif you are in draft game start player added with 'player'")
"""
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

