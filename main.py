from dotenv import load_dotenv
from os import getenv
import telegram
import telegram.ext
from telegram.ext._handlers.messagehandler import MessageHandler
from draft import handle_draft_add_pos, start_draft_game_command_handler,  new_draft_game_command_handler, join_draft_game_command_handler, set_draft_game_state_command_handler, cancel_draft_game_command_handler, vote_recive_poll_answer_handler, position_draft_message_handler, join_draft_game_callback_handler, random_team_draft_game_callback_handler
from guess_the_player import guess_the_player_start_game_command_handler, guess_the_player_join_game_command_handler, guess_the_player_new_game_command_handler,guess_the_player_ask_question_command_handler, guess_the_player_answer_question_command_handler, guess_the_player_proccess_answer_command_handler, guess_the_player_cancel_game_command_handler, guess_the_player_join_game_callback_handler, guess_the_player_start_round_command_handler, guess_the_player_leave_game_command_handler, guess_thE_player_get_questions_command_handler, handle_guess_the_player_answer_question_command, handle_guess_the_player_ask_question_command, handle_guess_the_player_proccess_answer_command, handle_guess_the_player_start_round
from shared import Draft, GuessThePlayer, Wilty, games

load_dotenv()

BOT_API_TOKEN = getenv("BOT_API_TOKEN")


async def handle_start(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not update.message or context == None:
        return

    await update.message.reply_text("")

async def handle_dispatch_messages(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    print("dispatch")
    if not update.message or not update.message.text or not update.effective_chat or not update.effective_user:
        return

    print("if passed")
    chat_id = update.effective_chat.id
    if update.effective_chat.type == "private":
        chat_id = context.bot_data.get(update.effective_user.id, None)
        if chat_id == None:
            return
    game = games.get(chat_id, None)
    if game == None:
        return

    print("game found")
    if isinstance(game, Draft):
        print("is draft")
        return await handle_draft_add_pos(update, context)
    if isinstance(game, GuessThePlayer):
        print("is guess the player")
        if update.effective_chat.type == "private":
            print("private")
            return await handle_guess_the_player_start_round(update, context)
        if update.message.reply_to_message:
            print("is reply")
            return await handle_guess_the_player_answer_question_command(update, context)
        else:
            print("else")
            return await handle_guess_the_player_proccess_answer_command(update, context)
    if isinstance(game, Wilty):
        print("wilty")
        return
    else:
        print("should be eror")
        return

def main():
    if not BOT_API_TOKEN:
        return

    application = telegram.ext.Application.builder().token(BOT_API_TOKEN).build()
    application.add_handler(guess_the_player_new_game_command_handler)
    application.add_handler(guess_the_player_join_game_command_handler)
    application.add_handler(guess_the_player_join_game_callback_handler)
    application.add_handler(guess_the_player_start_game_command_handler)
    application.add_handler(guess_the_player_ask_question_command_handler)
    #application.add_handler(guess_the_player_answer_question_command_handler)
    #application.add_handler(guess_the_player_proccess_answer_command_handler)
    application.add_handler(guess_the_player_cancel_game_command_handler)
    #application.add_handler(guess_the_player_start_round_command_handler)
    application.add_handler(guess_the_player_leave_game_command_handler)
    application.add_handler(guess_thE_player_get_questions_command_handler)

    application.add_handler(new_draft_game_command_handler)
    application.add_handler(join_draft_game_command_handler)
    application.add_handler(join_draft_game_callback_handler)
    application.add_handler(start_draft_game_command_handler)
    #application.add_handler(position_draft_message_handler)
    application.add_handler(set_draft_game_state_command_handler)
    application.add_handler(random_team_draft_game_callback_handler)
    application.add_handler(cancel_draft_game_command_handler)
    application.add_handler(vote_recive_poll_answer_handler)
    
    application.add_handler(MessageHandler((telegram.ext.filters.TEXT & ~ telegram.ext.filters.COMMAND), handle_dispatch_messages))

    application.run_polling(allowed_updates=telegram.Update.ALL_TYPES)

if __name__ == "__main__":
    main()
