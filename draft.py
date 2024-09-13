import telegram
from telegram._inline.inlinekeyboardbutton import InlineKeyboardButton
from telegram._inline.inlinekeyboardmarkup import InlineKeyboardMarkup
import telegram.ext
from datetime import datetime, timedelta
from telegram.ext._handlers.callbackqueryhandler import CallbackQueryHandler
from telegram.ext._handlers.commandhandler import CommandHandler
from telegram.ext._handlers.messagehandler import MessageHandler
from telegram.ext._handlers.pollanswerhandler import PollAnswerHandler
from shared import GuessThePlayer, Wilty, games, Draft, remove_jobs

def format_teams(teams:list[tuple[telegram.User, dict[str, str]]], formations:dict[str, str]):
    text = ""
    for player, team in teams:
        players_list = [f"{formations[pos]}:{name}\n" for pos, name in team.items()]
        players_list = "".join(players_list)
        text += f"{player.mention_html()}\n{players_list}"
    return text

async def handle_draft_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or not context.job_queue:
        return

    if update.effective_chat.id in games:
        return await update.message.reply_text("a game has already started")

    games[update.effective_chat.id] = Draft()

    data = {"game_id":update.effective_chat.id, "time":datetime.now()}
    context.job_queue.run_repeating(handle_draft_reapting_join_job, interval=20, first=10, data=data, chat_id=update.effective_chat.id, name="draft_reapting_join_job")
    context.job_queue.run_once(handle_draft_start_game_job, when=60, data=data, chat_id=update.effective_chat.id, name="draft_start_game_job")
    await update.message.reply_text(text="a game has started /draft_join or press the button", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="join game", callback_data="draft_join")]
        ]
    ))

async def handle_draft_reapting_join_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    game:Draft | GuessThePlayer | Wilty | None = games.get(context.job.data["game_id"], None)
    if not game or not isinstance(game, Draft) or game.state!= 0:
        return

    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to join\n use /join_draft to join the game\n or /start_draft to start game: {round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )

async def handle_draft_start_game_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    game:Draft | GuessThePlayer | Wilty | None = games.get(context.job.data["game_id"], None)
    if not game or not isinstance(game, Draft) or game.state!= 0:
        return
    
    remove_jobs("draft_reapting_join_job", context)
    res = game.start_game()
    if not res:
        del games[context.job.data["game_id"]]
        return await context.bot.send_message(text="not enougp players joined", chat_id=context.job.chat_id)

    data = {"game_id":context.job.chat_id, "time":datetime.now()}
    context.job_queue.run_repeating(handle_draft_reapting_statement_job, interval=20, first=10, data=data, chat_id=context.job.chat_id, name="draft_reapting_statement_job")
    context.job_queue.run_once(handle_draft_set_state_command_job, when=60, data=data, chat_id=context.job.chat_id, name="draft_set_state_command_job")
    
    await context.bot.send_message(text=f"the game has started decide the category, teams and formations\n then the admin should send as /set_draft_state category, teams,teams should be separated by - and the number of teams must be {11 + game.num_players} formations in that order with commas\n supported formations are 442 443 4231 352 532 in this foramt",
                                   chat_id=context.job.chat_id)
    

async def handle_draft_join_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    game:Draft | GuessThePlayer | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await update.message.reply_text("there is no game please start one first /new_draft")
    if not isinstance(game, Draft):
        return await update.message.reply_text("there is a game of differant type running")

    res = game.join_game(player=update.effective_user)
    if not res:
        return await update.message.reply_text("player has already joined game")

    await update.message.reply_text(f"player {update.effective_user.mention_html()} has joined the game", parse_mode=telegram.constants.ParseMode.HTML)
    
async def handle_draft_join_callback(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("here")
    if not update.callback_query or not update.effective_chat or not update.effective_user:
        return

    q = update.callback_query
    await q.answer()

    game:Draft | GuessThePlayer | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await context.bot.send_message(text=f"{update.effective_user.mention_html()} there is no game please start one first /new_draft",
                                              chat_id=update.effective_chat.id, parse_mode=telegram.constants.ParseMode.HTML)
    if not isinstance(game, Draft):
        return

    res = game.join_game(player=update.effective_user)
    if not res:
        return await context.bot.send_message(text=f"player {update.effective_user.mention_html()} has already joined game",
                                              chat_id=update.effective_chat.id, parse_mode=telegram.constants.ParseMode.HTML)

    await context.bot.send_message(text=f"player {update.effective_user.mention_html()} has joined the game",
                                   chat_id=update.effective_chat.id, parse_mode=telegram.constants.ParseMode.HTML)

async def handle_draft_start_game_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or not context.job_queue:
        return

    game:Draft | GuessThePlayer | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await update.message.reply_text("there is no game please start one first /new_draft")
    if not isinstance(game, Draft):
        return await update.message.reply_text("there is a game of differant type running")

    res = game.start_game()
    if not res:
        del games[update.effective_chat.id]
        return await update.message.reply_text("cant start game with less than two players start new game /new_draft")

    data = {"game_id":update.effective_chat.id, "time":datetime.now()}
    context.job_queue.run_repeating(handle_draft_reapting_statement_job, interval=20, first=10, data=data, chat_id=update.effective_chat.id, name="draft_reapting_statement_job")
    context.job_queue.run_once(handle_draft_set_state_command_job, when=30, data=data, chat_id=update.effective_chat.id, name="draft_set_state_command_job")

    await update.message.reply_text(f"the game has started decide the category, teams and formations\n then the admin should send as /set_draft_state category, teams,teams should be separated by - and the number of teams must be {11 + game.num_players} formations in that order with commas\n supported formations are 442 443 4231 352 532 in this foramt")

async def handle_draft_reapting_statement_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("reapting statement")
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    print("if passed")
    game:Draft | GuessThePlayer | Wilty | None = games.get(context.job.data["game_id"], None)
    if not game or not isinstance(game, Draft) or game.state != 1:
        return

    print("found game")
    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to decide statements: {round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )

async def handle_draft_set_state_command_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("set state jon")
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    remove_jobs("draft_reapting_statement_job", context)
    game:Draft | GuessThePlayer | Wilty | None = games.get(context.job.data["game_id"], None)
    if not game or not isinstance(game, Draft) or game.state != 1:
        return

    await context.bot.send_message(chat_id=context.job.chat_id, text=f"the admin should send the state as /set_draft_state category, teams,teams should be separated by - and the number of teams must be {11 + game.num_players} formations in that order with commas\n supported formations are 442 443 4231 352 532 in this foramt")

async def handle_draft_set_state_command(update: telegram.Update, context:telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_chat or not update.effective_user:
        return
    administrators = await context.bot.get_chat_administrators(update.effective_chat.id)
    admins_list = [admin.user.id for admin in administrators]
    if not update.effective_user.id in admins_list:
        return

    game:Draft | GuessThePlayer | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await update.message.reply_text("there is no game please start one first /new_draft")
    if not isinstance(game, Draft):
        return await update.message.reply_text("there is a game of differant type running")

    text = update.message.text.lower().replace("/set_draft_state", "").split(",")
    if len(text) != 3:
        return await update.message.reply_text("there is something missing")

    res, err = game.set_game_states(category=text[0].strip(), teams=text[1].split("-"), formation=text[2].strip())
    if not res:
        if err == "game error":
            del games[update.effective_chat.id]
            return await update.message.reply_text("err happend game aported")
        if err == "no category error":
            return await update.message.reply_text("no category provided")
        if err == "num of teams error":
            return await update.message.reply_text(f"number of teams must be {11 + game.num_players}")
        if err == "formation error":
            return await update.message.reply_text("formation must be 442 or 443 or 4231 or 352 or 523 written like this")
        if err == "duplicate teams error":
            return await update.message.reply_text("the teams must be with no duplicates")

    joined_games = "\n".join(game.teams)
    await update.message.reply_text(f"the category is {game.category} the formation is {game.formation[0]} the availabe teams are f{joined_games}",
                                    parse_mode=telegram.constants.ParseMode.HTML)
    return await update.message.reply_text(f"player {game.players[game.players_ids[game.start_player_idx]][0].mention_html()} press the button to pick team",
                                           parse_mode=telegram.constants.ParseMode.HTML,
                                           reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton(text="pick team", callback_data="draft_random_team")]
                                           ]))

async def handle_draft_pick_team_callback(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.callback_query or not update.effective_chat or not update.effective_user:
        return

    q = update.callback_query
    await q.answer()
    
    game:Draft | GuessThePlayer | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None or not isinstance(game, Draft):
        return

    res = game.rand_team(update.effective_user.id)
    if res == "":
        return 

    await context.bot.send_message(text=f"the team is {res} now choose your {game.formation[1][game.curr_pos]}", chat_id=update.effective_chat.id)

async def handle_draft_add_pos(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("add pos")
    if not update.message or not update.message.text or not update.effective_user or not update.effective_chat or not context.job_queue:
        return

    print("if passed")
    game:Draft | GuessThePlayer | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return 
    if not isinstance(game, Draft):
        return

    print("game found")
    if game.players_ids[game.curr_player_idx] != update.effective_user.id:
        return

    print("is curr player")
    res, status = game.add_pos_to_team(player=update.effective_user, added_player=update.message.text.lower().strip())
    if not res:
        if status == "game_error":
            del games[update.effective_chat.id]
            return await update.message.reply_text("an error happend game aported")
        elif status == "picked_pos_error":
            return await update.message.reply_text("player has already picked this position")
        elif status == "curr_player_error":
            return
        elif status == "picked_team_error":
            return await update.message.reply_text("this team has already passed")
        elif status == "taken_player_error":
            return await update.message.reply_text("this player is taken")
        else:
            del games[update.effective_chat.id]
            return await update.message.reply_text("an error happend game aported")
    if status == "new_pos":
        return await update.message.reply_text(f"player {game.players[game.players_ids[game.start_player_idx]][0].mention_html()} press the button to pick team",
                                               parse_mode=telegram.constants.ParseMode.HTML,
                                               reply_markup=InlineKeyboardMarkup([
                                                    [InlineKeyboardButton(text="pick team", callback_data="draft_random_team")]
                                               ]))
    elif status == "same_pos":
        return await update.message.reply_text(f"player {game.players[game.players_ids[game.curr_player_idx]][0].mention_html()} choose your player for {game.formation[1][game.curr_pos]}", parse_mode=telegram.constants.ParseMode.HTML)
    elif status == "end_game":
        data = {"game_id":update.effective_chat.id, "time":datetime.now()}
        context.job_queue.run_repeating(handle_draft_reapting_votes_job, interval=20, first=10, data=data, chat_id=update.effective_chat.id, name="draft_reapting_votes_job")
        context.job_queue.run_once(handle_draft_set_votes_job, when=30, data=data, chat_id=update.effective_chat.id, name="draft_set_votes_job")
        teams = [(player[0], player[1]) for player in game.players.values()]
        teams = format_teams(teams, game.formation[1])
        await context.bot.send_message(text=f"the teams\n{teams}", chat_id=update.effective_chat.id, parse_mode=telegram.constants.ParseMode.HTML)
        await context.bot.send_message(text="the drafting has ended discuss the teams for 3 minutes then vote for the best", chat_id=update.effective_chat.id)
        return
    else:
        del games[update.effective_chat.id]
        return await update.message.reply_text("an error happend game aported")

async def handle_draft_reapting_votes_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("repeating vote")
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    print("passed if")
    game:Draft | GuessThePlayer | Wilty | None = games.get(context.job.data["game_id"], None)
    if not game or not isinstance(game, Draft) or game.state != 3:
        return

    print("found game")
    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to decide: {round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )

async def handle_draft_set_votes_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("set votes")
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    print("if passed")
    remove_jobs("draft_reapting_votes_job", context)
    chat_id = context.job.data["game_id"]
    game:Draft | GuessThePlayer | Wilty | None = games.get(chat_id, None)
    if not game or not isinstance(game, Draft) or game.state != 3:
        return

    print("found game")
    poll_data = {
        "chat_id":chat_id,
        "questions":[player[0].full_name for player in game.players.values()],
        "votes_count":{player[0].full_name:0 for player in game.players.values()},
        "answers":0
    }
    message = await context.bot.send_poll(question="you has the best team" ,options=poll_data["questions"], chat_id=chat_id,
                                is_anonymous=False, allows_multiple_answers=False)

    poll_data["message_id"] = message.message_id
    context.bot_data[f"poll_{message.poll.id}"] = poll_data
    context.bot_data[f"poll_{chat_id}"] = poll_data
    print(context.bot_data)
    data = {"game_id":chat_id, "time":datetime.now(), "poll_id":message.poll.id}
    context.job_queue.run_repeating(handle_draft_reapting_votes_end_job, interval=20, first=10, data=data, chat_id=chat_id, name="draft_reapting_votes_end_job")
    context.job_queue.run_once(handle_draft_end_votes_job, when=30, data=data, chat_id=chat_id ,name="draft_end_votes_job")

async def handle_draft_reapting_votes_end_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    game:Draft | GuessThePlayer | Wilty | None = games.get(context.job.data["game_id"], None)
    if not game or not isinstance(game, Draft) or game.state != 3:
        return

    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to vote: {round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )

async def handle_draft_vote_recive(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("recive vote")
    print(update.poll_answer)
    print(context.job_queue)
    if not update.poll_answer or not context.job_queue:
        return

    print("if passed")
    answer = update.poll_answer
    poll_data = context.bot_data[f"poll_{answer.poll_id}"]
    chat_id = poll_data["chat_id"]
    game:Draft | GuessThePlayer | Wilty | None = games.get(chat_id, None)
    if game == None:
        return 
    if not isinstance(game, Draft):
        return

    print("game found")
    try:
        questions = poll_data["questions"]
    except KeyError:
        return

    print("qustion found")
    poll_data["votes_count"][questions[answer.option_ids[0]]] += 1 
    poll_data["answers"] += 1

    print("answer added")
    print(poll_data["answers"])
    if poll_data["answers"] == game.num_players:
        print("end game")
        votes = poll_data["votes_count"]
        del context.bot_data[f"poll_{answer.poll_id}"]
        remove_jobs("draft_reapting_votes_job", context)
        remove_jobs("draft_end_votes_job", context)
        await context.bot.stop_poll(chat_id=chat_id, message_id=poll_data["message_id"])
        data = {"game_id":chat_id, "time":datetime.now(), "votes":votes}
        context.job_queue.run_once(handle_draft_end_game_job, when=0, data=data, chat_id=chat_id ,name="draft_end_game_job")
    

async def handle_draft_start_votes_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_user or not update.effective_chat or not context.job_queue:
        return
    
    chat_id = update.effective_chat.id
    game:Draft | GuessThePlayer | Wilty | None = games.get(chat_id, None)
    if not game or not isinstance(game, Draft) or game.state != 3:
        return

    print("found game")
    poll_data = {
        "chat_id":chat_id,
        "questions":[player[0].full_name for player in game.players.values()],
        "votes_count":{player[0].full_name:0 for player in game.players.values()},
        "answers":0
    }
    message = await context.bot.send_poll(question="you has the best team" ,options=poll_data["questions"], chat_id=chat_id,
                                is_anonymous=False, allows_multiple_answers=False)

    poll_data["message_id"] = message.message_id
    context.bot_data[f"poll_{message.poll.id}"] = poll_data
    context.bot_data[f"poll_{chat_id}"] = poll_data
    data = {"game_id":chat_id, "time":datetime.now(), "poll_id":message.poll.id}

    remove_jobs("draft_reapting_votes_job", context)
    remove_jobs("draft_reapting_votes_end_job", context)
    
    context.job_queue.run_once(handle_draft_end_votes_job, when=30, data=data, chat_id=chat_id ,name="draft_end_votes_job")

async def handle_draft_end_votes_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_user or not update.effective_chat or not context.job_queue:
        return
    
    game:Draft | GuessThePlayer | Wilty | None = games.get(update.effective_chat.id, None)
    if not game or not isinstance(game, Draft):
        return

    remove_jobs("draft_reapting_votes_job", context)
    remove_jobs("draft_reapting_votes_end_job", context)
    
    print(context.bot_data)
    poll_data = context.bot_data[f"poll_{update.effective_chat.id}"]
    chat_id = poll_data["chat_id"]

    votes = poll_data["votes_count"]
    del context.bot_data[f"poll_{update.effective_chat.id}"]
    await context.bot.stop_poll(chat_id=chat_id, message_id=poll_data["message_id"])
    data = {"game_id":chat_id, "time":datetime.now(), "votes":votes}
    context.job_queue.run_once(handle_draft_end_game_job, when=0, data=data, chat_id=chat_id ,name="draft_end_game_job")

async def handle_draft_end_votes_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    remove_jobs("draft_reapting_votes_job", context)
    remove_jobs("draft_reapting_votes_end_job", context)
    chat_id = context.job.data["game_id"]
    game:Draft | GuessThePlayer | Wilty | None = games.get(chat_id, None)
    if not game or not isinstance(game, Draft):
        return
    
    poll_id = context.job.data["poll_id"]
    poll_data = context.bot_data[f"poll_{poll_id}"]
    chat_id = poll_data["chat_id"]


    votes = poll_data["votes_count"]
    del context.bot_data[f"poll_{poll_id}"]
    await context.bot.stop_poll(chat_id=chat_id, message_id=poll_data["message_id"])
    data = {"game_id":chat_id, "time":datetime.now(), "votes":votes}
    context.job_queue.run_once(handle_draft_end_game_job, when=0, data=data, chat_id=chat_id ,name="draft_end_game_job")


async def handle_draft_end_game_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("draft end game")
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    print("if passed")
    remove_jobs("draft_reapting_votes_job", context)
    remove_jobs("draft_reapting_votes_end_job", context)
    chat_id = context.job.data["game_id"]
    game:Draft | GuessThePlayer | Wilty | None = games.get(chat_id, None)
    if game == None or not isinstance(game, Draft) or game.state != 3:
        return

    print("found game")
    try:
        votes = context.job.data["votes"]
    except KeyError:
        print("coundt find votes")
        return

    username_to_id = {player[0].full_name:id for id, player in game.players.items()}
    votes = {username_to_id[username]:count for username, count in votes.items()}

    print("found votes")
    winners = game.end_game(votes=votes)
    winners_text = ""
    teams = []
    for winner in winners:
        winners_text += f"{winner[0].mention_html()}\n"
        teams.append((winner[0], winner[1]))
    teams = format_teams(teams, game.formation[1])
    await context.bot.send_message(text=f"the winners are {winners_text}\n the teams\n{teams}", chat_id=context.job.chat_id, parse_mode=telegram.constants.ParseMode.HTML)

async def handle_draft_cancel_game(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message:
        return

    game:Draft | GuessThePlayer | Wilty | None = games.get(update.effective_chat.id, None)
    if game == None:
        return await update.message.reply_text("there is no game please start one first /new_draft")
    if not isinstance(game, Draft):
        return await update.message.reply_text("there is a game of differant type running")

    remove_jobs("draft_reapting_votes_job", context)
    remove_jobs("draft_reapting_end_votes_job", context)
    remove_jobs("draft_end_votes_job", context)
    remove_jobs("draft_set_votes_job", context)
    remove_jobs("draft_reapting_join_job", context)
    remove_jobs("draft_start_game_job", context)
    remove_jobs("draft_reapting_statement_job", context)
    remove_jobs("draft_set_statement_command_job", context)
    del games[update.effective_chat.id]

    await update.message.reply_text("game has been canceled")

new_draft_game_command_handler = CommandHandler("new_draft", handle_draft_command)
join_draft_game_command_handler = CommandHandler("draft_join", handle_draft_join_command)
start_draft_game_command_handler = CommandHandler("start_draft", handle_draft_start_game_command)
set_draft_game_state_command_handler = CommandHandler("set_draft_state", handle_draft_set_state_command)
cancel_draft_game_command_handler = CommandHandler("cancel_draft", handle_draft_cancel_game)
end_vote_draft_game_command_handler = CommandHandler("draft_end_vote", handle_draft_end_votes_command)
start_vote_draft_game_command_handler = CommandHandler("draft_start_vote", handle_draft_start_votes_command)
position_draft_message_handler = MessageHandler((telegram.ext.filters.TEXT & ~telegram.ext.filters.COMMAND), handle_draft_add_pos)
vote_recive_poll_answer_handler = PollAnswerHandler(handle_draft_vote_recive)
join_draft_game_callback_handler = CallbackQueryHandler(callback=handle_draft_join_callback, pattern="^draft_join$")
random_team_draft_game_callback_handler = CallbackQueryHandler(callback=handle_draft_pick_team_callback, pattern="^draft_random_team$")
