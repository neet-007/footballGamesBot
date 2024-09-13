from contextlib import asynccontextmanager
from dotenv import load_dotenv
from os import getenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
import telegram
import telegram.ext
from telegram.ext._handlers.messagehandler import MessageHandler
from db.models import Base, Foo, Formation, Draft as d
from draft import handle_draft_add_pos, start_draft_game_command_handler,  new_draft_game_command_handler, join_draft_game_command_handler, set_draft_game_state_command_handler, cancel_draft_game_command_handler, vote_recive_poll_answer_handler, position_draft_message_handler, join_draft_game_callback_handler, random_team_draft_game_callback_handler, end_vote_draft_game_command_handler, start_vote_draft_game_command_handler
from guess_the_player import guess_the_player_start_game_command_handler, guess_the_player_join_game_command_handler, guess_the_player_new_game_command_handler,guess_the_player_ask_question_command_handler, guess_the_player_answer_question_command_handler, guess_the_player_proccess_answer_command_handler, guess_the_player_cancel_game_command_handler, guess_the_player_join_game_callback_handler, guess_the_player_start_round_command_handler, guess_the_player_leave_game_command_handler, guess_thE_player_get_questions_command_handler, handle_guess_the_player_answer_question_command, handle_guess_the_player_ask_question_command, handle_guess_the_player_proccess_answer_command, handle_guess_the_player_start_round
from shared import Draft, GuessThePlayer, Wilty, games
from fastapi import FastAPI, Request, Response 

load_dotenv()

BOT_API_TOKEN = getenv("BOT_API_TOKEN")
if not BOT_API_TOKEN:
    BOT_API_TOKEN = ""

WEBHOOK_URL = getenv("WEBHOOK_URL")
TURSO_DATABASE_URL = getenv("TURSO_DATABASE_URL", "http://127.0.0.1:8080") 
print("db url: ", TURSO_DATABASE_URL)


engine = create_engine("sqlite+libsql" + TURSO_DATABASE_URL, connect_args={'check_same_thread': False}, echo=True)

ptb = (
    telegram.ext.Application.builder()
    .updater(None)
    .token(BOT_API_TOKEN) 
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    print(WEBHOOK_URL)
    if not WEBHOOK_URL:
        return

    await ptb.bot.setWebhook(WEBHOOK_URL) 
    async with ptb:
        await ptb.start()
        yield
        await ptb.stop()

app = FastAPI(lifespan=lifespan)

@app.post("/")
async def process_update(request: Request):
    req = await request.json()
    update = telegram.Update.de_json(req, ptb.bot)
    await ptb.process_update(update)
    return Response(status_code=200)

@app.get("/api/health")
def home():
    print("testest")
    with Session(engine) as session:
        draft = d(
            chat_id=0,
            num_players=4,
            category="test",
            formation_name="433",
            teams=["1", "2", "3"],
            picked_teams=["1", "2", "3"],
            players_ids=["1", "2", "3"],
            start_player_idx=-1,
            curr_player_idx=-1,
            state=0,
            curr_team_idx=0,
            curr_pos="p1"
        )
        session.add(draft)
        session.commit()
        stmt = select(d)

        for item in session.scalars(stmt):
            print(item)

async def handle_start(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or context == None:
        return

    await update.message.reply_text("")

async def handle_dispatch_messages(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("dispatch")
    if not update.message or not update.message.text or not update.effective_chat or not update.effective_user:
        return

    print("if passed")
    chat_id = update.effective_chat.id
    if update.effective_chat.type == "private":
        chat_id_list = context.bot_data.get(update.effective_user.id, None)
        print("chat list found", chat_id_list)
        if chat_id_list == None or len(chat_id_list) == 0:
            return

        print("chat list found", chat_id_list)
        chat_id = chat_id_list[0]
    game = games.get(chat_id, None)
    if game == None:
        return

    print("game found")
    if isinstance(game, Draft):
        print("is draft")
        return await handle_draft_add_pos(update, context)
    if isinstance(game, GuessThePlayer):
        print("is guess the player")
        if update.effective_chat.type == "private":
            print("private")
            return await handle_guess_the_player_start_round(update, context)
        if update.message.reply_to_message:
            print("is reply")
            return await handle_guess_the_player_answer_question_command(update, context)
        else:
            print("else")
            return await handle_guess_the_player_proccess_answer_command(update, context)
    if isinstance(game, Wilty):
        print("wilty")
        return
    else:
        print("should be eror")
        return


ptb.add_handler(guess_the_player_new_game_command_handler)
ptb.add_handler(guess_the_player_join_game_command_handler)
ptb.add_handler(guess_the_player_join_game_callback_handler)
ptb.add_handler(guess_the_player_start_game_command_handler)
ptb.add_handler(guess_the_player_ask_question_command_handler)
#ptb.add_handler(guess_the_player_answer_question_command_handler)
#ptb.add_handler(guess_the_player_proccess_answer_command_handler)
ptb.add_handler(guess_the_player_cancel_game_command_handler)
#ptb.add_handler(guess_the_player_start_round_command_handler)
ptb.add_handler(guess_the_player_leave_game_command_handler)
ptb.add_handler(guess_thE_player_get_questions_command_handler)

ptb.add_handler(new_draft_game_command_handler)
ptb.add_handler(join_draft_game_command_handler)
ptb.add_handler(join_draft_game_callback_handler)
ptb.add_handler(start_draft_game_command_handler)
#ptb.add_handler(position_draft_message_handler)
ptb.add_handler(set_draft_game_state_command_handler)
ptb.add_handler(random_team_draft_game_callback_handler)
ptb.add_handler(cancel_draft_game_command_handler)
ptb.add_handler(end_vote_draft_game_command_handler)
ptb.add_handler(start_vote_draft_game_command_handler)
ptb.add_handler(vote_recive_poll_answer_handler)

ptb.add_handler(MessageHandler((telegram.ext.filters.TEXT & ~ telegram.ext.filters.COMMAND), handle_dispatch_messages))

