from telegram.ext import Application, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv
from os import getenv
from sys import exit
from bot.shared_handlers import error_handler, handle_help, handle_start, message_dispatcher
from games.draft_handlers import draft_new_handler, draft_join_handler, draft_start_handler, draft_set_state_handler, draft_start_vote_handler, draft_end_vote_handler, draft_cancel_game_handler, draft_vote_recive_handler, draft_join_callback_handler, draft_pick_team_callback_handler, draft_transfer_callback_handler
from games.guess_the_player_handlers import guess_the_player_start_game_command_handler, guess_the_player_join_game_command_handler, guess_the_player_new_game_command_handler,guess_the_player_ask_question_command_handler, guess_the_player_cancel_game_command_handler, guess_the_player_join_game_callback_handler, guess_the_player_leave_game_command_handler, guess_thE_player_get_questions_command_handler, new_db_handler

load_dotenv()

BOT_API_TOKEN = getenv("BOT_API_TOKEN")
if not BOT_API_TOKEN:
    #log fatal errpr
    exit(1)

ptb = (
    Application.builder()
    .updater(None)
    .token(BOT_API_TOKEN) 
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)

sync_ptb = (
    Application.builder()
    .token(BOT_API_TOKEN) 
    .build()
)


message_dispatch_handler = MessageHandler((filters.TEXT & ~filters.COMMAND), message_dispatcher)
help_handler = CommandHandler("help", handle_help)
start_handler = CommandHandler("start", handle_start)

ptb.add_handler(help_handler)
ptb.add_handler(start_handler)
ptb.add_error_handler(error_handler)
ptb.add_handler(new_db_handler)

ptb.add_handler(guess_the_player_new_game_command_handler)
ptb.add_handler(guess_the_player_join_game_command_handler)
ptb.add_handler(guess_the_player_join_game_callback_handler)
ptb.add_handler(guess_the_player_start_game_command_handler)
ptb.add_handler(guess_the_player_ask_question_command_handler)
ptb.add_handler(guess_the_player_cancel_game_command_handler)
ptb.add_handler(guess_the_player_leave_game_command_handler)
ptb.add_handler(guess_thE_player_get_questions_command_handler)

ptb.add_handler(message_dispatch_handler)

ptb.add_handler(draft_new_handler)
ptb.add_handler(draft_join_handler)
ptb.add_handler(draft_start_handler)
ptb.add_handler(draft_set_state_handler)
ptb.add_handler(draft_cancel_game_handler)
ptb.add_handler(draft_start_vote_handler)
ptb.add_handler(draft_end_vote_handler)
ptb.add_handler(draft_join_callback_handler)
ptb.add_handler(draft_transfer_callback_handler)
ptb.add_handler(draft_pick_team_callback_handler)
ptb.add_handler(draft_vote_recive_handler)

sync_ptb.add_handler(new_db_handler)
sync_ptb.add_handler(guess_the_player_new_game_command_handler)
sync_ptb.add_handler(guess_the_player_join_game_command_handler)
sync_ptb.add_handler(guess_the_player_join_game_callback_handler)
sync_ptb.add_handler(guess_the_player_start_game_command_handler)
sync_ptb.add_handler(guess_the_player_ask_question_command_handler)
sync_ptb.add_handler(guess_the_player_cancel_game_command_handler)
sync_ptb.add_handler(guess_the_player_leave_game_command_handler)
sync_ptb.add_handler(guess_thE_player_get_questions_command_handler)

sync_ptb.add_handler(draft_new_handler)
sync_ptb.add_handler(draft_join_handler)
sync_ptb.add_handler(draft_start_handler)
sync_ptb.add_handler(draft_set_state_handler)
sync_ptb.add_handler(draft_cancel_game_handler)
sync_ptb.add_handler(draft_start_vote_handler)
sync_ptb.add_handler(draft_end_vote_handler)
sync_ptb.add_handler(draft_join_callback_handler)
sync_ptb.add_handler(draft_pick_team_callback_handler)
sync_ptb.add_handler(draft_vote_recive_handler)

sync_ptb.add_handler(message_dispatch_handler)

