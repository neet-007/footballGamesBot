from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from db.connection import get_session, new_db
from games.guess_the_player_functions import answer_question_guess_the_player, ask_question_guess_the_player, cancel_game_guess_the_player, check_guess_the_player, end_game_guess_the_player, end_round_guess_the_player, get_asked_questions_guess_the_player, join_game_guess_the_player, leave_game_guess_the_player, new_game_guess_the_player, proccess_answer_guess_the_player, start_game_guess_the_player, start_round_guess_the_player
from utils.helpers import remove_jobs

PLAYER_NOT_IN_GAME_ERROR = "player is not in game"
NO_GAME_ERROR = "there is no game in this chat \nstart one using /new_guess_the_player"
EXCEPTION_ERROR = "internal error happend please try again later"
STATE_ERROR = "game error happend\n or this is not the time for this command"
CURR_PLAYER_ERROR = "❌  your are not the current player"

JOBS_END_TIME_SECONDS = 180
JOBS_REPEATING_INTERVAL = 20
JOBS_REPEATING_FIRST = 10

GUESS_THE_PLAYER_NEW = "guess_the_player_new"
GUESS_THE_PLAYER_JOIN = "guess_the_player_join"
GUESS_THE_PLAYER_START = "guess_the_player_start"
GUESS_THE_PLAYER_SET_STATE = "guess_the_player_set_state"
GUESS_THE_PLAYER_ASK_Q = "guess_the_player_ask_q"
GUESS_THE_PLAYER_ANSWER_Q = "guess_the_player_answer_q"
GUESS_THE_PLAYER_ANSWER = "guess_the_player_answer"
GUESS_THE_PLAYER_GET_QUESTIONS = "guess_the_player_get_questions"
GUESS_THE_PLAYER_LEAVE_GAME = "guess_the_player_leave_game"
GUESS_THE_PLAYER_CANCEL_GAME = "guess_the_player_cancel_game"

async def handle_guess_the_player_new_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_chat or not context.job_queue or update.effective_chat.type == "private":
        return

    with get_session() as session:
        num_rounds = update.message.text.replace(f"/{GUESS_THE_PLAYER_NEW}", "").strip() or None

        if num_rounds is not None:
            try:
                num_rounds = int(num_rounds)
            except ValueError:
                return await update.message.reply_text("The number of rounds must be an integer.")

        res, err = new_game_guess_the_player(update.effective_chat.id, num_rounds, session)
    if not res:
        if err == "a game has started":
            return await update.message.reply_text("the is game in chat cant make a new on")
        if err == "num of rounds less than 1":
            return await update.message.reply_text("the number of rounds must be higher than or equal to 1")
        if err == "exception":
            return await update.message.reply_text(EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(EXCEPTION_ERROR)

    data = {"time":datetime.now()}
    context.job_queue.run_repeating(handle_guess_the_player_reapting_join_job, data=data, interval=JOBS_REPEATING_INTERVAL,
                                    first=JOBS_REPEATING_FIRST,
                                    chat_id=update.effective_chat.id, name=f"guess_the_player_reapting_join_job_{update.effective_chat.id}")
    context.job_queue.run_once(handle_guess_the_player_start_game_job, when=JOBS_END_TIME_SECONDS,
                               data=data, chat_id=update.effective_chat.id,
                               name=f"guess_the_player_start_game_job_{update.effective_chat.id}")
    
    await update.message.reply_text(f"a guess the player game has started you can join with /{GUESS_THE_PLAYER_JOIN} or click the button\n/{GUESS_THE_PLAYER_START} to start game\ngame starts after 1 minute"
                                    , reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="join", callback_data="guess_the_player_join")]]))

async def handle_guess_the_player_join_command(update:Update, _: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or not update.effective_user or update.effective_chat.type == "private":
        return

    with get_session() as session:
        res, err = join_game_guess_the_player(update.effective_chat.id, update.effective_user.id, session)
    if not res:
        if err == "no game":
            return await update.message.reply_text(NO_GAME_ERROR)
        if err == "player already in game":
            return await update.message.reply_text(f"player f{update.effective_user.mention_html()} has already joined the game",
                                                   parse_mode=ParseMode.HTML)
        if err == "state error":
            return await update.message.reply_text(STATE_ERROR)
        if err == "exception":
            return await update.message.reply_text(EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(EXCEPTION_ERROR)
 
    await update.message.reply_text(f"player {update.effective_user.mention_html()} has joined the game",
                                    parse_mode=ParseMode.HTML)

async def handle_guess_the_player_reapting_join_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    with get_session() as session:
        res, err,  _, _= check_guess_the_player(context.job.chat_id, session)
    if not res:
        if err == "no game found":
            return await context.bot.send_message(text=NO_GAME_ERROR, chat_id=context.job.chat_id)
        if err == "exception":
            return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=context.job.chat_id)
        else:
            return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=context.job.chat_id)

    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to join: {round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )

async def handle_guess_the_player_join_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.callback_query or not update.effective_chat or not update.effective_user or update.effective_chat.type == "private":
        return

    q = update.callback_query
    await q.answer()

    with get_session() as session:
        res, err = join_game_guess_the_player(update.effective_chat.id, update.effective_user.id, session)
    if not res:
        if err == "no game":
            return await context.bot.send_message(chat_id=update.effective_chat.id,
                                                  text=NO_GAME_ERROR)
        if err == "player already in game":
            return await context.bot.send_message(chat_id=update.effective_chat.id,
                                                  text=f"player f{update.effective_user.mention_html()} has already joined the game",
                                                   parse_mode=ParseMode.HTML)
        if err == "state error":
            return await context.bot.send_message(chat_id=update.effective_chat.id,
                                                  text=STATE_ERROR)
        if err == "exception":
            return await context.bot.send_message(chat_id=update.effective_chat.id,
                                                  text=EXCEPTION_ERROR)
        else:
            return await context.bot.send_message(chat_id=update.effective_chat.id,
                                                  text=EXCEPTION_ERROR)

    await context.bot.send_message(text=f"player {update.effective_user.mention_html()} has joined the game", chat_id=update.effective_chat.id,
                                   parse_mode=ParseMode.HTML)

async def handle_guess_the_player_start_game_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    remove_jobs(f"guess_the_player_reapting_join_job_{context.job.chat_id}", context)
    with get_session() as session:
        res, err, curr_player_id = start_game_guess_the_player(context.job.chat_id, session)
    if not res:
        if err == "no game error":
            return await context.bot.send_message(text=NO_GAME_ERROR, chat_id=context.job.chat_id)
        if err == "player not in game":
            return await context.bot.send_message(text=PLAYER_NOT_IN_GAME_ERROR, chat_id=context.job.chat_id)
        if err == "no players associated with the game":
            return await context.bot.send_message(text=PLAYER_NOT_IN_GAME_ERROR, chat_id=context.job.chat_id)
        if err == "state error":
            return await context.bot.send_message(text=STATE_ERROR, chat_id=context.job.chat_id)
        if err == "number of players is less than 2 or not as expected":
            return await context.bot.send_message(text="not enough players", chat_id=context.job.chat_id)
        if err == "num players error":
            return await context.bot.send_message(text="not enough players", chat_id=context.job.chat_id)
        if err == "exception":
            return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=context.job.chat_id)
        else:
            return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=context.job.chat_id)

    curr_player = await context.bot.get_chat_member(chat_id=context.job.chat_id, user_id=curr_player_id)
    curr_player = curr_player.user

    await context.bot.send_message(text=f"the game has started the current player is {curr_player.mention_html()}\nsend your player and hints separated by comma ',' and the hints separated by a dash '-' like this\n[player], [hint1-hint2-hint3]",
                                   chat_id=context.job.chat_id, parse_mode=ParseMode.HTML)

async def handle_guess_the_player_start_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or update.effective_chat.type == "private":
        return

    remove_jobs(f"guess_the_player_reapting_join_job_{update.effective_chat.id}", context)
    remove_jobs(f"guess_the_player_start_game_job_{update.effective_chat.id}", context)
    with get_session() as session:
        res, err, curr_player_id = start_game_guess_the_player(update.effective_chat.id, session)
    if not res:
        if err == "no game error":
            return await update.message.reply_text(NO_GAME_ERROR)
        if err == "player not in game":
            return await update.message.reply_text(PLAYER_NOT_IN_GAME_ERROR)
        if err == "no players associated with the game":
            return await update.message.reply_text(PLAYER_NOT_IN_GAME_ERROR)
        if err == "state error":
            return await update.message.reply_text(STATE_ERROR)
        if err == "number of players is less than 2 or not as expected":
            return await update.message.reply_text("number of player less than 2")
        if err == "num players error":
            return await update.message.reply_text("number of player less than 2")
        if err == "exception":
            return await update.message.reply_text(EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(EXCEPTION_ERROR)

    curr_player = await context.bot.get_chat_member(chat_id=update.effective_chat.id, user_id=curr_player_id)
    curr_player = curr_player.user

    await update.message.reply_text(f"the game has started the current player is {curr_player.mention_html()}\nsend your player and hints separated by comma ',' and the hints separated by a dash '-' like this\n[player], [hint1-hint2-hint3]",
                                    parse_mode=ParseMode.HTML)

async def handle_guess_the_player_set_state_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_user or not update.effective_chat or update.effective_chat.type != "private":
        return

    text = update.message.text.lower().replace(f"/{GUESS_THE_PLAYER_SET_STATE}", "").split(",")
    if len(text) != 2:
        return await update.message.reply_text("must provide the player and hints separated by comma ','\n[player], [hint1-hint2-hint3]")

    with get_session() as session:
        res, err, curr_hints, chat_id = start_round_guess_the_player(update.effective_user.id, text[1].split("-"), text[0], session)
    if not res:
        if err == "no game found":
            return await update.message.reply_text(NO_GAME_ERROR)
        if err == "player not in game":
            return await update.message.reply_text(PLAYER_NOT_IN_GAME_ERROR)
        if err == "state error":
            return await update.message.reply_text(STATE_ERROR)
        if err == "player not found or not in game":
            return await update.message.reply_text(PLAYER_NOT_IN_GAME_ERROR)
        if err == "curr player error":
            return await update.message.reply_text(CURR_PLAYER_ERROR)
        if err == "empty inputs":
            return await update.message.reply_text("must provide the player and hints separated by comma ','")
        if err == "num hints error":
            return await update.message.reply_text("must provide 3 hints separeated by dash '-'")
        if err == "exception":
            return await update.message.reply_text(EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(EXCEPTION_ERROR)

    hints = "\n".join([f"{index}. {hint}" for index, hint in enumerate(curr_hints, start=1)])
    await context.bot.send_message(text=f"the current hints are\n{hints}\n every player has 3 questions and 2 tries\nuse answer is followed by the player\nanswer is [player]", chat_id=chat_id)

async def handle_guess_the_player_ask_question_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_chat or not update.effective_user or update.effective_chat.type == "private" or not context.job_queue or not update.message.text or update.effective_chat.type == "private":
        return

    with get_session() as session:
        res, err, curr_player_id = ask_question_guess_the_player(update.effective_chat.id, update.effective_user.id,
                                                 update.message.text.replace(f"/{GUESS_THE_PLAYER_ASK_Q}", "").lower().strip(), session)
        print(err)
    if not res:
        if err == "no game found":
            return await update.message.reply_text(NO_GAME_ERROR)
        if err == "state error":
            return await update.message.reply_text(STATE_ERROR)
        if err == "player not in game":
            return await update.message.reply_text(PLAYER_NOT_IN_GAME_ERROR)
        if err == "curr player error":
            return await update.message.reply_text(CURR_PLAYER_ERROR)
        if err == "no questions":
            return await update.message.reply_text("you have used all your questions")
        if err == "there is askin player error":
            return await update.message.reply_text("there is a question before that")
        if err == "exception":
            return await update.message.reply_text(EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(EXCEPTION_ERROR)
    
    curr_player = await update.effective_chat.get_member(user_id=curr_player_id)
    curr_player = curr_player.user

    await update.message.reply_text(f"{curr_player.mention_html()} answer the question by using command /{GUESS_THE_PLAYER_ANSWER_Q}[answer]", parse_mode=ParseMode.HTML)

async def handle_guess_the_player_answer_question_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_chat or update.effective_chat.type == "private" or not update.effective_user or not context.job_queue:
        return

    with get_session() as session:
        res, err = answer_question_guess_the_player(update.effective_chat.id, update.effective_user.id,
                                                    update.message.text.replace(f"/{GUESS_THE_PLAYER_ANSWER_Q}", ""), session)
    if not res:
        if err == "game not found":
            return await update.message.reply_text(NO_GAME_ERROR)
        if err == "state error":
            return await update.message.reply_text(STATE_ERROR)
        if err == "players not in game":
            return await update.message.reply_text(PLAYER_NOT_IN_GAME_ERROR)
        if err == "curr player error":
            return await update.message.reply_text(CURR_PLAYER_ERROR)
        if err == "not the question":
            return await update.message.reply_text("this is not the message with querstion")
        if err == "exception":
            return await update.message.reply_text(EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(EXCEPTION_ERROR)

    await update.message.reply_text("a quesiton has been detucted")

async def handle_guess_the_player_proccess_answer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_chat or update.effective_chat.type == "private" or not update.effective_user or not context.job_queue:
        return

    with get_session() as session:
        res, err = proccess_answer_guess_the_player(update.effective_chat.id, update.effective_user.id,
                                                    update.message.text.lower().strip().replace(f"/{GUESS_THE_PLAYER_ANSWER}", ""), session)
    if not res:
        if err == "game not found":
            return await update.message.reply_text(NO_GAME_ERROR)
        if err == "state error":
            return await update.message.reply_text(STATE_ERROR)
        if err == "player not in game":
            return await update.message.reply_text(PLAYER_NOT_IN_GAME_ERROR)
        if err == "curr player error":
            return await update.message.reply_text(CURR_PLAYER_ERROR)
        if err == "muted player":
            return await update.message.reply_text("❌  you are muted")
        if err == "exception":
            return await update.message.reply_text(EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(EXCEPTION_ERROR)
    
    if err == "false":
        return await update.message.reply_text("❌  your answer is wrong")
    if err == "correct":
        context.job_queue.run_once(handle_guess_the_player_end_round_job, when=0, chat_id=update.effective_chat.id,
                                   name=f"guess_the_player_end_round_job_{update.effective_chat.id}")
        return await update.message.reply_text("your answer is correct")
    if err == "all players muted":
        context.job_queue.run_once(handle_guess_the_player_end_round_job, when=0, chat_id=update.effective_chat.id,
                                   name=f"guess_the_player_end_round_job_{update.effective_chat.id}")
        return await update.message.reply_text("you have lost")
    else:
        return await update.message.reply_text(EXCEPTION_ERROR)

async def handle_guess_the_player_end_round_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not context.job_queue:
        return

    with get_session() as session:
        res, err, curr_player_id = end_round_guess_the_player(context.job.chat_id, session)
    if not res:
        if err == "game not found":
            return await context.bot.send_message(text=NO_GAME_ERROR, chat_id=context.job.chat_id)
        if err == "state error":
            return await context.bot.send_message(text=STATE_ERROR, chat_id=context.job.chat_id)
        if err == "player not in game":
            return await context.bot.send_message(text=PLAYER_NOT_IN_GAME_ERROR, chat_id=context.job.chat_id)
        if err == "exception":
            return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=context.job.chat_id)
        else:
            return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=context.job.chat_id)

    if err == "new round" or err == "round end":
        curr_player = await context.bot.get_chat_member(chat_id=context.job.chat_id, user_id=curr_player_id)
        curr_player = curr_player.user
        return await context.bot.send_message(chat_id=context.job.chat_id,
                                       text=f"the game has started the current player is {curr_player.mention_html()}\nsend your player and hints separated by comma ',' and the hints separated by a dash '-' like this\n[player], [hint1-hint2-hint3]",
                                       parse_mode=ParseMode.HTML)

    if err == "game end":
        await context.bot.send_message(text="the game has ended the results will come now", chat_id=context.job.chat_id)
        context.job_queue.run_once(handle_guess_the_player_end_game_job, when=0, chat_id=context.job.chat_id,
                                   name=f"guess_the_player_end_game_job_{context.job.chat_id}")
        return
    else:
        return await context.bot.send_message(text=err, chat_id=context.job.chat_id)

async def handle_guess_the_player_end_game_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not context.job_queue:
        return

    with get_session() as session:
        res, err, scores, winners = end_game_guess_the_player(context.job.chat_id, session)
    if not res:
        if err == "game not found":
            return await context.bot.send_message(text=NO_GAME_ERROR, chat_id=context.job.chat_id)
        if err == "players not found":
            return await context.bot.send_message(text=PLAYER_NOT_IN_GAME_ERROR, chat_id=context.job.chat_id)
        if err == "exception":
            return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=context.job.chat_id)
        else:
            return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=context.job.chat_id)

    text = ""
    winners_text = ""
    for player_id, score in scores.items():
        player = await context.bot.get_chat_member(chat_id=context.job.chat_id, user_id=player_id)
        text += f"{player.user.mention_html()}:{score}\n"

    for player_id in winners:
        player = await context.bot.get_chat_member(chat_id=context.job.chat_id, user_id=player_id)
        winners_text += f"{player.user.mention_html()}\n"

    return await context.bot.send_message(text=f"scores:\n{text}\nwinners:\n{winners_text}", chat_id=context.job.chat_id, parse_mode=ParseMode.HTML)

async def handle_guess_the_player_leave_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or not update.effective_user or not context.job_queue:
        return

    # mybe handle when the palyer is the current
    with get_session() as session:
        res, err, _ = leave_game_guess_the_player(update.effective_chat.id, update.effective_user.id, session)
    if not res:
        if err == "game not found":
            return await update.message.reply_text(NO_GAME_ERROR)
        if err == "player not in game":
            return await update.message.reply_text(PLAYER_NOT_IN_GAME_ERROR)
        if err == "exception":
            return await update.message.reply_text(EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(EXCEPTION_ERROR)

    await update.message.reply_text(f"player {update.effective_user.mention_html()} left the game", parse_mode=ParseMode.HTML)

async def handle_guess_the_player_cancel_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    with get_session() as session:
        res, err = cancel_game_guess_the_player(update.effective_chat.id, session)
    if not res:
        if err == "no game found":
            await update.message.reply_text(NO_GAME_ERROR)
        if err == "exception":
            await update.message.reply_text(EXCEPTION_ERROR)
        else:
            await update.message.reply_text(EXCEPTION_ERROR)

    remove_jobs(f"guess_the_player_reapting_join_job_{update.effective_chat.id}", context)
    remove_jobs(f"guess_the_player_start_game_job_{update.effective_chat.id}", context)
    remove_jobs(f"guess_the_player_end_round_job_{update.effective_chat.id}", context)
    remove_jobs(f"guess_the_player_end_game_job_{update.effective_chat.id}", context)
    await update.message.reply_text("game cancel")

async def handle_guess_the_player_get_questions(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    with get_session() as session:
        res, err, questions = get_asked_questions_guess_the_player(update.effective_chat.id, session)
    if not res:
        if err == "questions not found":
            return await update.message.reply_text("there are no questions or no game")
        if err == "exception":
            return await update.message.reply_text(EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(EXCEPTION_ERROR)

    text = ""
    for q, a in questions.items():
        text += f"q-{q}:{a}\n"

    await update.message.reply_text(f"the questions are\n{text}")

async def handle_new_db(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    new_db()
    await update.message.reply_text(f"new db")


new_db_handler = CommandHandler("new_db", handle_new_db)
guess_the_player_new_game_command_handler = CommandHandler(GUESS_THE_PLAYER_NEW, handle_guess_the_player_new_game)
guess_the_player_join_game_command_handler = CommandHandler(GUESS_THE_PLAYER_JOIN, handle_guess_the_player_join_command)
guess_the_player_start_game_command_handler = CommandHandler(GUESS_THE_PLAYER_START, handle_guess_the_player_start_game_command)
guess_the_player_set_state_command_handler = CommandHandler(GUESS_THE_PLAYER_SET_STATE, handle_guess_the_player_set_state_command)
guess_the_player_ask_question_command_handler = CommandHandler(GUESS_THE_PLAYER_ASK_Q, handle_guess_the_player_ask_question_command)
guess_the_player_answer_question_command_handler = CommandHandler(GUESS_THE_PLAYER_ANSWER_Q, handle_guess_the_player_answer_question_command)
guess_the_player_proccess_answer_command_handler = CommandHandler(GUESS_THE_PLAYER_ANSWER, handle_guess_the_player_proccess_answer_command)
guess_the_player_leave_game_command_handler = CommandHandler(GUESS_THE_PLAYER_LEAVE_GAME, handle_guess_the_player_leave_game)
guess_the_player_cancel_game_command_handler = CommandHandler(GUESS_THE_PLAYER_CANCEL_GAME, handle_guess_the_player_cancel_game)
guess_thE_player_get_questions_command_handler = CommandHandler(GUESS_THE_PLAYER_GET_QUESTIONS, handle_guess_the_player_get_questions)
guess_the_player_join_game_callback_handler = CallbackQueryHandler(handle_guess_the_player_join_game_callback, pattern="^guess_the_player_join$")
