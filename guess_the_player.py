from datetime import datetime, timedelta
import telegram
from telegram._inline.inlinekeyboardbutton import InlineKeyboardButton
from telegram._inline.inlinekeyboardmarkup import InlineKeyboardMarkup
import telegram.ext
from telegram.ext._handlers.callbackqueryhandler import CallbackQueryHandler
from shared import answer_question_guess_the_player, ask_question_guess_the_player, cancel_game_guess_the_player, check_guess_the_player, end_game_guess_the_player, end_round_guess_the_player, games, get_asked_questions_guess_the_player, join_game_guess_the_player, leave_game_guess_the_player, new_game_guess_the_player, proccess_answer_guess_the_player, remove_jobs, session, start_game_guess_the_player, start_round_guess_the_player
from telegram.ext._handlers.commandhandler import CommandHandler
from telegram.ext._handlers.messagehandler import MessageHandler
from collections import deque

async def handle_test_guess_the_player_new_game(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or not context.job_queue:
        return

    if update.effective_chat.id in games:
        return await update.message.reply_text("a game has already started")

    res, status = new_game_guess_the_player(update.effective_chat.id, session)
    if not res:
        return await update.message.reply_text(status)

    data = {"chat_id":update.effective_chat.id, "time":datetime.now()}
    context.job_queue.run_repeating(handle_test_guess_the_player_reapting_join_job, data=data, interval=20, first=10,
                                    chat_id=update.effective_chat.id, name="guess_the_player_reapting_join_job")
    context.job_queue.run_once(handle_test_guess_the_player_start_game_job, when=60, data=data, chat_id=update.effective_chat.id,
                               name="guess_the_player_start_game_job")
    
    await update.message.reply_text("a game has started you can join with the join command /join_guess_the_player or click the button\n/start_game_guess_the_player to start game\ngame starts after 1 minute"
                                    , reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="join", callback_data="guess_the_player_join")]]))

async def handle_test_guess_the_player_join_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    res, status = join_game_guess_the_player(update.effective_chat.id, update.effective_user.id, session)
    if not res:
        if status == "no game":
            return await update.message.reply_text("there is no game start one first /new_guess_the_player")
        elif status== "player already in game":
            return await update.message.reply_text(f"player f{update.effective_user.mention_html()} has already joined the game",
                                                   parse_mode=telegram.constants.ParseMode.HTML)
        else:
            return await update.message.reply_text(status)
 
    await update.message.reply_text(f"player {update.effective_user.mention_html()} has joined the game",
                                    parse_mode=telegram.constants.ParseMode.HTML)

async def handle_test_guess_the_player_reapting_join_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    res, _, _= check_guess_the_player(context.job.chat_id)
    if not res:
        return await context.bot.send_message(text="there is no game start one first /new_guess_the_player", chat_id=context.job.chat_id)

    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to join: {round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )

async def handle_test_guess_the_player_join_game_callback(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.callback_query or not update.effective_chat or not update.effective_user:
        return

    q = update.callback_query
    await q.answer()

    res, status = join_game_guess_the_player(update.effective_chat.id, update.effective_user.id, session)
    if not res:
        if status == "no game":
            return await context.bot.send_message(chat_id=update.effective_chat.id,
                                                  text="there is no game start one first /new_guess_the_player")
        elif status== "player already in game":
            return await context.bot.send_message(chat_id=update.effective_chat.id,
                                                  text=f"player f{update.effective_user.mention_html()} has already joined the game",
                                                   parse_mode=telegram.constants.ParseMode.HTML)
        else:
            return await context.bot.send_message(chat_id=update.effective_chat.id,
                                                  text=status)

    await context.bot.send_message(text=f"player {update.effective_user.mention_html()} has joined the game", chat_id=update.effective_chat.id,
                                   parse_mode=telegram.constants.ParseMode.HTML)

async def handle_test_guess_the_player_start_game_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    remove_jobs("guess_the_player_reapting_join_job", context)
    res, err, curr_player_id = start_game_guess_the_player(context.job.chat_id)
    if not res:
        if err == "game error":
            return await context.bot.send_message(text="game error game aborted", chat_id=context.job.chat_id)
        if err == "num players error":
            return await context.bot.send_message(text="not enough players", chat_id=context.job.chat_id)
        else:
            return await context.bot.send_message(text="game error game aborted", chat_id=context.job.chat_id)

    context.bot_data.setdefault(curr_player_id, deque()).append(context.job.chat_id)
    curr_player = await context.bot.get_chat_member(chat_id=context.job.chat_id, user_id=curr_player_id)
    curr_player = curr_player.user

    await context.bot.send_message(text=f"game started the curr player is {curr_player.mention_html()} send your the player and hints separated by comma ',' and the hints separated by a dash '-'",
                                   chat_id=context.job.chat_id, parse_mode=telegram.constants.ParseMode.HTML)

async def handle_test_guess_the_player_start_game_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    remove_jobs("guess_the_player_reapting_join_job", context)
    remove_jobs("guess_the_player_start_game_job", context)
    res, err, curr_player_id = start_game_guess_the_player(update.effective_chat.id)
    if not res:
        if err == "game error":
            return 
        if err == "num players error":
            return await update.message.reply_text("not enough players")
        else:
            return await update.message.reply_text("game error game aborted")

    context.bot_data.setdefault(curr_player_id, deque()).append(update.effective_chat.id)
    curr_player = await context.bot.get_chat_member(chat_id=update.effective_chat.id, user_id=curr_player_id)
    curr_player = curr_player.user

    await update.message.reply_text(f"game started the curr player is {curr_player.mention_html()} send your the player and hints separated by comma ',' and the hints separated by a dash '-'",
                                    parse_mode=telegram.constants.ParseMode.HTML)

async def handle_test_guess_the_player_start_round(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("private")
    if not update.message or not update.message.text or not update.effective_user or not update.effective_chat or update.effective_chat.type != "private":
        return

    chat_id_list = context.bot_data.get(update.effective_user.id, None)
    print("chat list found", chat_id_list)
    if chat_id_list == None or len(chat_id_list) == 0:
        return

    print("chat list found", chat_id_list)
    chat_id = chat_id_list.pop()
    print("chat id", chat_id)

    text = update.message.text.lower().split(",")
    if len(text) != 2:
        return await update.message.reply_text("must provide the player and hints separated by comma ','")

    res, err, curr_hints = start_round_guess_the_player(chat_id, update.effective_user.id, text[1].split("-"), text[0])
    if not res:
        if err == "game error":
            return await update.message.reply_text(err)
        if err == "empty inputs":
            return await update.message.reply_text("must provide the player and hints separated by comma ','")
        if err == "num hints error":
            return await update.message.reply_text("must provide 3 hints separeated by dash '-'")
        if err == "curr player error":
            return await update.message.reply_text(err)
        else:
            context.bot_data[update.effective_user.id].remove(chat_id)
            return await update.message.reply_text("game error game aborted")

    text = "\n".join([f"{index}. {hint}" for index, hint in enumerate(curr_hints, start=1)])
    await context.bot.send_message(text=f"the curr hints are\n{text}\n every player has 3 questions and 2 tries\nuse /answer_player_guess_the_player followed by the player", chat_id=chat_id)

async def handle_test_guess_the_player_ask_question_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_chat or not update.effective_user or not context.job_queue or not update.message.text:
        return

    res, err, curr_player_id = ask_question_guess_the_player(update.effective_chat.id, update.effective_user.id,
                                             update.message.text.replace("/ask_q_guess_the_player", "").lower().strip())
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
            return await update.message.reply_text(err)
    
    curr_player = await update.effective_chat.get_member(user_id=curr_player_id)
    curr_player = curr_player.user

    await update.message.reply_text(f"{curr_player.mention_html()} answer the question by replying to the qeustion", parse_mode=telegram.constants.ParseMode.HTML)

async def handle_test_guess_the_player_answer_question_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.reply_to_message or not update.message.reply_to_message.from_user or not update.message.text or not update.effective_chat or not update.effective_user or not context.job_queue or not update.message.reply_to_message.text:
        return

    res, err = answer_question_guess_the_player(update.effective_chat.id, update.effective_user.id,
                                                update.message.reply_to_message.from_user.id,
                                                update.message.reply_to_message.text.replace("/ask_q_guess_the_player", ""),
                                                update.message.text)
    if not res:
        if err == "game error":
            return await update.message.reply_text(err)
        if err == "curr player error":
            return print("is not curr player")
        if err == "player is not the asking error":
            return print("player is not asking")
        if err == "no asking player error":
            return print("there is not question")
        if err == "not the question":
            return await update.message.reply_text(err)
        else:
            return await update.message.reply_text("game error game aborted")

    await update.message.reply_text("a quesiton has been detucted")

async def handle_test_guess_the_player_proccess_answer_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("proccessa answer")
    if update.effective_chat.type == "private":
        return await handle_test_guess_the_player_start_round(update, context)
    if not update.message or not update.message.text or not update.effective_chat or not update.effective_user or not context.job_queue:
        return

    res, err = proccess_answer_guess_the_player(update.effective_chat.id, update.effective_user.id,
                                                update.message.text.replace("/answer_player_guess_the_player", "").lower().strip())
    if not res:
        if err == "game error":
            return 
        if err == "curr player error":
            return
        if err == "muted player":
            return
        else:
            return await update.message.reply_text(err)
    
    if err == "false":
        return await update.message.reply_text("the answer is wrong")
    if err == "correct":
        context.job_queue.run_once(handle_test_guess_the_player_end_round_job, when=0, chat_id=update.effective_chat.id)
        return await update.message.reply_text("your answer is correct")
    if err == "all players muted":
        context.job_queue.run_once(handle_test_guess_the_player_end_round_job, when=0, chat_id=update.effective_chat.id)
        return await update.message.reply_text("you have lost")
    else:
        return await update.message.reply_text(err)

async def handle_test_guess_the_player_end_round_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not context.job_queue:
        return

    res, err, curr_player_id = end_round_guess_the_player(context.job.chat_id)
    if not res:
        if err == "game error":
            return await context.bot.send_message(text=err, chat_id=context.job.chat_id, parse_mode=telegram.constants.ParseMode.HTML)
        else:
            return await context.bot.send_message(text=err, chat_id=context.job.chat_id, parse_mode=telegram.constants.ParseMode.HTML)

    if err == "game end":
        context.job_queue.run_once(handle_test_guess_the_player_end_game_job, when=0, chat_id=context.job.chat_id)
        return await context.bot.send_message(text="the game has ended the results will come now", chat_id=context.job.chat_id)
    if err == "round end":
        curr_player = await context.bot.get_chat_member(chat_id=context.job.chat_id, user_id=curr_player_id)
        curr_player = curr_player.user

        context.bot_data.setdefault(curr_player_id, deque()).append(context.job.chat_id)
        await context.bot.send_message(text=f"gane started the curr player is {curr_player.mention_html()} send your the player and hints separated by comma ',' and the hints separated by a dash '-'",
                                       chat_id=context.job.chat_id, parse_mode=telegram.constants.ParseMode.HTML)
    else:
        return await context.bot.send_message(text=err, chat_id=context.job.chat_id)

async def handle_test_guess_the_player_end_game_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not context.job_queue:
        return

    res, err, scores, winners = end_game_guess_the_player(context.job.chat_id)
    if not res:
        return await context.bot.send_message(text=err, chat_id=context.job.chat_id, parse_mode=telegram.constants.ParseMode.HTML)

    text = ""
    winners_text = ""
    for player_id, score in scores.items():
        player = await context.bot.get_chat_member(chat_id=context.job.chat_id, user_id=player_id)
        text += f"{player.user.mention_html()}:{score}\n"

    for player_id in winners:
        print(player_id)
        player = await context.bot.get_chat_member(chat_id=context.job.chat_id, user_id=player_id)
        winners_text += f"{player.user.mention_html()}\n"

    return await context.bot.send_message(text=f"scores:\n{text}\nwinners:\n{winners_text}", chat_id=context.job.chat_id, parse_mode=telegram.constants.ParseMode.HTML)

async def handle_dispatch_messages(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("dispatch")
    if not update.message or not update.message.text or not update.effective_chat or not update.effective_user:
        return

    if update.effective_chat.type == "private":
        print("private")
        return await handle_test_guess_the_player_start_round(update, context)
    if update.message.reply_to_message:
        print("is reply")
        return await handle_test_guess_the_player_answer_question_command(update, context)
    else:
        print("else")
        return await handle_test_guess_the_player_proccess_answer_command(update, context)

async def handle_test_guess_the_player_leave_game(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or not update.effective_user or not context.job_queue:
        return

    res, err, curr_player_id = leave_game_guess_the_player(update.effective_chat.id, update.effective_user.id)
    if not res:
        if err == "player not in game error":
            return
        if err == "end round":
            context.job_queue.run_once(handle_test_guess_the_player_end_round_job, when=0, chat_id=update.effective_chat.id)
        if err == "end game":
            context.job_queue.run_once(handle_test_guess_the_player_end_game_job, when=0, chat_id=update.effective_chat.id)
        else:
            return await update.message.reply_text(err)

    try:
        context.bot_data.setdefault(curr_player_id, deque()).remove(update.effective_chat.id)
    except:
        pass

    await update.message.reply_text(f"player {update.effective_user.mention_html()} left the game", parse_mode=telegram.constants.ParseMode.HTML)

async def handle_test_guess_the_player_cancel_game(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    res, err = cancel_game_guess_the_player(update.effective_chat.id)
    if not res:
        await update.message.reply_text(err)

    #remove from user games
    remove_jobs("guess_the_player_reapting_join_job", context)
    remove_jobs("guess_the_player_start_game_job", context)
    remove_jobs("guess_the_player_end_round_job", context)
    remove_jobs("guess_the_player_end_game_job", context)
    await update.message.reply_text("game cancel")

async def handle_test_guess_the_player_get_questions(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    res, err, questions = get_asked_questions_guess_the_player(update.effective_chat.id)
    if not res:
        return await update.message.reply_text(err)

    text = ""
    for q, a in questions.items():
        text += f"q-{q}:{a}\n"

    await update.message.reply_text(f"the questions are\n{text}")


guess_the_player_new_game_command_handler = CommandHandler("new_guess_the_player", handle_test_guess_the_player_new_game)
guess_the_player_join_game_command_handler = CommandHandler("join_guess_the_player", handle_test_guess_the_player_join_command)
guess_the_player_start_game_command_handler = CommandHandler("start_game_guess_the_player", handle_test_guess_the_player_start_game_command)
guess_the_player_ask_question_command_handler = CommandHandler("ask_q_guess_the_player", handle_test_guess_the_player_ask_question_command)
guess_the_player_dispatch_handler = MessageHandler((telegram.ext.filters.TEXT & ~ telegram.ext.filters.COMMAND), handle_dispatch_messages)
#guess_the_player_proccess_answer_command_handler = MessageHandler((telegram.ext.filters.TEXT & ~ telegram.ext.filters.COMMAND), handle_guess_the_player_proccess_answer_command)
guess_the_player_leave_game_command_handler = CommandHandler("leave_game_guess_the_player", handle_test_guess_the_player_leave_game)
guess_the_player_cancel_game_command_handler = CommandHandler("cancel_guess_the_player", handle_test_guess_the_player_cancel_game)
guess_thE_player_get_questions_command_handler = CommandHandler("get_questions_guess_the_player", handle_test_guess_the_player_get_questions)
#guess_the_player_start_round_command_handler = MessageHandler((telegram.ext.filters.TEXT & ~telegram.ext.filters.REPLY &~ telegram.ext.filters.COMMAND),
          #                                                   handle_guess_the_player_start_round)
guess_the_player_join_game_callback_handler = CallbackQueryHandler(handle_test_guess_the_player_join_game_callback, pattern="^guess_the_player_join$")
