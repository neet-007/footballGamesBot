from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, User, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from telegram.ext._handlers.callbackqueryhandler import CallbackQueryHandler
from telegram.ext._handlers.commandhandler import CommandHandler
from telegram.ext._handlers.pollanswerhandler import PollAnswerHandler

from db.connection import get_session
from games.draft_functions import FORMATIONS, add_pos_to_team_draft, add_vote, cancel_game_draft, check_draft, end_game_draft, end_round_draft, get_vote_data, get_vote_results, join_game_draft, make_vote, new_game_draft, rand_team_draft, set_game_states_draft, start_game_draft, transfers
from utils.helpers import remove_jobs

PLAYER_NOT_IN_GAME_ERROR = "player is not in game"
NO_GAME_ERROR = "there is no game in this chat \nstart one using /new_draft"
EXCEPTION_ERROR = "internal error happend please try again later"
STATE_ERROR = "game error happend\n or this is not the time for this command"
CURR_PLAYER_ERROR = "❌  your are not the current player"

JOBS_END_TIME_SECONDS = 180
JOBS_REPEATING_INTERVAL = 20
JOBS_REPEATING_FIRST = 10

DRAFT_NEW_COMMAND = "draft_new"
DRAFT_JOIN_COMMAND = "draft_join"
DRAFT_START_COMMAND = "draft_start"
DRAFT_SET_STATE_COMMAND = "draft_set_state"
DRAFT_ADD_POS_COMMAND = "draft_add_pos"
DRAFT_START_VOTE_COMMAND = "draft_start_vote"
DRAFT_END_VOTE_COMMAND = "draft_end_vote"
DRAFT_LEAVE_GAME_COMMAND = "draft_leave_game"
DRAFT_CANCEL_GAME_COMMAND = "draft_cancel_game"

def format_teams(teams:list[tuple[User, dict[str, str]]], formations:dict[str, str]):
    text = ""
    for player, team in teams:
        players_list = [f"{formations[pos]}:{name}\n" for pos, name in team.items()]
        players_list = "".join(players_list)
        text += f"{player.mention_html()}\n{players_list}"
    return text

async def handle_draft_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.effective_user or not update.message or not context.job_queue or update.effective_chat.type == "private":
        return

    with get_session() as session:
        res, err = new_game_draft(update.effective_chat.id, session)
    if not res:
        if err == "a game has started in this chat":
            return await update.message.reply_text("a game has started in this chat cant make a new one")
        if err == "exception":
            return await update.message.reply_text(EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(EXCEPTION_ERROR)

    data = {"time":datetime.now()}
    context.job_queue.run_repeating(handle_draft_reapting_join_job, interval=JOBS_REPEATING_INTERVAL,
                                    first=JOBS_REPEATING_FIRST, data=data, chat_id=update.effective_chat.id,
                                    name=f"draft_reapting_join_job_{update.effective_chat.id}")
    context.job_queue.run_once(handle_draft_start_game_job, when=JOBS_END_TIME_SECONDS, data=data, chat_id=update.effective_chat.id,
                               name=f"draft_start_game_job_{update.effective_chat.id}")
    await update.message.reply_text(text=f"a draft game 📝 has started /{DRAFT_JOIN_COMMAND} or press the button", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="join game", callback_data="draft_join")]
        ]
    ))

async def handle_draft_reapting_join_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    with get_session() as session:
        res, err, state, num_players = check_draft(context.job.chat_id, session)
    if not res:
        if err == "no game found":
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=NO_GAME_ERROR)
        if err == "exception":
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=EXCEPTION_ERROR)
        else:
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=EXCEPTION_ERROR)
    
    if state != 0:
        return await context.bot.send_message(chat_id=context.job.chat_id,
                                              text=STATE_ERROR)

    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to join:{round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds\n use /{DRAFT_JOIN_COMMAND} to join the game\nor /{DRAFT_START_COMMAND} to start game\nnumber of players in game:{num_players}"
    )

async def handle_draft_start_game_job(context: ContextTypes.DEFAULT_TYPE):
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
            return await context.bot.send_message(text=f"there are no players in this game\nstart a new one /{DRAFT_NEW_COMMAND}",
                                                  chat_id=context.job.chat_id)
        if err == "number of players is less than 2 or not as expected":
            return await context.bot.send_message(text=f"number of players less than two could not start\nstart a new one /{DRAFT_NEW_COMMAND}",
                                                  chat_id=context.job.chat_id)
        if err == "exception":
            return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=context.job.chat_id)
        else:
            return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=context.job.chat_id)

    data = {"time":datetime.now()}
    context.job_queue.run_repeating(handle_draft_reapting_statement_job, interval=JOBS_REPEATING_INTERVAL,
                                    first=JOBS_REPEATING_FIRST, data=data, chat_id=context.job.chat_id,
                                    name=f"draft_reapting_statement_job_{context.job.chat_id}")
    context.job_queue.run_once(handle_draft_set_state_command_job, when=JOBS_END_TIME_SECONDS, data=data, chat_id=context.job.chat_id,
                               name=f"draft_set_state_command_job_{context.job.chat_id}")
    
    await context.bot.send_message(text=f"""the draft game has started you have {JOBS_END_TIME_SECONDS} secnods to
decide the category, teams and formations[433, 4231, 442, 532, 352]
then send the command /{DRAFT_SET_STATE_COMMAND} [category], [teams], [formation]
teams should be separated by -, like [team1-team2-team3] and the number of teams must be {11 + num_players}
supported formations are 442, 443, 4231, 352, 532 in this foramt""",
                                   chat_id=context.job.chat_id)

async def handle_draft_join(update: Update, _: ContextTypes.DEFAULT_TYPE):
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

async def handle_draft_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def handle_draft_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            return await update.message.reply_text(text=f"there are no players in this game\nstart a new one /{DRAFT_NEW_COMMAND}")
        if err == "number of players is less than 2 or not as expected":
            return await update.message.reply_text(text=f"number of players less than two could not start\n start a new one /{DRAFT_NEW_COMMAND}")
        if err == "exception":
            return await update.message.reply_text(text=EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(text=EXCEPTION_ERROR)

    data = {"time":datetime.now()}
    context.job_queue.run_repeating(handle_draft_reapting_statement_job, interval=JOBS_REPEATING_INTERVAL,
                                    first=JOBS_REPEATING_FIRST, data=data, chat_id=update.effective_chat.id,
                                    name=f"draft_reapting_statement_job_{update.effective_chat.id}")
    context.job_queue.run_once(handle_draft_set_state_command_job, when=JOBS_END_TIME_SECONDS, data=data, chat_id=update.effective_chat.id,
                               name=f"draft_set_state_command_job_{update.effective_chat.id}")

    await update.message.reply_text(f"""the draft game has started you have {JOBS_END_TIME_SECONDS} secnods to
decide the category, teams and formations[433, 4231, 442, 532, 352]
then send the command /{DRAFT_SET_STATE_COMMAND} [category], [teams], [formation]
teams should be separated by -, like [team1-team2-team3] and the number of teams must be {11 + num_players}
supported formations are 442, 443, 4231, 352, 532 in this foramt""")

async def handle_draft_reapting_statement_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    with get_session() as session:
        res, err,  state, _ = check_draft(context.job.chat_id, session)
    if not res:
        if err == "no game found":
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=NO_GAME_ERROR)
        if err == "exception":
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=EXCEPTION_ERROR)
        else:
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=EXCEPTION_ERROR)

    if state != 1:
        return await context.bot.send_message(chat_id=context.job.chat_id,
                                              text=STATE_ERROR)
    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to decide statements:{round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )
 
async def handle_draft_set_state_command_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    remove_jobs(f"draft_reapting_statement_job_{context.job.chat_id}", context)
    with get_session() as session:
        res, err,  state, num_players = check_draft(context.job.chat_id, session)
    if not res:
        if err == "no game found":
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=NO_GAME_ERROR)
        if err == "exception":
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=EXCEPTION_ERROR)
        else:
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=EXCEPTION_ERROR)

    if state != 1:
        return await context.bot.send_message(chat_id=context.job.chat_id,
                                              text=STATE_ERROR)

    await context.bot.send_message(chat_id=context.job.chat_id, text=f"""now send {DRAFT_SET_STATE_COMMAND} to
decide the category, teams and formations[433, 4231, 442, 532, 352]
teams should be separated by -, like [team1-team2-team3] and the number of teams must be {11 + num_players}
supported formations are 442, 443, 4231, 352, 532 in this foramt""")

async def handle_draft_set_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_chat or not update.effective_user or update.effective_chat.type == "private":
        return

    remove_jobs(f"draft_reapting_statement_job_{update.effective_chat.id}", context)
    remove_jobs(f"draft_set_state_command_job_{update.effective_chat.id}", context)
    text = update.message.text.lower().replace("/test_set", "").split(",")
    if len(text) != 3:
        return await update.message.reply_text("there is something missing\nyou must provied the category, teams, foramtation seperated by commas ','")

    with get_session() as session:
        res, err, other = set_game_states_draft(update.effective_chat.id, update.effective_user.id,
                                text[0].strip(), text[1].split("-"), text[2].strip(), session)
    if not res:
        if err == "state error":
            return await update.message.reply_text(STATE_ERROR)
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

async def handle_draft_pick_team_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.callback_query or not update.effective_chat or not update.effective_user:
        return

    q = update.callback_query
    await q.answer()
    
    with get_session() as session:
        res, err, team, formation, curr_pos, non_picked_team = rand_team_draft(update.effective_chat.id, update.effective_user.id, session)
    if not res:
        if err == "no game found":
            return await context.bot.send_message(text=NO_GAME_ERROR,
                                                  chat_id=update.effective_chat.id)
        if err == "player not in game":
            return await context.bot.send_message(text=PLAYER_NOT_IN_GAME_ERROR,
                                                  chat_id=update.effective_chat.id)
        if err == "state error":
            return await context.bot.send_message(text=STATE_ERROR,
                                                  chat_id=update.effective_chat.id)
        if err == "curr_player_error":
            return await context.bot.send_message(text=CURR_PLAYER_ERROR,
                                                  chat_id=update.effective_chat.id)
        if err == "expection":
            return await context.bot.send_message(text=EXCEPTION_ERROR,
                                                  chat_id=update.effective_chat.id)
        else:
            return await context.bot.send_message(text=EXCEPTION_ERROR,
                                                  chat_id=update.effective_chat.id)

    non_picked_team = "\n".join([f"🟢 {team}" for team in non_picked_team])
    await context.bot.send_message(text=f"the team is <strong>{team.capitalize()}</strong> now choose your <strong>{FORMATIONS[formation][curr_pos].upper()}</strong>\nthe reamaining teams are\n{non_picked_team}",
                                   chat_id=update.effective_chat.id, parse_mode=ParseMode.HTML)

async def handle_draft_transfer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.callback_query or not update.effective_chat or not update.effective_user or not context.job_queue:
        return

    q = update.callback_query
    position = q.data

    await q.answer()
    
    if position is None:
        return
    
    position = position.replace("draft_transfer_", "")

    with get_session() as session:
        res, err, other = transfers(update.effective_chat.id, update.effective_user.id, position, session)
    print("\n======================\n", err, "\n======================\n")
    if not res:
        if err == "no game found":
            return await context.bot.send_message(text=NO_GAME_ERROR,
                                                  chat_id=update.effective_chat.id)
        if err == "player not in game":
            return await context.bot.send_message(text=PLAYER_NOT_IN_GAME_ERROR,
                                                  chat_id=update.effective_chat.id)
        if err == "state error":
            return await context.bot.send_message(text=STATE_ERROR,
                                                  chat_id=update.effective_chat.id)
        if err == "curr_player_error":
            return await context.bot.send_message(text=CURR_PLAYER_ERROR,
                                                  chat_id=update.effective_chat.id)
        if err == "expection":
            return await context.bot.send_message(text=EXCEPTION_ERROR,
                                                  chat_id=update.effective_chat.id)
        if err == "game error":
            return await context.bot.send_message(text=EXCEPTION_ERROR,
                                                  chat_id=update.effective_chat.id)
        if err == "invalid posistion":
            return await context.bot.send_message(text="this position is invalid",
                                                  chat_id=update.effective_chat.id)
        if err == "player has transferd error":
            return await context.bot.send_message(text="player has already transfer",
                                                  chat_id=update.effective_chat.id)
        else:
            return await context.bot.send_message(text=EXCEPTION_ERROR,
                                                  chat_id=update.effective_chat.id)

    if err == "skipped":
        if not other[3] or not other[1]:
            return

        next_player = await context.bot.get_chat_member(chat_id=update.effective_chat.id, user_id=other[3])
        formation_ = FORMATIONS[other[1]]
        return await context.bot.send_message(chat_id=update.effective_chat.id,
            text=f"player {next_player.user.mention_html()} press the button to pick the position you want to transfer\n if you dont want to transfer then pick skip",
                                               parse_mode=ParseMode.HTML,
                                               reply_markup=InlineKeyboardMarkup([
                                                    [InlineKeyboardButton(text=formation_["p1"], callback_data="draft_transfer_p1")],
                                                    [InlineKeyboardButton(text=formation_["p2"], callback_data="draft_transfer_p2")],
                                                    [InlineKeyboardButton(text=formation_["p3"], callback_data="draft_transfer_p3")],
                                                    [InlineKeyboardButton(text=formation_["p4"], callback_data="draft_transfer_p4")],
                                                    [InlineKeyboardButton(text=formation_["p5"], callback_data="draft_transfer_p5")],
                                                    [InlineKeyboardButton(text=formation_["p6"], callback_data="draft_transfer_p6")],
                                                    [InlineKeyboardButton(text=formation_["p7"], callback_data="draft_transfer_p7")],
                                                    [InlineKeyboardButton(text=formation_["p8"], callback_data="draft_transfer_p8")],
                                                    [InlineKeyboardButton(text=formation_["p9"], callback_data="draft_transfer_p9")],
                                                    [InlineKeyboardButton(text=formation_["p10"], callback_data="draft_transfer_p10")],
                                                    [InlineKeyboardButton(text=formation_["p11"], callback_data="draft_transfer_p11")],
                                                    [InlineKeyboardButton(text="skip", callback_data="draft_transfer_skip")],
                                               ]))

    if err == "end_game":
        if not other[4] or not other[1]:
            return

        data = {"time":datetime.now()}
        context.job_queue.run_repeating(handle_draft_reapting_votes_job, interval=JOBS_REPEATING_INTERVAL,
                                        first=JOBS_REPEATING_FIRST, data=data, chat_id=update.effective_chat.id,
                                        name=f"draft_reapting_votes_job_{update.effective_chat.id}")
        context.job_queue.run_once(handle_draft_set_votes_job, when=JOBS_END_TIME_SECONDS, data=data, chat_id=update.effective_chat.id,
                                   name=f"draft_set_votes_job_{update.effective_chat.id}")

        teams = []
        for player_id, team in other[4]:
            player = await update.effective_chat.get_member(player_id)
            teams.append((player.user, team))

        teams = format_teams(teams, FORMATIONS[other[1]])
        await context.bot.send_message(text=f"the teams are\n{teams}", chat_id=update.effective_chat.id, parse_mode=ParseMode.HTML)
        await context.bot.send_message(text=f"the drafting has ended discuss the teams for {JOBS_END_TIME_SECONDS} seconds then vote for the best", chat_id=update.effective_chat.id)
        return

    if other[0] is None or other[1] is None or other[2] is None or other[5] is None:
        return

    non_picked_team = "\n".join([f"🟢 {team}" for team in other[5]])
    await context.bot.send_message(text=f"the team is <strong>{other[0].capitalize()}</strong> now choose your <strong>{FORMATIONS[other[1]][other[2]].upper()}</strong>\nthe reamaining teams are\n{non_picked_team}",
                                   chat_id=update.effective_chat.id, parse_mode=ParseMode.HTML)

async def handle_draft_add_pos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_user or not update.effective_chat or not context.job_queue or update.effective_chat.type == "private":
        return

    with get_session() as session:
        res, status, other = add_pos_to_team_draft(update.effective_chat.id, update.effective_user.id,
                                            update.message.text.lower().strip().replace(f"/{DRAFT_ADD_POS_COMMAND}", ""), session)
    if not res:
        if status == "no game found":
            return await update.message.reply_text(NO_GAME_ERROR)
        if status == "player not in game":
            return await update.message.reply_text(PLAYER_NOT_IN_GAME_ERROR)
        if status == "curr_player_error":
            return await update.message.reply_text(CURR_PLAYER_ERROR)
        if status == "state error":
            return await update.message.reply_text(STATE_ERROR)
        if status == "picked_pos_error":
            return await update.message.reply_text("❌ player has already picked this position")
        if status == "picked_team_error":
            return await update.message.reply_text("❌ this team has already passed")
        if status == "taken player error":
            return await update.message.reply_text("❌ this player is taken")
        if status == "expection":
            return await update.message.reply_text(EXCEPTION_ERROR)
        else:
            return await update.message.reply_text(EXCEPTION_ERROR)

    if status == "end round":
        return await handle_draft_end_round(update, context)

    elif status == "same_pos":
        if not other[0] or not other[1] or not other[2]:
            return await update.message.reply_text(EXCEPTION_ERROR)
        curr_player = await update.effective_chat.get_member(other[0])
        return await update.message.reply_text(f"player {curr_player.user.mention_html()} choose your player for {FORMATIONS[other[1]][other[2]].upper()}",
                                               parse_mode=ParseMode.HTML)

async def handle_draft_end_round(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_user or not update.effective_chat or not context.job_queue or update.effective_chat.type == "private":
        return

    with get_session() as session:
        res, status, other = end_round_draft(update.effective_chat.id, session)

    if not res:
        if status == "no game found":
            return update.message.reply_text(NO_GAME_ERROR)
        if status == "expection":
            return update.message.reply_text(EXCEPTION_ERROR)
        else:
            return update.message.reply_text(EXCEPTION_ERROR)

    if status == "new_pos":
        if not other[0]:
            return await update.message.reply_text(EXCEPTION_ERROR)
        start_player = await update.effective_chat.get_member(other[0])
        return await update.message.reply_text(f"player {start_player.user.mention_html()} press the button to pick team",
                                               parse_mode=ParseMode.HTML,
                                               reply_markup=InlineKeyboardMarkup([
                                                    [InlineKeyboardButton(text="pick team", callback_data="draft_random_team")]
                                               ]))
    if status == "transfer_start" or status == "new_transfer":
        if not other[0] or not other[1]:
            return await update.message.reply_text(EXCEPTION_ERROR)
        start_player = await update.effective_chat.get_member(other[0])
        formation_ = FORMATIONS[other[1]]
        return await update.message.reply_text(f"player {start_player.user.mention_html()} press the button to pick the position you want to transfer\n if you dont want to transfer then pick skip",
                                               parse_mode=ParseMode.HTML,
                                               reply_markup=InlineKeyboardMarkup([
                                                    [InlineKeyboardButton(text=formation_["p1"], callback_data="draft_transfer_p1")],
                                                    [InlineKeyboardButton(text=formation_["p2"], callback_data="draft_transfer_p2")],
                                                    [InlineKeyboardButton(text=formation_["p3"], callback_data="draft_transfer_p3")],
                                                    [InlineKeyboardButton(text=formation_["p4"], callback_data="draft_transfer_p4")],
                                                    [InlineKeyboardButton(text=formation_["p5"], callback_data="draft_transfer_p5")],
                                                    [InlineKeyboardButton(text=formation_["p6"], callback_data="draft_transfer_p6")],
                                                    [InlineKeyboardButton(text=formation_["p7"], callback_data="draft_transfer_p7")],
                                                    [InlineKeyboardButton(text=formation_["p8"], callback_data="draft_transfer_p8")],
                                                    [InlineKeyboardButton(text=formation_["p9"], callback_data="draft_transfer_p9")],
                                                    [InlineKeyboardButton(text=formation_["p10"], callback_data="draft_transfer_p10")],
                                                    [InlineKeyboardButton(text=formation_["p11"], callback_data="draft_transfer_p11")],
                                                    [InlineKeyboardButton(text="skip", callback_data="draft_transfer_skip")],
                                               ]))
    if status == "end_game":
        if not other[0] or not other[1] or not other[2] or not other[3]:
            return await update.message.reply_text(EXCEPTION_ERROR)

        data = {"time":datetime.now()}
        context.job_queue.run_repeating(handle_draft_reapting_votes_job, interval=JOBS_REPEATING_INTERVAL,
                                        first=JOBS_REPEATING_FIRST, data=data, chat_id=update.effective_chat.id,
                                        name=f"draft_reapting_votes_job_{update.effective_chat.id}")
        context.job_queue.run_once(handle_draft_set_votes_job, when=JOBS_END_TIME_SECONDS, data=data, chat_id=update.effective_chat.id,
                                   name=f"draft_set_votes_job_{update.effective_chat.id}")
        teams = []
        for player_id, team in other[3]:
            player = await update.effective_chat.get_member(player_id)
            teams.append((player.user, team))

        teams = format_teams(teams, FORMATIONS[other[1]])
        await context.bot.send_message(text=f"the teams\n{teams}", chat_id=update.effective_chat.id, parse_mode=ParseMode.HTML)
        await context.bot.send_message(text=f"the drafting has ended discuss the teams for {JOBS_END_TIME_SECONDS} seconds then vote for the best", chat_id=update.effective_chat.id)
        return

async def handle_draft_reapting_votes_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    with get_session() as session:
        res, err, state, _ = check_draft(context.job.chat_id, session)
    if not res:
        if err == "no game found":
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=NO_GAME_ERROR)
        if err == "exception":
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=EXCEPTION_ERROR)
        else:
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=EXCEPTION_ERROR)

    if not res or state != 4:
        return await context.bot.send_message(chat_id=context.job.chat_id,
                                              text=STATE_ERROR)

    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to decide: {round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )

async def handle_draft_start_votes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    if state != 4:
        return await update.message.reply_text(STATE_ERROR)
    if not players_ids:
        return await update.message.reply_text(PLAYER_NOT_IN_GAME_ERROR)


    players = [[], []]
    for id in players_ids:
        player = await context.bot.get_chat_member(chat_id, id[0])
        players[0].append(id)
        players[1].append(player.user.full_name)


    message = await context.bot.send_poll(question="who has the best team" ,options=players[1], chat_id=chat_id,
                                is_anonymous=False, allows_multiple_answers=False)

    if not message.poll:
        return

    with get_session() as session:
        res, err = make_vote(chat_id, players[0], message.message_id, message.poll.id, session)
        if not res:
            if err == "no game found":
                return await context.bot.send_message(chat_id=chat_id, text=NO_GAME_ERROR)
            if err == "exception":
                return await context.bot.send_message(chat_id=chat_id, text=EXCEPTION_ERROR)
            else:
                return await context.bot.send_message(chat_id=chat_id, text=EXCEPTION_ERROR)

    data = {"time":datetime.now()}
    context.job_queue.run_repeating(handle_draft_reapting_votes_end_job, interval=JOBS_REPEATING_INTERVAL,
                                    first=JOBS_REPEATING_FIRST, data=data, chat_id=chat_id,
                                    name=f"draft_reapting_votes_end_job_{update.effective_chat.id}")
    context.job_queue.run_once(handle_draft_end_votes_job, when=JOBS_END_TIME_SECONDS, data=data, chat_id=chat_id,
                               name=f"draft_end_votes_job_{update.effective_chat.id}")

async def handle_draft_reapting_votes_end_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict):
        return

    with get_session() as session:
        res, err, state, _ = check_draft(context.job.chat_id, session)
    if not res:
        if err == "no game found":
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=NO_GAME_ERROR)
        if err == "exception":
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=EXCEPTION_ERROR)
        else:
            return await context.bot.send_message(chat_id=context.job.chat_id,
                                                  text=EXCEPTION_ERROR)

    if not res or state != 4:
        return await context.bot.send_message(chat_id=context.job.chat_id,
                                              text=STATE_ERROR)

    await context.bot.send_message(
        chat_id=context.job.chat_id, 
        text=f"Remaining time to vote: {round((context.job.data['time'] + timedelta(minutes=3) - datetime.now()).total_seconds())} seconds"
    )

async def handle_draft_set_votes_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    remove_jobs(f"draft_reapting_votes_job_{context.job.chat_id}", context)
    remove_jobs(f"draft_reapting_votes_end_job_{context.job.chat_id}", context)
    
    chat_id = context.job.chat_id
    with get_session() as session:
        res, err, state, players_ids = get_vote_data(chat_id, session)
    if not res:
        if err == "no game":
            return await context.bot.send_message(chat_id=chat_id, text=NO_GAME_ERROR)
        if err == "no players associated with the game":
            return await context.bot.send_message(chat_id=chat_id, text=PLAYER_NOT_IN_GAME_ERROR)
        if err == "exception":
            return await context.bot.send_message(chat_id=chat_id, text=EXCEPTION_ERROR)
        else:
            return await context.bot.send_message(chat_id=chat_id, text=EXCEPTION_ERROR)

    if state != 4:
        return await context.bot.send_message(chat_id=chat_id, text=STATE_ERROR)
    if not players_ids:
        return await context.bot.send_message(chat_id=chat_id, text=PLAYER_NOT_IN_GAME_ERROR)

    players = [[], []]
    for id in players_ids:
        player = await context.bot.get_chat_member(chat_id, id[0])
        players[0].append(id)
        players[1].append(player.user.full_name)


    message = await context.bot.send_poll(question="you has the best team" ,options=players[1], chat_id=chat_id,
                                is_anonymous=False, allows_multiple_answers=False)

    if not message.poll:
        return

    with get_session() as session:
        res, err = make_vote(chat_id, players[0], message.message_id, message.poll.id, session)
        if not res:
            if err == "no game found":
                return await context.bot.send_message(chat_id=chat_id, text=NO_GAME_ERROR)
            if err == "exception":
                return await context.bot.send_message(chat_id=chat_id, text=EXCEPTION_ERROR)
            else:
                return await context.bot.send_message(chat_id=chat_id, text=EXCEPTION_ERROR)

    data = {"time":datetime.now()}
    context.job_queue.run_repeating(handle_draft_reapting_votes_end_job, interval=JOBS_REPEATING_INTERVAL,
                                    first=JOBS_REPEATING_FIRST, data=data, chat_id=chat_id,
                                    name=f"draft_reapting_votes_end_job_{context.job.chat_id}")
    context.job_queue.run_once(handle_draft_end_votes_job, when=JOBS_END_TIME_SECONDS, data=data, chat_id=chat_id,
                               name=f"draft_end_votes_job_{context.job.chat_id}")

async def handle_draft_vote_recive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.poll_answer or not context.job_queue:
        return

    answer = update.poll_answer
    poll_id = answer.poll_id

    with get_session() as session:
        res, err, chat_id = add_vote(poll_id, answer.option_ids[0], session)

    if not res:
        if err == "no game found":
            return
        if err == "exception":
            return
        else:
            return

    if err == "end vote":
        remove_jobs(f"draft_reapting_votes_job_{chat_id}", context)
        remove_jobs(f"draft_end_votes_job_{chat_id}", context)
        data = {"time":datetime.now(), "poll_id":update.poll_answer.poll_id}
        context.job_queue.run_once(handle_draft_end_votes_job, when=0, data=data, chat_id=chat_id ,
                                   name=f"draft_end_votes_job_{chat_id}")

async def handle_draft_end_votes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or not update.effective_user or not update.effective_chat or not context.job_queue:
        return
    
    remove_jobs(f"draft_reapting_votes_job_{update.effective_chat.id}", context)
    remove_jobs(f"draft_reapting_votes_end_job_{update.effective_chat.id}", context)
    chat_id = update.effective_chat.id

    with get_session() as session:
        res, err, message_id, votes = get_vote_results(chat_id, session)
        if not res:
            if err == "exception":
                return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=chat_id)
            else:
                return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=chat_id)

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

    is_won = True
    if max_vote == 0 or max_vote == float("-inf"):
        is_won = False

    await context.bot.stop_poll(chat_id=chat_id, message_id=message_id)
    await draft_end_game(chat_id, max_vote_ids, FORMATIONS[formation], is_won, context)

async def handle_draft_end_votes_job(context: ContextTypes.DEFAULT_TYPE):
    if not context.job or not context.job.chat_id or not isinstance(context.job.data, dict) or not context.job_queue:
        return

    chat_id = context.job.chat_id
    remove_jobs(f"draft_reapting_votes_job_{chat_id}", context)
    remove_jobs(f"draft_reapting_votes_end_job_{chat_id}", context)

    with get_session() as session:
        res, err, message_id, votes = get_vote_results(chat_id, session)
        if not res:
            if err == "exception":
                return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=chat_id)
            else:
                return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=chat_id)

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

    is_won = True
    if max_vote == 0 or max_vote == float("-inf"):
        is_won = False

    await context.bot.stop_poll(chat_id=chat_id, message_id=message_id)
    await draft_end_game(chat_id, max_vote_ids, FORMATIONS[formation], is_won, context)

async def draft_end_game(chat_id, winners, formation, is_won, context: ContextTypes.DEFAULT_TYPE):
    remove_jobs(f"draft_reapting_votes_job_{chat_id}", context)
    remove_jobs(f"draft_reapting_votes_end_job_{chat_id}", context)

    if not isinstance(winners, list):
        return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=chat_id)
    if not isinstance(formation, dict):
        return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=chat_id)
    if not isinstance(is_won, bool):
        return await context.bot.send_message(text=EXCEPTION_ERROR, chat_id=chat_id)

    if not is_won:
        return await context.bot.send_message(text=f"the are no winners,\nno one voted", chat_id=chat_id)

    winners_text = ""
    teams = []
    for winner in winners:
        winners_text += f"{winner[0].mention_html()}\n"
        teams.append((winner[0], winner[1]))
    teams = format_teams(teams, formation)
    await context.bot.send_message(text=f"the winners are {winners_text}\n the teams\n{teams}", chat_id=chat_id,
                                   parse_mode=ParseMode.HTML)

async def handle_draft_cancel_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

draft_new_handler = CommandHandler(DRAFT_NEW_COMMAND, handle_draft_new)
draft_join_handler = CommandHandler(DRAFT_JOIN_COMMAND, handle_draft_join)
draft_start_handler = CommandHandler(DRAFT_START_COMMAND, handle_draft_start)
draft_set_state_handler = CommandHandler(DRAFT_SET_STATE_COMMAND, handle_draft_set_state)
draft_add_pos_handler = CommandHandler(DRAFT_ADD_POS_COMMAND, handle_draft_add_pos_command)
draft_cancel_game_handler = CommandHandler(DRAFT_CANCEL_GAME_COMMAND, handle_draft_cancel_game)
draft_end_vote_handler = CommandHandler(DRAFT_END_VOTE_COMMAND, handle_draft_end_votes_command)
draft_start_vote_handler = CommandHandler(DRAFT_START_VOTE_COMMAND, handle_draft_start_votes_command)
draft_vote_recive_handler = PollAnswerHandler(handle_draft_vote_recive)
draft_join_callback_handler = CallbackQueryHandler(callback=handle_draft_join_callback, pattern="^draft_join$")
draft_pick_team_callback_handler = CallbackQueryHandler(callback=handle_draft_pick_team_callback, pattern="^draft_random_team$")
draft_transfer_callback_handler = CallbackQueryHandler(callback=handle_draft_transfer_callback, pattern= r"^draft_transfer_(p[1-9]|p10|p11|skip)$")
