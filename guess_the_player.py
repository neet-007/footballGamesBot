from datetime import datetime
import telegram
from telegram._inline.inlinekeyboardbutton import InlineKeyboardButton
from telegram._inline.inlinekeyboardmarkup import InlineKeyboardMarkup
import telegram.ext
from telegram.ext._handlers.callbackqueryhandler import CallbackQueryHandler
from shared import Draft, Wilty, games, GuessThePlayer, remove_jobs
from telegram.ext._handlers.commandhandler import CommandHandler
from telegram.ext._handlers.messagehandler import MessageHandler

async def handle_guess_the_player_new_game(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or not context.job_queue:
        return

    if update.effective_chat.id in games:
        return await update.message.reply_text("a game has already started")

    games[update.effective_chat.id] = GuessThePlayer()
    
    data = {"chat_id":update.effective_chat.id, "time":datetime.now()}
    context.job_queue.run_repeating(handle_guess_the_player_reapting_join_job, data=data, interval=20, first=10,
                                    chat_id=update.effective_chat.id, name="guess_the_player_reapting_join_job")
    context.job_queue.run_once(handle_guess_the_player_start_game_job, when=60, data=data, chat_id=update.effective_chat.id,
                               name="guess_the_player_start_game_job")
    
    await update.message.reply_text("a game has started you can join with the join command /join_guess_the_player or click the button\n/start_game_guess_the_player to start game\ngame starts after 1 minute"
                                    , reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="join", callback_data="guess_the_player_join")]]))

async def handle_guess_the_player_join_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    game:GuessThePlayer | Draft | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await update.message.reply_text("there is no game start one first /new_guess_the_player")
    if not isinstance(game, GuessThePlayer):
        return await update.message.reply_text("there is a game of differant type running")

    res = game.join_game(player=update.effective_user)
    if not res:
        return await update.message.reply_text(f"player f{update.effective_user.mention_html()} has already joined the game",
                                               parse_mode=telegram.constants.ParseMode.HTML)

    await update.message.reply_text(f"player {update.effective_user.mention_html()} has joined the game",
                                    parse_mode=telegram.constants.ParseMode.HTML)

async def handle_guess_the_player_reapting_join_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    game:GuessThePlayer | Draft | Wilty | None = games.get(context.job.chat_id, None)
    if game == None:
        return await context.bot.send_message(text="there is no game start one first /new_guess_the_player", chat_id=context.job.chat_id)
    if not isinstance(game, GuessThePlayer):
        return await context.bot.send_message(text="there is a game of differant type running", chat_id=context.job.chat_id)

    await context.bot.send_message(chat_id=context.job.chat_id, text=f"reaming time to join {round((context.job.data['time'] - datetime.now()).seconds)}")

async def handle_guess_the_player_join_game_callback(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.callback_query or not update.effective_chat or not update.effective_user:
        return

    q = update.callback_query
    await q.answer()

    game:GuessThePlayer | Draft | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await context.bot.send_message(text="there is no game start one first /new_guess_the_player", chat_id=update.effective_chat.id)
    if not isinstance(game, GuessThePlayer):
        return await context.bot.send_message(text="there is a game of differant type running", chat_id=update.effective_chat.id)

    res = game.join_game(player=update.effective_user)
    if not res:
        return await context.bot.send_message(text=f"player {update.effective_user.mention_html()} has already joined game", chat_id=update.effective_chat.id,
                                              parse_mode=telegram.constants.ParseMode.HTML)

    await context.bot.send_message(text=f"player {update.effective_user.mention_html()} has joined the game", chat_id=update.effective_chat.id,
                                   parse_mode=telegram.constants.ParseMode.HTML)

async def handle_guess_the_player_start_game_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    game:GuessThePlayer | Draft | Wilty | None = games.get(context.job.chat_id, None)
    if game == None or not isinstance(game, GuessThePlayer) or game.state != 0:
        return

    remove_jobs("guess_the_player_reapting_join_job", context)
    res, err = game.start_game()
    if not res:
        del games[context.job.chat_id]
        if err == "game error":
            return await context.bot.send_message(text="game error game aborted", chat_id=context.job.chat_id)
        if err == "num players error":
            return await context.bot.send_message(text="not enough players", chat_id=context.job.chat_id)
        else:
            return await context.bot.send_message(text="game error game aborted", chat_id=context.job.chat_id)

    context.bot_data[game.players_ids[game.curr_player_idx]] = context.job.chat_id
    print(context.bot_data)
    await context.bot.send_message(text=f"game started the curr player is {game.players[game.players_ids[game.curr_player_idx]][0].mention_html()} send your the player and hints separated by comma ',' and the hints separated by a dash '-'",
                                   chat_id=context.job.chat_id, parse_mode=telegram.constants.ParseMode.HTML)

async def handle_guess_the_player_start_game_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    game:GuessThePlayer | Draft | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await update.message.reply_text("there is no game start one first /new_guess_the_player")
    if not isinstance(game, GuessThePlayer):
        return await update.message.reply_text("there is a game of differant type running")

    remove_jobs("guess_the_player_reapting_join_job", context)
    remove_jobs("guess_the_player_start_game_job", context)
    res, err = game.start_game()
    if not res:
        del games[update.effective_chat.id]
        if err == "game error":
            return 
        if err == "num players error":
            return await update.message.reply_text("not enough players")
        else:
            return await update.message.reply_text("game error game aborted")

    context.bot_data[game.players_ids[game.curr_player_idx]] = update.effective_chat.id
    print(context.bot_data)
    await update.message.reply_text(f"game started the curr player is {game.players[game.players_ids[game.curr_player_idx]][0].mention_html()} send your the player and hints separated by comma ',' and the hints separated by a dash '-'",
                                    parse_mode=telegram.constants.ParseMode.HTML)

async def handle_guess_the_player_start_round(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("private")
    if not update.message or not update.message.text or not update.effective_user or not update.effective_chat or update.effective_chat.type != "private":
        return

    print(context.bot_data)
    print("if found")
    chat_id = context.bot_data.get(update.effective_user.id, None)
    if chat_id == None:
        return

    print("chat found")
    game:GuessThePlayer | Draft | Wilty | None = games.get(chat_id, None)
    if game == None:
        return await update.message.reply_text("create game at a group first")
    if not isinstance(game, GuessThePlayer):
        return await update.message.reply_text("there is a game of differant type running")

    print("game found")
    if game.state != 1 and game.state != 3:
        return 

    print("state if passed")
    if update.effective_user.id != game.players[game.players_ids[game.curr_player_idx]][0].id:
        return 

    print("currect user found")
    text = update.message.text.lower().split(",")
    if len(text) != 2:
        return await update.message.reply_text("must provide the player and hints separated by comma ','")

    res, err = game.start_round(player=update.effective_user, curr_answer=text[0], curr_hints=text[1].split("-"))
    if not res:
        if err == "game error":
            return 
        if err == "empty inputs":
            return await update.message.reply_text("must provide the player and hints separated by comma ','")
        if err == "num hints error":
            return await update.message.reply_text("must provide 3 hints separeated by dash '-'")
        if err == "curr player error":
            return
        else:
            del context.bot_data[update.effective_user.id]
            return await update.message.reply_text("game error game aborted")

    text = "\n".join([f"{index}. {hint}" for index, hint in enumerate(game.curr_hints, start=1)])
    await context.bot.send_message(text=f"the curr hints are\n{text}\n every player has 3 questions and 2 tries\nuse /answer_player_guess_the_player followed by the player", chat_id=chat_id)

async def handle_guess_the_player_ask_question_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_chat or not update.effective_user or not context.job_queue or not update.message.text:
        return

    game:GuessThePlayer | Draft | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await update.message.reply_text("there is no game start one first /new_guess_the_player")
    if not isinstance(game, GuessThePlayer):
        return await update.message.reply_text("there is a game of differant type running")

    update.message.text.replace("/guess_the_player_ask_q", "").lower().strip()
    res, err = game.ask_question(player=update.effective_user, question=update.message.text.replace("/ask_q_guess_the_player", ""))
    if not res:
        if err == "game_error":
            return 
        if err == "curr player error":
            return 
        if err == "no questions":
            return await update.message.reply_text("you have used all your questions")
        if err == "there is askin player error":
            return await update.message.reply_text("there is a question before that")
        else:
            return await update.message.reply_text("game error game aborted")

    await update.message.reply_text(f"{game.players[game.players_ids[game.curr_player_idx]][0].mention_html()} answer the question by replying to the qeustion", parse_mode=telegram.constants.ParseMode.HTML)

async def handle_guess_the_player_answer_question_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.reply_to_message or not update.message.reply_to_message.from_user or not update.message.text or not update.effective_chat or not update.effective_user or not context.job_queue or not update.message.reply_to_message.text:
        return

    game:GuessThePlayer | Draft | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await update.message.reply_text("there is no game start one first /new_guess_the_player")
    if not isinstance(game, GuessThePlayer):
        return await update.message.reply_text("there is a game of differant type running")

    res, err = game.answer_question(player=update.effective_user, player_asked=update.message.reply_to_message.from_user,
                                    question=update.message.reply_to_message.text.replace("/ask_q_guess_the_player", ""),
                                    answer=update.message.text)
    if not res:
        if err == "game error":
            return 
        if err == "curr player error":
            return print("is not curr player")
        if err == "player is not the asking error":
            return print("player is not asking")
        if err == "no asking player error":
            return print("there is not question")
        if err == "not the question":
            return
        else:
            return await update.message.reply_text("game error game aborted")

    await update.message.reply_text("a quesiton has been detucted")

async def handle_guess_the_player_proccess_answer_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("proccessa answer")
    if update.effective_chat.type == "private":
        return await handle_guess_the_player_start_round(update, context)
    if not update.message or not update.message.text or not update.effective_chat or not update.effective_user or not context.job_queue:
        return

    print("if passed")
    game:GuessThePlayer | Draft | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await update.message.reply_text("there is no game start one first /new_guess_the_player")
    if not isinstance(game, GuessThePlayer):
        return await update.message.reply_text("there is a game of differant type running")

    if game.state != 2:
        return

    print("game found")
    res, err = game.proccess_answer(player=update.effective_user, answer=update.message.text.replace("/answer_player_guess_the_player", "").lower().strip())
    if not res:
        if err == "game error":
            return 
        if err == "curr player error":
            return
        if err == "muted player":
            return
        else:
            return await update.message.reply_text("game error game aborted")
    
    print(err)
    if err == "false":
        return await update.message.reply_text("the answer is wrong")
    if err == "correct":
        context.job_queue.run_once(handle_guess_the_player_end_round_job, when=0, chat_id=update.effective_chat.id)
        return await update.message.reply_text("your answer is correct")
    if err == "all players muted":
        context.job_queue.run_once(handle_guess_the_player_end_round_job, when=0, chat_id=update.effective_chat.id)
        return await update.message.reply_text("you have lost")
    else:
        return await update.message.reply_text("game error game aborted")

async def handle_guess_the_player_end_round_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("end round")
    if not context.job or not context.job.chat_id or not context.job_queue:
        return

    print("if passed")
    game:GuessThePlayer | Draft | Wilty | None = games.get(context.job.chat_id, None)
    if game == None:
        return await context.bot.send_message(text="there is no game start one first /new_guess_the_player", chat_id=context.job.chat_id)
    if not isinstance(game, GuessThePlayer):
        return await context.bot.send_message(text="there is a game of differant type running", chat_id=context.job.chat_id)

    print("game found")
    res, err = game.end_round()
    if not res:
        if err == "game error":
            return 
        else:
            pass

    print("no error")
    if err == "game end":
        print("end game")
        context.job_queue.run_once(handle_guess_the_player_end_game_job, when=0, chat_id=context.job.chat_id)
        return await context.bot.send_message(text="the game has ended the results will come now", chat_id=context.job.chat_id)
    if err == "round end":
        print("rouind end")
        context.bot_data[game.players_ids[game.curr_player_idx]] = context.job.chat_id
        print(context.bot_data)
        await context.bot.send_message(text=f"gane started the curr player is {game.players[game.players_ids[game.curr_player_idx]][0].mention_html()} send your the player and hints separated by comma ',' and the hints separated by a dash '-'",
                                       chat_id=context.job.chat_id, parse_mode=telegram.constants.ParseMode.HTML)
    else:
        return await context.bot.send_message(text="game error game aborted", chat_id=context.job.chat_id)

async def handle_guess_the_player_end_game_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("end game")
    if not context.job or not context.job.chat_id or not context.job_queue:
        return

    print("if passed")
    game:GuessThePlayer | Draft | Wilty | None = games.get(context.job.chat_id, None)
    if game == None:
        return await context.bot.send_message(text="there is no game start one first /new_guess_the_player", chat_id=context.job.chat_id)
    if not isinstance(game, GuessThePlayer):
        return await context.bot.send_message(text="there is a game of differant type running", chat_id=context.job.chat_id)
        
    print("game found")
    del games[context.job.chat_id]
    scores, winners = game.end_game()
    text = ""
    for player, score in scores.items():
        text += f"{player.mention_html()}:{score}\n"

    return await context.bot.send_message(text=f"scores:\n{text}\nwinners:\n{winners}", chat_id=context.job.chat_id, parse_mode=telegram.constants.ParseMode.HTML)

async def handle_guess_the_player_leave_game(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or not update.effective_user or not context.job_queue:
        return

    game:GuessThePlayer | Draft | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await update.message.reply_text("there is no game start one first /new_guess_the_player")
    if not isinstance(game, GuessThePlayer):
        return await update.message.reply_text("there is a game of differant type running")

    res, err = game.leave_game(player=update.effective_user)
    if not res:
        if err == "player not in game error":
            return
        if err == "end round":
            context.job_queue.run_once(handle_guess_the_player_end_round_job, when=0, chat_id=update.effective_chat.id)
        if err == "end game":
            context.job_queue.run_once(handle_guess_the_player_end_game_job, when=0, chat_id=update.effective_chat.id)
        else:
            return await update.message.reply_text("game error game aborted")

    await update.message.reply_text(f"player {update.effective_user.mention_html()} left the game", parse_mode=telegram.constants.ParseMode.HTML)

async def handle_guess_the_player_cancel_game(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    game:GuessThePlayer | Draft | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await update.message.reply_text("there is no game start one first /new_guess_the_player")
    if not isinstance(game, GuessThePlayer):
        return await update.message.reply_text("there is a game of differant type running")

    del games[update.effective_chat.id]
    remove_jobs("guess_the_player_reapting_join_job", context)
    remove_jobs("guess_the_player_start_game_job", context)
    remove_jobs("guess_the_player_end_round_job", context)
    remove_jobs("guess_the_player_end_game_job", context)
    await update.message.reply_text("game cancel")

async def handle_guess_the_player_get_questions(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    game:GuessThePlayer | Draft | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await update.message.reply_text("there is no game start one first /new_guess_the_player")
    if not isinstance(game, GuessThePlayer):
        return await update.message.reply_text("there is a game of differant type running")

    questions = game.asked_questions
    if not questions:
        return await update.message.reply_text("there are no questions")

    text = ""
    for q, a in questions.items():
        text += f"q-{q}:{a}\n"

    await update.message.reply_text(f"the questions are\n{text}")

        

guess_the_player_new_game_command_handler = CommandHandler("new_guess_the_player", handle_guess_the_player_new_game)
guess_the_player_join_game_command_handler = CommandHandler("join_guess_the_player", handle_guess_the_player_join_command)
guess_the_player_start_game_command_handler = CommandHandler("start_game_guess_the_player", handle_guess_the_player_start_game_command)
guess_the_player_ask_question_command_handler = CommandHandler("ask_q_guess_the_player", handle_guess_the_player_ask_question_command)
guess_the_player_proccess_answer_command_handler = MessageHandler((telegram.ext.filters.TEXT & ~ telegram.ext.filters.COMMAND), handle_guess_the_player_proccess_answer_command)
guess_the_player_leave_game_command_handler = CommandHandler("leave_game_guess_the_player", handle_guess_the_player_leave_game)
guess_the_player_cancel_game_command_handler = CommandHandler("cancel_guess_the_player", handle_guess_the_player_cancel_game)
guess_thE_player_get_questions_command_handler = CommandHandler("get_questions_guess_the_player", handle_guess_the_player_get_questions)
guess_the_player_answer_question_command_handler = MessageHandler((telegram.ext.filters.TEXT & telegram.ext.filters.REPLY & ~ telegram.ext.filters.COMMAND),
                                                                  handle_guess_the_player_answer_question_command)
guess_the_player_start_round_command_handler = MessageHandler((telegram.ext.filters.TEXT & ~telegram.ext.filters.REPLY &~ telegram.ext.filters.COMMAND),
                                                             handle_guess_the_player_start_round)
guess_the_player_join_game_callback_handler = CallbackQueryHandler(handle_guess_the_player_join_game_callback, pattern="^guess_the_player_join$")
