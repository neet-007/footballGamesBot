import telegram
from telegram._inline.inlinekeyboardbutton import InlineKeyboardButton
from telegram._inline.inlinekeyboardmarkup import InlineKeyboardMarkup
import telegram.ext
from datetime import datetime, timedelta
from telegram.ext._handlers.callbackqueryhandler import CallbackQueryHandler
from telegram.ext._handlers.commandhandler import CommandHandler
from telegram.ext._handlers.messagehandler import MessageHandler
from telegram.ext._handlers.pollanswerhandler import PollAnswerHandler
from shared import FORMATIONS, add_pos_to_team_draft, cancel_game_draft, check_draft, end_game_draft, games, get_vote_data, join_game_draft, new_game_draft, rand_team_draft, remove_jobs, session, set_game_states_draft, start_game_draft

def format_teams(teams:list[tuple[telegram.User, dict[str, str]]], formations:dict[str, str]):
    text = ""
    for player, team in teams:
        players_list = [f"{formations[pos]}:{name}\n" for pos, name in team.items()]
        players_list = "".join(players_list)
        text += f"{player.mention_html()}\n{players_list}"
    return text

async def handle_test_make_game(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.effective_user or not update.message or not context.job_queue:
        return

    res, err = new_game_draft(update.effective_chat.id, session)
    if not res:
        return await update.message.reply_text(err)

    data = {"game_id":update.effective_chat.id, "time":datetime.now()}
    context.job_queue.run_repeating(handle_test_draft_reapting_join_job, interval=20, first=10, data=data, chat_id=update.effective_chat.id, name="draft_reapting_join_job")
    context.job_queue.run_once(handle_test_draft_start_game_job, when=60, data=data, chat_id=update.effective_chat.id, name="draft_start_game_job")
    await update.message.reply_text(text="a game has started /test_join or press the button", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="join game", callback_data="draft_join")]
        ]
    ))

async def handle_test_draft_reapting_join_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("repintg")
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    print("testeint res")
    res, state, _ = check_draft(context.job.chat_id)
    if not res or state!= 0:
        return
    print("send message")

    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to join\n use /test_join to join the game\n or /test_start to start game: {round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )

async def handle_test_draft_start_game_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    remove_jobs("draft_reapting_join_job", context)
    res, err, num_players = start_game_draft(context.job.chat_id, session)
    if not res:
        return await context.bot.send_message(text=err, chat_id=context.job.chat_id)

    data = {"game_id":context.job.chat_id, "time":datetime.now()}
    context.job_queue.run_repeating(handle_draft_reapting_statement_job, interval=20, first=10, data=data, chat_id=context.job.chat_id, name="draft_reapting_statement_job")
    context.job_queue.run_once(handle_test_draft_set_state_command_job, when=60, data=data, chat_id=context.job.chat_id, name="draft_set_state_command_job")
    
    await context.bot.send_message(text=f"the game has started decide the category, teams and formations\n then the admin should send as /test_set category, teams,teams should be separated by - and the number of teams must be {11 + num_players} formations in that order with commas\n supported formations are 442 443 4231 352 532 in this foramt",
                                   chat_id=context.job.chat_id)

async def handle_test_join_game(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.effective_user or not update.message:
        return

    res, err = join_game_draft(update.effective_chat.id, update.effective_user.id, session)
    if not res:
        return await context.bot.send_message(text=f"player {update.effective_user.mention_html()} {err}",
                                              chat_id=update.effective_chat.id, parse_mode=telegram.constants.ParseMode.HTML)
    await update.message.reply_text(f"player {update.effective_user.mention_html()} has joined the game", parse_mode=telegram.constants.ParseMode.HTML)

async def handle_test_draft_join_callback(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("here")
    if not update.callback_query or not update.effective_chat or not update.effective_user:
        return

    q = update.callback_query
    await q.answer()

    res, err = join_game_draft(update.effective_chat.id, update.effective_user.id, session)
    if not res:
        return await context.bot.send_message(text=f"player {update.effective_user.mention_html()} {err}",
                                              chat_id=update.effective_chat.id, parse_mode=telegram.constants.ParseMode.HTML)

    await context.bot.send_message(text=f"player {update.effective_user.mention_html()} has joined the game",
                                   chat_id=update.effective_chat.id, parse_mode=telegram.constants.ParseMode.HTML)

async def handle_test_start_game(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.effective_user or not update.message or not context.job_queue:
        return

    res, err, num_players= start_game_draft(update.effective_chat.id, session)
    if not res:
        await update.message.reply_text(err)

    data = {"game_id":update.effective_chat.id, "time":datetime.now()}
    context.job_queue.run_repeating(handle_test_draft_reapting_statement_job, interval=20, first=10, data=data, chat_id=update.effective_chat.id, name="draft_reapting_statement_job")
    context.job_queue.run_once(handle_test_draft_set_state_command_job, when=30, data=data, chat_id=update.effective_chat.id, name="draft_set_state_command_job")

    await update.message.reply_text(f"the game has started decide the category, teams and formations\n then the admin should send as /test_set category, teams,teams should be separated by - and the number of teams must be {11 + num_players} formations in that order with commas\n supported formations are 442 443 4231 352 532 in this foramt")

async def handle_test_draft_reapting_statement_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    res, state, _ = check_draft(context.job.chat_id)
    if not res or state != 1:
        return

    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to decide statements: {round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )
 
async def handle_test_draft_set_state_command_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("set state jon")
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    remove_jobs("draft_reapting_statement_job", context)
    res, state, num_players = check_draft(context.job.chat_id)
    if not res or state != 1:
        return

    await context.bot.send_message(chat_id=context.job.chat_id, text=f"the admin should send the state as /test_set category, teams,teams should be separated by - and the number of teams must be {11 + num_players} formations in that order with commas\n supported formations are 442 443 4231 352 532 in this foramt")

async def handle_test_set_state(update: telegram.Update, context:telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_chat or not update.effective_user:
        return

    text = update.message.text.lower().replace("/test_set", "").split(",")
    if len(text) != 3:
        return await update.message.reply_text("there is something missing")

    res, err, other = set_game_states_draft(update.effective_chat.id, update.effective_user.id,
                            text[0].strip(), text[1].split("-"), text[2].strip(),
                            session)
    if not res:
        if err == "game error":
            return await update.message.reply_text("err happend game aported")
        if err == "no category error":
            return await update.message.reply_text("no category provided")
        if err == "num of teams error":
            return await update.message.reply_text("number of teams must be")
        if err == "formation error":
            return await update.message.reply_text("formation must be 442 or 443 or 4231 or 352 or 523 written like this")
        if err == "duplicate teams error":
            return await update.message.reply_text("the teams must be with no duplicates")
        else:
            return await update.message.reply_text(f"{err}{other}")

    curr_player = await update.effective_chat.get_member(other[3])
    await update.message.reply_text(f"the category is {other[0]} the formation is {other[1]} the availabe teams are f{other[2]}",
                                    parse_mode=telegram.constants.ParseMode.HTML)
    return await update.message.reply_text(f"player {curr_player.user.mention_html()} press the button to pick team",
                                           parse_mode=telegram.constants.ParseMode.HTML,
                                           reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton(text="pick team", callback_data="draft_random_team")]
                                           ]))

async def handle_test_draft_pick_team_callback(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.callback_query or not update.effective_chat or not update.effective_user:
        return

    q = update.callback_query
    await q.answer()
    
    res, team, formation, curr_pos = rand_team_draft(update.effective_chat.id, update.effective_user.id, session)
    if not res:
        print(team, formation, curr_pos)
        return 

    await context.bot.send_message(text=f"the team is {team} now choose your {FORMATIONS[formation][curr_pos]}", chat_id=update.effective_chat.id)

async def handle_test_draft_add_pos(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_user or not update.effective_chat or not context.job_queue:
        return

    res, status, other = add_pos_to_team_draft(update.effective_chat.id, update.effective_user.id,
                                        update.message.text.lower().strip(), session)
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
            return await update.message.reply_text(status)
    if status == "new_pos":
        if not other[0]:
            return await update.message.reply_text("error happend")
        start_player = await update.effective_chat.get_member(other[0])
        return await update.message.reply_text(f"player {start_player.user.mention_html()} press the button to pick team",
                                               parse_mode=telegram.constants.ParseMode.HTML,
                                               reply_markup=InlineKeyboardMarkup([
                                                    [InlineKeyboardButton(text="pick team", callback_data="draft_random_team")]
                                               ]))
    elif status == "same_pos":
        if not other[0] or not other[1] or not other[2]:
            return await update.message.reply_text("error happend")
        curr_player = await update.effective_chat.get_member(other[0])
        return await update.message.reply_text(f"player {curr_player.user.mention_html()} choose your player for {FORMATIONS[other[1]][other[2]]}", parse_mode=telegram.constants.ParseMode.HTML)
    elif status == "end_game":
        if not other[0] or not other[1] or not other[2] or not other[3]:
            return await update.message.reply_text("error happend")

        data = {"game_id":update.effective_chat.id, "time":datetime.now()}
        context.job_queue.run_repeating(handle_test_draft_reapting_votes_job, interval=20, first=10, data=data, chat_id=update.effective_chat.id, name="draft_reapting_votes_job")
        context.job_queue.run_once(handle_test_draft_set_votes_job, when=30, data=data, chat_id=update.effective_chat.id, name="draft_set_votes_job")
        teams = []
        for player_id, team in other[3]:
            player = await update.effective_chat.get_member(player_id)
            teams.append((player.user, team))

        teams = format_teams(teams, FORMATIONS[other[1]])
        await context.bot.send_message(text=f"the teams\n{teams}", chat_id=update.effective_chat.id, parse_mode=telegram.constants.ParseMode.HTML)
        await context.bot.send_message(text="the drafting has ended discuss the teams for 3 minutes then vote for the best", chat_id=update.effective_chat.id)
        return
    else:
        return await update.message.reply_text(status)

async def handle_test_draft_reapting_votes_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    res, state, _ = check_draft(context.job.chat_id)
    if not res or state != 3:
        return

    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to decide: {round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )

async def handle_test_draft_start_votes_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_user or not update.effective_chat or not context.job_queue:
        return
    
    remove_jobs("draft_reapting_votes_job", context)
    remove_jobs("draft_reapting_votes_end_job", context)
    chat_id = update.effective_chat.id
    res, state, players_ids = get_vote_data(chat_id)
    if not res or state != 3 or not players_ids:
        return

    players = []
    for id in players_ids:
        player = await context.bot.get_chat_member(chat_id, id[0])
        players.append(player.user.full_name)

    poll_data = {
        "chat_id":chat_id,
        "questions":players,
        "votes_count":{player:0 for player in players},
        "answers":0
    }
    message = await context.bot.send_poll(question="you has the best team" ,options=poll_data["questions"], chat_id=chat_id,
                                is_anonymous=False, allows_multiple_answers=False)

    poll_data["message_id"] = message.message_id
    if not message.poll:
        return

    context.bot_data[f"poll_{message.poll.id}"] = poll_data
    context.bot_data[f"poll_{chat_id}"] = poll_data
    data = {"game_id":chat_id, "time":datetime.now(), "poll_id":message.poll.id}
    context.job_queue.run_repeating(handle_test_draft_reapting_votes_end_job, interval=20, first=10, data=data, chat_id=chat_id, name="draft_reapting_votes_end_job")
    context.job_queue.run_once(handle_test_draft_end_votes_job, when=30, data=data, chat_id=chat_id ,name="draft_end_votes_job")

async def handle_test_draft_reapting_votes_end_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    res, state, _ = check_draft(context.job.chat_id)
    if not res or state != 3:
        return

    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to vote: {round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )

async def handle_test_draft_set_votes_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    remove_jobs("draft_reapting_votes_job", context)
    remove_jobs("draft_reapting_votes_end_job", context)
    chat_id = context.job.data["game_id"]
    res, state, players_ids = get_vote_data(chat_id)
    if not res or state != 3 or not players_ids:
        return

    players = []
    for id in players_ids:
        player = await context.bot.get_chat_member(chat_id, id[0])
        players.append(player.user.full_name)

    poll_data = {
        "chat_id":chat_id,
        "questions":players,
        "votes_count":{player:0 for player in players},
        "answers":0
    }
    message = await context.bot.send_poll(question="you has the best team" ,options=poll_data["questions"], chat_id=chat_id,
                                is_anonymous=False, allows_multiple_answers=False)

    poll_data["message_id"] = message.message_id
    if not message.poll:
        return

    context.bot_data[f"poll_{message.poll.id}"] = poll_data
    context.bot_data[f"poll_{chat_id}"] = poll_data
    print(context.bot_data)
    data = {"game_id":chat_id, "time":datetime.now(), "poll_id":message.poll.id}
    context.job_queue.run_repeating(handle_test_draft_reapting_votes_end_job, interval=20, first=10, data=data, chat_id=chat_id, name="draft_reapting_votes_end_job")
    context.job_queue.run_once(handle_test_draft_end_votes_job, when=30, data=data, chat_id=chat_id ,name="draft_end_votes_job")

async def handle_test_draft_vote_recive(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("here")
    if not update.poll_answer or not context.job_queue:
        return
    print("if ppadded")

    answer = update.poll_answer
    poll_data = context.bot_data[f"poll_{answer.poll_id}"]
    chat_id = poll_data["chat_id"]
    res, _, num_players = check_draft(chat_id)
    if res == None:
        return 

    try:
        questions = poll_data["questions"]
    except KeyError:
        return

    poll_data["votes_count"][questions[answer.option_ids[0]]] += 1 
    poll_data["answers"] += 1

    if poll_data["answers"] == num_players:
        remove_jobs("draft_reapting_votes_job", context)
        remove_jobs("draft_end_votes_job", context)
        #await context.bot.stop_poll(chat_id=chat_id, message_id=poll_data["message_id"])
        data = {"game_id":chat_id, "time":datetime.now(), "poll_id":update.poll_answer.poll_id}
        context.job_queue.run_once(handle_test_draft_end_votes_job, when=0, data=data, chat_id=chat_id ,name="draft_end_votes_job")

async def handle_test_draft_end_votes_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_user or not update.effective_chat or not context.job_queue:
        return
    
    remove_jobs("draft_reapting_votes_job", context)
    remove_jobs("draft_reapting_votes_end_job", context)
    poll_data = context.bot_data[f"poll_{update.effective_chat.id}"]
    chat_id = poll_data["chat_id"]

    votes = poll_data["votes_count"]
    res, players_and_teams, formation = end_game_draft(chat_id)
    if not res or not players_and_teams or not formation:
        return await context.bot.send_message(text="error happend or excpetion", chat_id=chat_id)
    
    players = []
    for id, _ in players_and_teams:
        player = await context.bot.get_chat_member(chat_id=chat_id, user_id=id)
        players.append(player.user.full_name)

    username_to_id = {players[i]:players_and_teams[i][0] for i in range(len(players))}
    votes = {username_to_id[username]:count for username, count in votes.items()}

    max_vote = float("-inf")
    max_vote_ids = []
    for id, vote_count in votes.items():
        if vote_count > max_vote:
            max_vote = vote_count
            max_vote_ids.clear()
            max_vote_ids.append((id, vote_count))
        elif vote_count == max_vote:
            max_vote_ids.append((id, vote_count))
    for i, id in enumerate(max_vote_ids):
        winner = await context.bot.get_chat_member(chat_id=chat_id, user_id=id[0])
        max_vote_ids[i] = (winner.user, players_and_teams[i][1])

    #del context.bot_data[f"poll_{poll_data['poll_id']}"]
    del context.bot_data[f"poll_{update.effective_chat.id}"]
    await context.bot.stop_poll(chat_id=chat_id, message_id=poll_data["message_id"])
    data = {"game_id":chat_id, "time":datetime.now(), "winners":max_vote_ids, "formation":FORMATIONS[formation]}
    context.job_queue.run_once(handle_test_draft_end_game_job, when=0, data=data, chat_id=chat_id ,name="draft_end_game_job")

async def handle_test_draft_end_votes_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    remove_jobs("draft_reapting_votes_job", context)
    remove_jobs("draft_reapting_votes_end_job", context)
    chat_id = context.job.data["game_id"]
    
    poll_id = context.job.data["poll_id"]
    poll_data = context.bot_data[f"poll_{poll_id}"]
    chat_id = poll_data["chat_id"]

    votes = poll_data["votes_count"]
    res, players_and_teams, formation = end_game_draft(chat_id)
    if not res or not players_and_teams or not formation:
        return await context.bot.send_message(text="error happend or excpetion", chat_id=chat_id)
    
    players = []
    for id, _ in players_and_teams:
        player = await context.bot.get_chat_member(chat_id=chat_id, user_id=id)
        players.append(player.user.full_name)

    username_to_id = {players[i]:players_and_teams[i][0] for i in range(len(players))}
    votes = {username_to_id[username]:count for username, count in votes.items()}

    max_vote = float("-inf")
    max_vote_ids = []
    for id, vote_count in votes.items():
        if vote_count > max_vote:
            max_vote = vote_count
            max_vote_ids.clear()
            max_vote_ids.append((id, vote_count))
        elif vote_count == max_vote:
            max_vote_ids.append((id, vote_count))
    for i, id in enumerate(max_vote_ids):
        winner = await context.bot.get_chat_member(chat_id=chat_id, user_id=id[0])
        max_vote_ids[i] = (winner.user, players_and_teams[i][1])

    del context.bot_data[f"poll_{poll_id}"]
    await context.bot.stop_poll(chat_id=chat_id, message_id=poll_data["message_id"])
    data = {"game_id":chat_id, "time":datetime.now(), "winners":max_vote_ids, "formation":FORMATIONS[formation]}
    context.job_queue.run_once(handle_test_draft_end_game_job, when=0, data=data, chat_id=chat_id ,name="draft_end_game_job")

async def handle_test_draft_end_game_job(context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    remove_jobs("draft_reapting_votes_job", context)
    remove_jobs("draft_reapting_votes_end_job", context)

    winners = context.job.data["winners"]
    formation = context.job.data["formation"]
    winners_text = ""
    teams = []
    for winner in winners:
        winners_text += f"{winner[0].mention_html()}\n"
        teams.append((winner[0], winner[1]))
    teams = format_teams(teams, formation)
    await context.bot.send_message(text=f"the winners are {winners_text}\n the teams\n{teams}", chat_id=context.job.chat_id, parse_mode=telegram.constants.ParseMode.HTML)

async def handle_test_draft_cancel_game(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message:
        return

    res = cancel_game_draft(update.effective_chat.id, session)
    if not res:
        return await update.message.reply_text("there is no game please start one first /new_draft")

    remove_jobs("draft_reapting_votes_job", context)
    remove_jobs("draft_reapting_end_votes_job", context)
    remove_jobs("draft_end_votes_job", context)
    remove_jobs("draft_set_votes_job", context)
    remove_jobs("draft_reapting_join_job", context)
    remove_jobs("draft_start_game_job", context)
    remove_jobs("draft_reapting_statement_job", context)
    remove_jobs("draft_set_statement_command_job", context)

    await update.message.reply_text("game has been canceled")

make_game_test_handler = CommandHandler("test_make", handle_test_make_game)
join_game_test_handler = CommandHandler("test_join", handle_test_join_game)
start_game_test_handler = CommandHandler("test_start", handle_test_start_game)
set_game_test_handler = CommandHandler("test_set", handle_test_set_state)
cancel_game_test_handler = CommandHandler("test_cancel", handle_test_draft_cancel_game)
end_vote_game_test_handler = CommandHandler("test_end_vote", handle_test_draft_end_votes_command)
start_vote_game_test_handler = CommandHandler("test_start_vote", handle_test_draft_start_votes_command)
position_draft_message_test_handler = MessageHandler((telegram.ext.filters.TEXT & ~telegram.ext.filters.COMMAND), handle_test_draft_add_pos)
vote_recive_poll_answer_test_handler = PollAnswerHandler(handle_test_draft_vote_recive)
join_game_callback_test_handler = CallbackQueryHandler(callback=handle_test_draft_join_callback, pattern="^draft_join$")
random_team_draft_game_callback_handler = CallbackQueryHandler(callback=handle_test_draft_pick_team_callback, pattern="^draft_random_team$")
