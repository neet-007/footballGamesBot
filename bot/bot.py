from telegram.ext import Application
from dotenv import load_dotenv
from os import getenv
from sys import exit
from bot.shared_handlers import RateLimitHandler, chack_rate_limit_handler, error_handler
from games.draft_handlers import random_team_draft_game_callback_handler, make_game_test_handler, join_game_test_handler, start_game_test_handler, set_game_test_handler, position_draft_message_test_handler, cancel_game_test_handler, vote_recive_poll_answer_test_handler, end_vote_game_test_handler, join_game_callback_test_handler, start_vote_game_test_handler
from games.guess_the_player_handlers import guess_the_player_start_game_command_handler, guess_the_player_join_game_command_handler, guess_the_player_new_game_command_handler,guess_the_player_ask_question_command_handler, guess_the_player_cancel_game_command_handler, guess_the_player_join_game_callback_handler, guess_the_player_leave_game_command_handler, guess_thE_player_get_questions_command_handler, handle_dispatch_messages, new_db_handler, guess_the_player_dispatch_handler

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

ptb.add_error_handler(error_handler)
ptb.add_handler(RateLimitHandler(chack_rate_limit_handler))
ptb.add_handler(new_db_handler)
#ptb.add_handler(guess_the_player_new_game_command_handler)
#ptb.add_handler(guess_the_player_join_game_command_handler)
#ptb.add_handler(guess_the_player_join_game_callback_handler)
#ptb.add_handler(guess_the_player_start_game_command_handler)
#ptb.add_handler(guess_the_player_ask_question_command_handler)
#ptb.add_handler(guess_the_player_answer_question_command_handler)
#ptb.add_handler(guess_the_player_proccess_answer_command_handler)
#ptb.add_handler(guess_the_player_cancel_game_command_handler)
#ptb.add_handler(guess_the_player_start_round_command_handler)
#ptb.add_handler(guess_the_player_leave_game_command_handler)
#ptb.add_handler(guess_thE_player_get_questions_command_handler)
#ptb.add_handler(guess_the_player_dispatch_handler)

ptb.add_handler(make_game_test_handler)
ptb.add_handler(join_game_test_handler)
ptb.add_handler(start_game_test_handler)
ptb.add_handler(set_game_test_handler)
ptb.add_handler(cancel_game_test_handler)
ptb.add_handler(end_vote_game_test_handler)
ptb.add_handler(start_vote_game_test_handler)
ptb.add_handler(vote_recive_poll_answer_test_handler)
ptb.add_handler(join_game_callback_test_handler)
ptb.add_handler(random_team_draft_game_callback_handler)
ptb.add_handler(position_draft_message_test_handler)
#ptb.add_handler(MessageHandler((telegram.ext.filters.TEXT & ~ telegram.ext.filters.COMMAND), handle_dispatch_messages))

sync_ptb.add_handler(new_db_handler)
#sync_ptb.add_handler(guess_the_player_new_game_command_handler)
#sync_ptb.add_handler(guess_the_player_join_game_command_handler)
#sync_ptb.add_handler(guess_the_player_join_game_callback_handler)
#sync_ptb.add_handler(guess_the_player_start_game_command_handler)
#sync_ptb.add_handler(guess_the_player_ask_question_command_handler)
#sync_ptb.add_handler(guess_the_player_answer_question_command_handler)
#sync_ptb.add_handler(guess_the_player_proccess_answer_command_handler)
#sync_ptb.add_handler(guess_the_player_cancel_game_command_handler)
#sync_ptb.add_handler(guess_the_player_start_round_command_handler)
#sync_ptb.add_handler(guess_the_player_leave_game_command_handler)
#sync_ptb.add_handler(guess_thE_player_get_questions_command_handler)
#sync_ptb.add_handler(guess_the_player_dispatch_handler)

sync_ptb.add_handler(make_game_test_handler)
sync_ptb.add_handler(join_game_test_handler)
sync_ptb.add_handler(start_game_test_handler)
sync_ptb.add_handler(set_game_test_handler)
sync_ptb.add_handler(cancel_game_test_handler)
sync_ptb.add_handler(end_vote_game_test_handler)
sync_ptb.add_handler(start_vote_game_test_handler)
sync_ptb.add_handler(vote_recive_poll_answer_test_handler)
sync_ptb.add_handler(join_game_callback_test_handler)
sync_ptb.add_handler(random_team_draft_game_callback_handler)
sync_ptb.add_handler(position_draft_message_test_handler)
#sync_ptb.add_handler(MessageHandler((telegram.ext.filters.TEXT & ~ telegram.ext.filters.COMMAND), handle_dispatch_messages))


