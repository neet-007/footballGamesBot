from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, User, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, filters
from telegram.ext._handlers.callbackqueryhandler import CallbackQueryHandler
from telegram.ext._handlers.commandhandler import CommandHandler
from telegram.ext._handlers.messagehandler import MessageHandler
from telegram.ext._handlers.pollanswerhandler import PollAnswerHandler

from db.connection import get_session
from games.draft_functions import FORMATIONS, add_pos_to_team_draft, cancel_game_draft, check_draft, end_game_draft, get_vote_data, join_game_draft, new_game_draft, rand_team_draft, set_game_states_draft, start_game_draft
from utils.helpers import remove_jobs

PLAYER_NOT_IN_GAME_ERROR = "player is not in game"
NO_GAME_ERROR = "there is no game in this chat \nstart one using /new_draft"
EXCEPTION_ERROR = "internal error happend please try again later"
STATE_ERROR = "game error happend\n or this is not the time for this command"

def format_teams(teams:list[tuple[User, dict[str, str]]], formations:dict[str, str]):
    text = ""
    for player, team in teams:
        players_list = [f"{formations[pos]}:{name}\n" for pos, name in team.items()]
        players_list = "".join(players_list)
        text += f"{player.mention_html()}\n{players_list}"
    return text

async def handle_test_make_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.effective_user or not update.message or not context.job_queue or update.effective_chat.type == "private":
        return

    with get_session() as session:
        res, err = new_game_draft(update.effective_chat.id, session)
    if not res:
        if err == "a game has started in this chat":
            return await update.message.reply_text("a game has started in this chat cant make a new one")
        return await update.message.reply_text(EXCEPTION_ERROR)

    data = {"game_id":update.effective_chat.id, "time":datetime.now()}
    context.job_queue.run_repeating(handle_test_draft_reapting_join_job, interval=20, first=10, data=data, chat_id=update.effective_chat.id,
                                    name=f"draft_reapting_join_job_{update.effective_chat.id}")
    context.job_queue.run_once(handle_test_draft_start_game_job, when=60, data=data, chat_id=update.effective_chat.id,
                               name=f"draft_start_game_job_{update.effective_chat.id}")
    await update.message.reply_text(text="a game has started /test_join or press the button", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="join game", callback_data="draft_join")]
        ]
    ))

async def handle_test_draft_reapting_join_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    print("====================\n", "joooooooooooooooooin repppppppppppppt", "\n====================\n")
    with get_session() as session:
        res, err, state, num_players = check_draft(context.job.chat_id, session)
    if not res:
        if err == "no game found":
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=NO_GAME_ERROR)
        return await context.bot.send_message(chat_id=context.job.chat_id,
                                              text=EXCEPTION_ERROR)
    
    if state != 0:
        return await context.bot.send_message(chat_id=context.job.chat_id,
                                              text=STATE_ERROR)

    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to join\n use /test_join to join the game\n or /test_start to start game\nnumber of players in game:{num_players}: {round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )

async def handle_test_draft_start_game_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    remove_jobs(f"draft_reapting_join_job_{context.job.chat_id}", context)
    with get_session() as session:
        res, err, num_players = start_game_draft(context.job.chat_id, session)
    if not res:
        if err == "no game":
            return await context.bot.send_message(text=NO_GAME_ERROR, chat_id=context.job.chat_id)
        if err == "state error":
            return await context.bot.send_message(text=STATE_ERROR, chat_id=context.job.chat_id)
        if err == "no players associated with the game":
            return await context.bot.send_message(text="there are no players in this game\n start a new one /new_draft", chat_id=context.job.chat_id)
        if err == "number of players is less than 2 or not as expecte…":
            return await context.bot.send_message(text="number of players less than two could not start\n start a new one /new_draft", chat_id=context.job.chat_id)
        if err == "exception":
            return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=context.job.chat_id)
        else:
            return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=context.job.chat_id)

    data = {"game_id":context.job.chat_id, "time":datetime.now()}
    context.job_queue.run_repeating(handle_test_draft_reapting_statement_job, interval=20, first=10, data=data, chat_id=context.job.chat_id,
                                    name=f"draft_reapting_statement_job_{context.job.chat_id}")
    context.job_queue.run_once(handle_test_draft_set_state_command_job, when=60, data=data, chat_id=context.job.chat_id,
                               name=f"draft_set_state_command_job_{context.job.chat_id}")
    
    await context.bot.send_message(text=f"the game has started decide the category, teams and formations\n then the admin should send as /test_set category, teams,teams should be separated by - and the number of teams must be {11 + num_players} formations in that order with commas\n supported formations are 442 443 4231 352 532 in this foramt",
                                   chat_id=context.job.chat_id)

async def handle_test_join_game(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.effective_user or not update.message or update.effective_chat.type == "private":
        return

    with get_session() as session:
        res, err = join_game_draft(update.effective_chat.id, update.effective_user.id, session)
    if not res:
        if err == "no game":
            return await update.message.reply_text(text=NO_GAME_ERROR)
        if err == "game has started":
            return await update.message.reply_text(text=EXCEPTION_ERROR)
        if err == "player already in game":
            await update.message.reply_text(f"player {update.effective_user.mention_html()} is already in game",
                                            parse_mode=ParseMode.HTML)
        if err == "exception":
            return await update.message.reply_text(text=EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(text=EXCEPTION_ERROR)

    await update.message.reply_text(f"player {update.effective_user.mention_html()} has joined the game", parse_mode=ParseMode.HTML)

async def handle_test_draft_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.callback_query or not update.effective_chat or not update.effective_user or update.effective_chat.type == "private":
        return

    q = update.callback_query
    await q.answer()

    with get_session() as session:
        res, err = join_game_draft(update.effective_chat.id, update.effective_user.id, session)
    if not res:
        if err == "no game":
            return await context.bot.send_message(text=NO_GAME_ERROR,
                                                  chat_id=update.effective_chat.id)
        if err == "game has started":
            return await context.bot.send_message(text=EXCEPTION_ERROR,
                                                  chat_id=update.effective_chat.id)
        if err == "player already in game":
            return await context.bot.send_message(text=f"player {update.effective_user.mention_html()} is already in game",
                                                  chat_id=update.effective_chat.id, parse_mode=ParseMode.HTML)
        if err == "exception":
            return await context.bot.send_message(text=EXCEPTION_ERROR,
                                                  chat_id=update.effective_chat.id)
        else:
            return await context.bot.send_message(text=EXCEPTION_ERROR,
                                                  chat_id=update.effective_chat.id)

    await context.bot.send_message(text=f"player {update.effective_user.mention_html()} has joined the game",
                                   chat_id=update.effective_chat.id, parse_mode=ParseMode.HTML)

async def handle_test_start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.effective_user or not update.message or not context.job_queue or update.effective_chat.type == "private":
        return

    remove_jobs(f"draft_reapting_join_job_{update.effective_chat.id}", context)
    remove_jobs(f"draft_start_game_job_{update.effective_chat.id}", context)
    with get_session() as session:
        res, err, num_players= start_game_draft(update.effective_chat.id, session)
    if not res:
        if err == "no game":
            return await update.message.reply_text(text=NO_GAME_ERROR)
        if err == "state error":
            return await update.message.reply_text(text=STATE_ERROR)
        if err == "no players associated with the game":
            return await update.message.reply_text(text="there are no players in this game\n start a new one /new_draft")
        if err == "number of players is less than 2 or not as expecte…":
            return await update.message.reply_text(text="number of players less than two could not start\n start a new one /new_draft")
        if err == "exception":
            return await update.message.reply_text(text=EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(text=EXCEPTION_ERROR)

    data = {"game_id":update.effective_chat.id, "time":datetime.now()}
    context.job_queue.run_repeating(handle_test_draft_reapting_statement_job, interval=20, first=10, data=data, chat_id=update.effective_chat.id,
                                    name=f"draft_reapting_statement_job_{update.effective_chat.id}")
    context.job_queue.run_once(handle_test_draft_set_state_command_job, when=30, data=data, chat_id=update.effective_chat.id,
                               name=f"draft_set_state_command_job_{update.effective_chat.id}")

    await update.message.reply_text(f"the game has started decide the category, teams and formations\n then the admin should send as /test_set category, teams,teams should be separated by - and the number of teams must be {11 + num_players} formations in that order with commas\n supported formations are 442 443 4231 352 532 in this foramt")

async def handle_test_draft_reapting_statement_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    with get_session() as session:
        res, err,  state, _ = check_draft(context.job.chat_id, session)
    if not res:
        if err == "no game found":
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=NO_GAME_ERROR)
        return await context.bot.send_message(chat_id=context.job.chat_id,
                                              text=EXCEPTION_ERROR)

    if state != 1:
        return await context.bot.send_message(chat_id=context.job.chat_id,
                                              text=STATE_ERROR)
    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to decide statements: {round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )
 
async def handle_test_draft_set_state_command_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    remove_jobs(f"draft_reapting_statement_job_{context.job.chat_id}", context)
    with get_session() as session:
        res, err,  state, num_players = check_draft(context.job.chat_id, session)
    if not res:
        if err == "no game found":
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=NO_GAME_ERROR)
        return await context.bot.send_message(chat_id=context.job.chat_id,
                                              text=EXCEPTION_ERROR)

    if state != 1:
        return await context.bot.send_message(chat_id=context.job.chat_id,
                                              text=STATE_ERROR)

    await context.bot.send_message(chat_id=context.job.chat_id, text=f"the admin should send the state as /test_set category, teams,teams should be separated by - and the number of teams must be {11 + num_players} formations in that order with commas\n supported formations are 442 443 4231 352 532 in this foramt")

async def handle_test_set_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_chat or not update.effective_user or update.effective_chat.type == "private":
        return

    remove_jobs(f"draft_reapting_statement_job_{update.effective_chat.id}", context)
    remove_jobs(f"draft_set_state_command_job_{update.effective_chat.id}", context)
    text = update.message.text.lower().replace("/test_set", "").split(",")
    if len(text) != 3:
        return await update.message.reply_text("there is something missing")

    with get_session() as session:
        res, err, other = set_game_states_draft(update.effective_chat.id, update.effective_user.id,
                                text[0].strip(), text[1].split("-"), text[2].strip(), session)
    if not res:
        if err == "game error":
            return await update.message.reply_text(EXCEPTION_ERROR)
        if err == "no game found":
            return await update.message.reply_text(NO_GAME_ERROR)
        if err == "player not in game":
            return await update.message.reply_text(PLAYER_NOT_IN_GAME_ERROR)
        if err == "no category error":
            return await update.message.reply_text("no category provided")
        if err == "num of teams error":
            return await update.message.reply_text(f"number of teams must be {11 + other[0]}")
        if err == "formation error":
            return await update.message.reply_text("formation must be 442 or 443 or 4231 or 352 or 523 written like this")
        if err == "duplicate teams error":
            return await update.message.reply_text("the teams must be with no duplicates")
        if err == "expection":
            return await update.message.reply_text(EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(EXCEPTION_ERROR)

    curr_player = await update.effective_chat.get_member(other[4])
    await update.message.reply_text(f"the category is {other[1]} the formation is {other[2]} the availabe teams are f{other[3]}",
                                    parse_mode=ParseMode.HTML)
    return await update.message.reply_text(f"player {curr_player.user.mention_html()} press the button to pick team",
                                           parse_mode=ParseMode.HTML,
                                           reply_markup=InlineKeyboardMarkup([
                                                [InlineKeyboardButton(text="pick team", callback_data="draft_random_team")]
                                           ]))

async def handle_test_draft_pick_team_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.callback_query or not update.effective_chat or not update.effective_user:
        return

    q = update.callback_query
    await q.answer()
    
    with get_session() as session:
        res, err, team, formation, curr_pos = rand_team_draft(update.effective_chat.id, update.effective_user.id, session)
    if not res:
        if err == "no game found":
            return await context.bot.send_message(text=NO_GAME_ERROR,
                                                  chat_id=update.effective_chat.id)
        if err == "player not in game":
            return await context.bot.send_message(text=PLAYER_NOT_IN_GAME_ERROR,
                                                  chat_id=update.effective_chat.id)
        if err == "game error":
            return await context.bot.send_message(text=EXCEPTION_ERROR,
                                                  chat_id=update.effective_chat.id)
        if err == "curr_player_error":
            return await context.bot.send_message(text="player not curr player",
                                                  chat_id=update.effective_chat.id)
        if err == "expection":
            return await context.bot.send_message(text=EXCEPTION_ERROR,
                                                  chat_id=update.effective_chat.id)
        else:
            return await context.bot.send_message(text=EXCEPTION_ERROR,
                                                  chat_id=update.effective_chat.id)

    await context.bot.send_message(text=f"the team is {team} now choose your {FORMATIONS[formation][curr_pos]}", chat_id=update.effective_chat.id)

async def handle_test_draft_add_pos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_user or not update.effective_chat or not context.job_queue or update.effective_chat.type == "private":
        return

    with get_session() as session:
        res, status, other = add_pos_to_team_draft(update.effective_chat.id, update.effective_user.id,
                                            update.message.text.lower().strip(), session)
    if not res:
        if status == "no game found":
            return await update.message.reply_text(NO_GAME_ERROR)
        if status == "player not in game":
            return await update.message.reply_text(PLAYER_NOT_IN_GAME_ERROR)
        if status == "curr_player_error":
            return await update.message.reply_text("not current player")
        if status == "game_error":
            return await update.message.reply_text(EXCEPTION_ERROR)
        if status == "picked_pos_error":
            return await update.message.reply_text("player has already picked this position")
        if status == "picked_team_error":
            return await update.message.reply_text("this team has already passed")
        if status == "taken_player_error":
            return await update.message.reply_text("this player is taken")
        if status == "expection":
            return await update.message.reply_text(EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(EXCEPTION_ERROR)

    if status == "new_pos":
        if not other[0]:
            return await update.message.reply_text(EXCEPTION_ERROR)
        start_player = await update.effective_chat.get_member(other[0])
        return await update.message.reply_text(f"player {start_player.user.mention_html()} press the button to pick team",
                                               parse_mode=ParseMode.HTML,
                                               reply_markup=InlineKeyboardMarkup([
                                                    [InlineKeyboardButton(text="pick team", callback_data="draft_random_team")]
                                               ]))
    elif status == "same_pos":
        if not other[0] or not other[1] or not other[2]:
            return await update.message.reply_text(EXCEPTION_ERROR)
        curr_player = await update.effective_chat.get_member(other[0])
        return await update.message.reply_text(f"player {curr_player.user.mention_html()} choose your player for {FORMATIONS[other[1]][other[2]]}",
                                               parse_mode=ParseMode.HTML)
    elif status == "end_game":
        if not other[0] or not other[1] or not other[2] or not other[3]:
            return await update.message.reply_text(EXCEPTION_ERROR)

        data = {"game_id":update.effective_chat.id, "time":datetime.now()}
        context.job_queue.run_repeating(handle_test_draft_reapting_votes_job, interval=20, first=10, data=data, chat_id=update.effective_chat.id,
                                        name=f"draft_reapting_votes_job_{update.effective_chat.id}")
        context.job_queue.run_once(handle_test_draft_set_votes_job, when=30, data=data, chat_id=update.effective_chat.id,
                                   name=f"draft_set_votes_job_{update.effective_chat.id}")
        teams = []
        for player_id, team in other[3]:
            player = await update.effective_chat.get_member(player_id)
            teams.append((player.user, team))

        teams = format_teams(teams, FORMATIONS[other[1]])
        await context.bot.send_message(text=f"the teams\n{teams}", chat_id=update.effective_chat.id, parse_mode=ParseMode.HTML)
        await context.bot.send_message(text="the drafting has ended discuss the teams for 3 minutes then vote for the best", chat_id=update.effective_chat.id)
        return
    else:
        return await update.message.reply_text(status)

async def handle_test_draft_reapting_votes_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    with get_session() as session:
        res, err, state, _ = check_draft(context.job.chat_id, session)
    if not res:
        if err == "no game found":
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=NO_GAME_ERROR)
        return await context.bot.send_message(chat_id=context.job.chat_id,
                                              text=EXCEPTION_ERROR)

    if not res or state != 3:
        return await context.bot.send_message(chat_id=context.job.chat_id,
                                              text=STATE_ERROR)

    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to decide: {round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )

async def handle_test_draft_start_votes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_user or not update.effective_chat or not context.job_queue:
        return
    
    remove_jobs(f"draft_reapting_votes_job_{update.effective_chat.id}", context)
    remove_jobs(f"draft_reapting_votes_end_job_{update.effective_chat.id}", context)
    chat_id = update.effective_chat.id
    with get_session() as session:
        res, err, state, players_ids = get_vote_data(chat_id, session)
    if not res:
        if err == "no game":
            return await update.message.reply_text(NO_GAME_ERROR)
        if err == "no players associated with the game":
            return await update.message.reply_text(PLAYER_NOT_IN_GAME_ERROR)
        if err == "exception":
            return await update.message.reply_text(EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(EXCEPTION_ERROR)

    if state != 3:
        return await update.message.reply_text(STATE_ERROR)
    if not players_ids:
        return await update.message.reply_text(PLAYER_NOT_IN_GAME_ERROR)

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
    context.job_queue.run_repeating(handle_test_draft_reapting_votes_end_job, interval=20, first=10, data=data, chat_id=chat_id,
                                    name=f"draft_reapting_votes_end_job_{update.effective_chat.id}")
    context.job_queue.run_once(handle_test_draft_end_votes_job, when=30, data=data, chat_id=chat_id ,
                               name=f"draft_end_votes_job_{update.effective_chat.id}")

async def handle_test_draft_reapting_votes_end_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    with get_session() as session:
        res, err, state, _ = check_draft(context.job.chat_id, session)
    if not res:
        if err == "no game found":
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=NO_GAME_ERROR)
        return await context.bot.send_message(chat_id=context.job.chat_id,
                                              text=EXCEPTION_ERROR)

    if not res or state != 3:
        return await context.bot.send_message(chat_id=context.job.chat_id,
                                              text=STATE_ERROR)

    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to vote: {round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )

async def handle_test_draft_set_votes_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    remove_jobs(f"draft_reapting_votes_job_{context.job.chat_id}", context)
    remove_jobs(f"draft_reapting_votes_end_job_{context.job.chat_id}", context)
    
    chat_id = context.job.data["game_id"]
    with get_session() as session:
        res, err, state, players_ids = get_vote_data(chat_id, session)
    if not res:
        if err == "no game":
            return await context.bot.send_message(chat_id==chat_id, text=NO_GAME_ERROR)
        if err == "no players associated with the game":
            return await context.bot.send_message(chat_id==chat_id, text=PLAYER_NOT_IN_GAME_ERROR)
        if err == "exception":
            return await context.bot.send_message(chat_id==chat_id, text=EXCEPTION_ERROR)
        else:
            return await context.bot.send_message(chat_id==chat_id, text=EXCEPTION_ERROR)

    if state != 3:
        return await context.bot.send_message(chat_id==chat_id, text=STATE_ERROR)
    if not players_ids:
        return await context.bot.send_message(chat_id==chat_id, text=PLAYER_NOT_IN_GAME_ERROR)

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
    context.job_queue.run_repeating(handle_test_draft_reapting_votes_end_job, interval=20, first=10, data=data, chat_id=chat_id,
                                    name=f"draft_reapting_votes_end_job_{context.job.chat_id}")
    context.job_queue.run_once(handle_test_draft_end_votes_job, when=30, data=data, chat_id=chat_id ,
                               name=f"draft_end_votes_job_{context.job.chat_id}")

async def handle_test_draft_vote_recive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.poll_answer or not context.job_queue:
        return

    answer = update.poll_answer
    poll_data = context.bot_data[f"poll_{answer.poll_id}"]
    chat_id = poll_data["chat_id"]
    with get_session() as session:
        res, err, _, num_players = check_draft(chat_id, session)
    if not res:
        if err == "no game found":
            return await context.bot.send_message(chat_id=chat_id,
                                                  text=NO_GAME_ERROR)
        return await context.bot.send_message(chat_id=chat_id,
                                              text=EXCEPTION_ERROR)

    try:
        questions = poll_data["questions"]
    except KeyError:
        return

    poll_data["votes_count"][questions[answer.option_ids[0]]] += 1 
    poll_data["answers"] += 1

    if poll_data["answers"] == num_players:
        remove_jobs(f"draft_reapting_votes_job_{chat_id}", context)
        remove_jobs(f"draft_end_votes_job_{chat_id}", context)
        #await context.bot.stop_poll(chat_id=chat_id, message_id=poll_data["message_id"])
        data = {"game_id":chat_id, "time":datetime.now(), "poll_id":update.poll_answer.poll_id}
        context.job_queue.run_once(handle_test_draft_end_votes_job, when=0, data=data, chat_id=chat_id ,
                                   name=f"draft_end_votes_job_{chat_id}")

async def handle_test_draft_end_votes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_user or not update.effective_chat or not context.job_queue:
        return
    
    remove_jobs(f"draft_reapting_votes_job_{update.effective_chat.id}", context)
    remove_jobs(f"draft_reapting_votes_end_job_{update.effective_chat.id}", context)
    poll_data = context.bot_data[f"poll_{update.effective_chat.id}"]
    chat_id = poll_data["chat_id"]

    votes = poll_data["votes_count"]
    with get_session() as session:
        res, err, players_and_teams, formation = end_game_draft(chat_id, session)
    if not res:
        if err == "no game found":
            return await context.bot.send_message(text=NO_GAME_ERROR, chat_id=chat_id)
        if err == "no players no formation":
            return await context.bot.send_message(text=PLAYER_NOT_IN_GAME_ERROR, chat_id=chat_id)
        if err == "exception":
            return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=chat_id)
        else:
            return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=chat_id)

    if not players_and_teams or not formation:
        return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=chat_id)
    
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
    context.job_queue.run_once(handle_test_draft_end_game_job, when=0, data=data, chat_id=chat_id ,
                               name=f"draft_end_game_job_{update.effective_chat.id}")

async def handle_test_draft_end_votes_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    chat_id = context.job.data["game_id"]
    remove_jobs(f"draft_reapting_votes_job_{chat_id}", context)
    remove_jobs(f"draft_reapting_votes_end_job_{chat_id}", context)
    
    poll_id = context.job.data["poll_id"]
    poll_data = context.bot_data[f"poll_{poll_id}"]
    chat_id = poll_data["chat_id"]

    votes = poll_data["votes_count"]
    with get_session() as session:
        res, err, players_and_teams, formation = end_game_draft(chat_id, session)
    if not res:
        if err == "no game found":
            return await context.bot.send_message(text=NO_GAME_ERROR, chat_id=chat_id)
        if err == "no players no formation":
            return await context.bot.send_message(text=PLAYER_NOT_IN_GAME_ERROR, chat_id=chat_id)
        if err == "exception":
            return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=chat_id)
        else:
            return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=chat_id)

    if not players_and_teams or not formation:
        return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=chat_id)
    
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
    print(formation)
    data = {"game_id":chat_id, "time":datetime.now(), "winners":max_vote_ids, "formation":FORMATIONS[formation]}
    context.job_queue.run_once(handle_test_draft_end_game_job, when=0, data=data, chat_id=chat_id ,
                               name=f"draft_end_game_job_{chat_id}")

async def handle_test_draft_end_game_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    remove_jobs(f"draft_reapting_votes_job_{context.job.chat_id}", context)
    remove_jobs(f"draft_reapting_votes_end_job_{context.job.chat_id}", context)

    winners = context.job.data["winners"]
    formation = context.job.data["formation"]
    
    if not isinstance(winners, list):
        return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=context.job.chat_id)
    if not isinstance(formation, dict):
        return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=context.job.chat_id)

    winners_text = ""
    teams = []
    for winner in winners:
        winners_text += f"{winner[0].mention_html()}\n"
        teams.append((winner[0], winner[1]))
    teams = format_teams(teams, formation)
    await context.bot.send_message(text=f"the winners are {winners_text}\n the teams\n{teams}", chat_id=context.job.chat_id,
                                   parse_mode=ParseMode.HTML)

async def handle_test_draft_cancel_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message:
        return

    with get_session() as session:
        res, err = cancel_game_draft(update.effective_chat.id, session)
    if not res:
        if err == "no game found":
            return await update.message.reply_text(NO_GAME_ERROR)
        if err == "exception":
            return await update.message.reply_text(EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(EXCEPTION_ERROR)

    remove_jobs(f"draft_reapting_votes_job_{update.effective_chat.id}", context)
    remove_jobs(f"draft_reapting_end_votes_job_{update.effective_chat.id}", context)
    remove_jobs(f"draft_end_votes_job_{update.effective_chat.id}", context)
    remove_jobs(f"draft_set_votes_job_{update.effective_chat.id}", context)
    remove_jobs(f"draft_reapting_join_job_{update.effective_chat.id}", context)
    remove_jobs(f"draft_start_game_job_{update.effective_chat.id}", context)
    remove_jobs(f"draft_reapting_statement_job_{update.effective_chat.id}", context)
    remove_jobs(f"draft_set_statement_command_job_{update.effective_chat.id}", context)

    await update.message.reply_text("game has been canceled")

make_game_test_handler = CommandHandler("test_make", handle_test_make_game)
join_game_test_handler = CommandHandler("test_join", handle_test_join_game)
start_game_test_handler = CommandHandler("test_start", handle_test_start_game)
set_game_test_handler = CommandHandler("test_set", handle_test_set_state)
cancel_game_test_handler = CommandHandler("test_cancel", handle_test_draft_cancel_game)
end_vote_game_test_handler = CommandHandler("test_end_vote", handle_test_draft_end_votes_command)
start_vote_game_test_handler = CommandHandler("test_start_vote", handle_test_draft_start_votes_command)
position_draft_message_test_handler = MessageHandler((filters.TEXT & ~filters.COMMAND), handle_test_draft_add_pos)
vote_recive_poll_answer_test_handler = PollAnswerHandler(handle_test_draft_vote_recive)
join_game_callback_test_handler = CallbackQueryHandler(callback=handle_test_draft_join_callback, pattern="^draft_join$")
random_team_draft_game_callback_handler = CallbackQueryHandler(callback=handle_test_draft_pick_team_callback, pattern="^draft_random_team$")
