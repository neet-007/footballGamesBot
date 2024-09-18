import telegram
from telegram._inline.inlinekeyboardbutton import InlineKeyboardButton
from telegram._inline.inlinekeyboardmarkup import InlineKeyboardMarkup
import telegram.ext
from shared import WILTY_ROUNDS, GuessThePlayer, Wilty, games, remove_jobs
from datetime import datetime

async def handle_wilty_start_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or not context.job_queue:
        return

    if update.effective_chat.id in games:
        return await update.message.reply_text("there is already a game")

    game = Wilty()
    games[update.effective_chat.id] = game

    data = {"chat_id":update.effective_chat.id, "time":datetime.now()}
    context.job_queue.run_repeating(handle_wilty_reapting_join_job, data=data, interval=20, first=10,
                                    chat_id=update.effective_chat.id, name="wilty_reapting_join_job")
    context.job_queue.run_once(handle_wilty_start_game_job, when=60, data=data, chat_id=update.effective_chat.id,
                               name="wilty_start_game_job")

    await update.message.reply_text("a game has started join with /wilty_join or press the button\ngame starts after 1 minute",
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="join", callback_data="wilty_join")]]))

async def handle_wilty_join_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    game:GuessThePlayer  | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await update.message.reply_text("there is no game start one first /new_wilty")
    if not isinstance(game, Wilty):
        return await update.message.reply_text("there is a game of differant type running")

    res = game.join_game(player=update.effective_user)
    if not res:
        return await update.message.reply_text(f"player f{update.effective_user.mention_html()} has already joined the game",
                                               parse_mode=telegram.constants.ParseMode.HTML)

    await update.message.reply_text(f"player {update.effective_user.mention_html()} has joined the game",
                                    parse_mode=telegram.constants.ParseMode.HTML)

async def handle_wilty_reapting_join_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    game:GuessThePlayer  | Wilty | None = games.get(context.job.chat_id, None)
    if game == None:
        return await context.bot.send_message(text="there is no game start one first /new_wilty", chat_id=context.job.chat_id)
    if not isinstance(game, Wilty):
        return await context.bot.send_message(text="there is a game of differant type running", chat_id=context.job.chat_id)

    await context.bot.send_message(chat_id=context.job.chat_id, text=f"reaming time to join {round((context.job.data['time'] - datetime.now()).seconds)}")

async def handle_wilty_join_game_callback(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.callback_query or not update.effective_chat or not update.effective_user:
        return

    q = update.callback_query
    await q.answer()

    game:GuessThePlayer  | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await context.bot.send_message(text="there is no game start one first /new_wilty", chat_id=update.effective_chat.id)
    if not isinstance(game, Wilty):
        return await context.bot.send_message(text="there is a game of differant type running", chat_id=update.effective_chat.id)

    res = game.join_game(player=update.effective_user)
    if not res:
        return await context.bot.send_message(text=f"player {update.effective_user.mention_html()} has already joined game", chat_id=update.effective_chat.id,
                                              parse_mode=telegram.constants.ParseMode.HTML)

    await context.bot.send_message(text=f"player {update.effective_user.mention_html()} has joined the game", chat_id=update.effective_chat.id,
                                   parse_mode=telegram.constants.ParseMode.HTML)

async def handle_wilty_start_game_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    game:GuessThePlayer  | Wilty | None = games.get(context.job.chat_id, None)
    if game == None or not isinstance(game, Wilty) or game.state != 0:
        return

    remove_jobs("wilty_join_job", context)
    res, err = game.start_game()
    if not res:
        del games[context.job.chat_id]
        if err == "game error":
            return await context.bot.send_message(text="game error game aborted", chat_id=context.job.chat_id)
        if err == "num players error":
            return await context.bot.send_message(text="not enough players", chat_id=context.job.chat_id)
        else:
            return await context.bot.send_message(text="game error game aborted", chat_id=context.job.chat_id)

    for id in game.players_ids:
        context.bot_data[id] = context.job.chat_id

    print(context.bot_data)
    await context.bot.send_message(text=f"game started send your statements to the bot in a private message, it must be in the format\ntransfers, managers, player comparisions, predictions, young players\n each statement is inorder and separated by comma ',', dont use commas in your statement",
                                   chat_id=context.job.chat_id, parse_mode=telegram.constants.ParseMode.HTML)

async def handle_wilty_get_statements(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or update.effective_chat.type != "private" or not update.effective_user or not update.message.text:
        return

    chat_id = context.bot_data.get(update.effective_user.id, None)
    if chat_id == None:
        return

    game:GuessThePlayer  | Wilty | None = games.get(chat_id, None)
    if game == None or not isinstance(game, Wilty):
        return
    if game.state != 1:
        return

    statements = update.message.text.split(",")
    res, err = game.get_statements(player=update.effective_user, statements=statements)
    if not res:
        if err == "game error":
            return
        if err == "player has submited error":
            return context.bot.send_message(text="you have already sent your statements", chat_id=chat_id)
        if err == "statements length error":
            return context.bot.send_message(text="you must provide 5 statements separated by comma ','", chat_id=chat_id)

    if err == "start game":
        res_, _ = game.start_round()
        if not res_:
                return
        await context.bot.send_message(text=f"the curr mode is {game.players[game.players_ids[game.curr_mod_idx]].mention_html} and curr player is {game.players[game.players_ids[game.curr_player_idx]].mention_html} the mod must send me the statemnt\n send __same__ if you dont want to change else write the statment", chat_id=chat_id,
                                       parse_mode=telegram.constants.ParseMode.HTML)

async def handle_wilty_get_mod_statement(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or update.effective_chat.type != "private" or not update.effective_user or not update.message.text or not context.job_queue:
        return

    chat_id = context.bot_data.get(update.effective_user.id, None)
    if chat_id == None:
        return

    game:GuessThePlayer  | Wilty | None = games.get(chat_id, None)
    if game == None or not isinstance(game, Wilty):
        return
    if game.state != 1:
        return

    res, err = game.get_mod_statement(player=update.effective_user, statement=update.message.text)
    if not res:
        if err == "game error":
            return
        if err == "curr mod error":
            return

    data = {"chat_id":update.effective_chat.id, "time":datetime.now()}
    context.job_queue.run_repeating(handle_wilty_reapting_vote_job, data=data, interval=20, first=10,
                                    chat_id=chat_id, name="wilty_reapting_vote_job")
    context.job_queue.run_once(handle_wilty_start_vote_job, when=60, data=data, chat_id=chat_id,
                               name="wilty_start_vote_job")
    await context.bot.send_message(text=f"the curr player is {game.players[game.players_ids[game.curr_player_idx]].mention_html()} the statement is {game.curr_statement} you have 3 mintues to discuss until the vote", chat_id=chat_id)

async def handle_wilty_reapting_vote_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    game:GuessThePlayer  | Wilty | None = games.get(context.job.chat_id, None)
    if game == None:
        return await context.bot.send_message(text="there is no game start one first /new_wilty", chat_id=context.job.chat_id)
    if not isinstance(game, Wilty):
        return await context.bot.send_message(text="there is a game of differant type running", chat_id=context.job.chat_id)

    await context.bot.send_message(chat_id=context.job.chat_id, text=f"reaming time to discusse {round((context.job.data['time'] - datetime.now()).seconds)}")

async def handle_wilty_start_vote_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    game:GuessThePlayer  | Wilty | None = games.get(context.job.chat_id, None)
    if game == None or not isinstance(game, Wilty) or game.state != 0 or not context.job_queue:
        return

    remove_jobs("wilty_reapting_vote_job", context)

    poll_data = {
        "chat_id":context.job.chat_id,
        "question":"is it his statement",
        "options":["yes", "no"],
        "answers":[0, 0]
    }

    print(context.bot_data)
    message = await context.bot.send_poll(question="is it his statement", options=["yes", "no"], is_anonymous=False, allows_multiple_answers=False,
                                chat_id=context.job.chat_id)
    poll_data["message_id"] = message.message_id
    context.bot_data[f"poll_{message.poll.id}"] = poll_data
    context.job_queue.run_once(handle_wilty_end_vote_job, when=60, name="wilty_end_vote_job")

async def handle_wilty_recive_vote_job(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.poll_answer or not update.effective_chat or not context.job_queue:
        return

    poll_answer = update.poll_answer
    poll_id = poll_answer.poll_id

    try:
        answers = context.bot_data[f"poll_{poll_id}"]["answers"]
    except KeyError:
        return

    game:GuessThePlayer  | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None or not isinstance(game, Wilty) or game.state != 0 or not context.job_queue:
        return

    answers[poll_answer.option_ids[0]] += 1
    if sum(answers) == game.num_players:
        context.job_queue.run_once(handle_wilty_end_vote_job, when=0, data={"answers":answers}, name="wilty_end_vote_job")

async def handle_wilty_end_vote_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    answers = context.job.data["answers"]
    game:GuessThePlayer  | Wilty | None = games.get(context.job.chat_id, None)
    if game == None or not isinstance(game, Wilty) or game.state != 0:
        return

    remove_jobs("wilty_reapting_vote_job", context)
    remove_jobs("wilty_end_vote_job", context)

    res, err = game.play(vote=answers)
    if not res:
        if err == "game error":
            return

    if err == "continue":
        return await context.bot.send_message(text=f"the curr mode is {game.players[game.players_ids[game.curr_mod_idx]].mention_html} and curr player is {game.players[game.players_ids[game.curr_player_idx]].mention_html} the mod must send me the statemnt\n send __same__ if you dont want to change else write the statment", chat_id=context.job.chat_id,
                                       parse_mode=telegram.constants.ParseMode.HTML)
    if err == "end round":
        return context.job_queue.run_once(handle_wilty_end_round_job, when=0, name="wilty_end_round_job")


async def handle_wilty_end_round_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    game:GuessThePlayer  | Wilty | None = games.get(context.job.chat_id, None)
    if game == None or not isinstance(game, Wilty) or game.state != 0:
        return

    res, err = game.end_round()
    if not res:
        if err == "game error":
            return

    if err == "next round":
        return await context.bot.send_message(text=f"the curr round is {WILTY_ROUNDS[game.round_type]} the curr mode is {game.players[game.players_ids[game.curr_mod_idx]].mention_html} and curr player is {game.players[game.players_ids[game.curr_player_idx]].mention_html} the mod must send me the statemnt\n send __same__ if you dont want to change else write the statment", chat_id=context.job.chat_id,
                                       parse_mode=telegram.constants.ParseMode.HTML)
    if err == "end game":
        context.job_queue.run_once(handle_wilty_end_game_job, when=0, name="wilty_end_game_job")
        return await context.bot.send_message(text="the game has ended the results will come", chat_id=context.job.chat_id)

async def handle_wilty_end_game_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    game:GuessThePlayer  | Wilty | None = games.get(context.job.chat_id, None)
    if game == None or not isinstance(game, Wilty) or game.state != 0:
        return

    text, winners = game.end_game()

    if not text or not winners:
        return

    await context.bot.send_message(text=f"the scores:\n{text}\n\nthe winners:\n{winners}", chat_id=context.job.chat_id,
                                   parse_mode=telegram.constants.ParseMode.HTML)
    
async def handle_wilty_leave_game(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    return

async def handle_wilty_cancel_game(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    game:GuessThePlayer  | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await update.message.reply_text("there is no game start one first /new_guess_the_player")
    if not isinstance(game, Wilty):
        return await update.message.reply_text("there is a game of differant type running")

    del games[update.effective_chat.id]
    remove_jobs("wilty_reapting_join_job", context)
    remove_jobs("wilty_start_game_job", context)
    remove_jobs("wilty_end_round_job", context)
    remove_jobs("wilty_end_game_job", context)
    await update.message.reply_text("game cancel")
