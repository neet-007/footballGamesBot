from sqlalchemy import delete, func, insert, or_, select, update
from db.connection import get_session
from db.models import AskedQuestions, Game, GuessThePlayer, GuessThePlayerPlayer, guess_the_player_guess_the_player_player_association
from utils.jaro_winkler import jaro_winkler_similarity

session = get_session()

def check_guess_the_player(chat_id:int):
    try:
        with session.begin():
            game = session.query(GuessThePlayer.state, GuessThePlayer.num_players).filter(GuessThePlayer.chat_id == chat_id).first()
            if not game:
                return False, "no game found", -1, -1

            return True, "", game[0], game[1]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", -1, -1

def new_game_guess_the_player(chat_id:int):
    try:
        with session.begin():
            game = session.query(Game).filter(Game.chat_id == chat_id).first()
            if game:
                return False, "a game has started"

            guess_the_player = GuessThePlayer(
                chat_id=chat_id,
            )
            game = Game(
                chat_id=chat_id,
            )

            session.add_all([game, guess_the_player])
            return True, ""
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception"

def join_game_guess_the_player(chat_id:int, player_id:int):
    try:
        with session.begin():
            guess_the_player = session.query(GuessThePlayer).filter(GuessThePlayer.chat_id == chat_id).first()
            if not guess_the_player:
                return False, "no game"

            if guess_the_player.state != 0:
                return False, "game has started"

            player_db = session.query(GuessThePlayerPlayer).filter(GuessThePlayerPlayer.player_id == player_id,
                                                                   GuessThePlayerPlayer.guess_the_player_id == chat_id).first()
            if player_db:
                return False, "player already in game"

            player_db = GuessThePlayerPlayer(
                player_id=player_id,
                guess_the_player_id=chat_id,
            )
            session.add(player_db)

            guess_the_player.num_players += 1

            return True, ""
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception"

def start_game_guess_the_player(chat_id:int):
    try:
        with session.begin():
            guess_the_player = session.query(GuessThePlayer).filter(GuessThePlayer.chat_id == chat_id).first()
            if not guess_the_player:
                return False, "no game error", -1

            if guess_the_player.state != 0:
                return False, "state error", -1

            player_ids = (
                    session.query(GuessThePlayerPlayer)
                    .with_entities(GuessThePlayerPlayer.id)
                    .filter(GuessThePlayerPlayer.guess_the_player_id == guess_the_player.chat_id)
                    .order_by(GuessThePlayerPlayer.time_join.asc())  
                    .all()
            )

            if not player_ids:
                (
                    session.query(Game)
                    .filter(Game.chat_id == chat_id)
                    .delete()
                )
                session.delete(guess_the_player)
                session.execute(
                     delete(guess_the_player_guess_the_player_player_association).where(
                            guess_the_player_guess_the_player_player_association.c.guess_the_player_id == chat_id,
                    )
                )
                return False, "no players associated with the game", -1

            num_players = len(player_ids)

            if num_players < 2 or num_players != guess_the_player.num_players:
                (
                    session.query(Game)
                    .filter(Game.chat_id == chat_id)
                    .delete()
                )
                session.delete(guess_the_player)
                session.execute(
                     delete(guess_the_player_guess_the_player_player_association).where(
                            guess_the_player_guess_the_player_player_association.c.guess_the_player_id == chat_id,
                    )
                )
                return False, "number of players is less than 2 or not as expected", -1

            player_id = player_ids[0][0]
            guess_the_player.current_player_id = player_id

            guess_the_player.state = 1
            curr_player = (
                session.execute(
                    update(GuessThePlayerPlayer)
                    .where(GuessThePlayerPlayer.id == guess_the_player.current_player_id)
                    .values(picked=True)
                    .returning(GuessThePlayerPlayer.player_id)
                )
            ).fetchone()

            if not curr_player:
                return False, "player not in game", -1

            session.execute(
                insert(guess_the_player_guess_the_player_player_association).values(
                    guess_the_player_id=guess_the_player.chat_id,
                    guess_the_player_player_id=guess_the_player.current_player_id,
                    guess_the_player_player_player_id=curr_player[0],
                    time_created=func.now()
                )
            )
    
            return True, "", curr_player[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", -1

def start_round_guess_the_player(player_id:int, curr_hints:list[str], curr_answer:str):
    try:
        with session.begin():
            result = session.execute(
                select(
                    guess_the_player_guess_the_player_player_association.c.id,
                    guess_the_player_guess_the_player_player_association.c.guess_the_player_id,
                )
                .where(
                    guess_the_player_guess_the_player_player_association.c.guess_the_player_player_player_id == player_id
                )
                .order_by(
                    guess_the_player_guess_the_player_player_association.c.time_created.asc()
                )
                .limit(1)
            ).first()
            
            if not result:
                return False, "player not found or not in game", [], -1

            id, chat_id = result

            guess_the_player = session.query(GuessThePlayer).filter(GuessThePlayer.chat_id == chat_id).first()
            if not guess_the_player:
                return False, "no game found", [], -1

            if guess_the_player.state != 1 and guess_the_player.state != 3:
                return False, "state error", [], -1
            if len(curr_hints) != 3:
                return False, "num hints error", [], -1
            curr_player_id = (
                session.query(GuessThePlayerPlayer.player_id)
                .filter(GuessThePlayerPlayer.id == guess_the_player.current_player_id)
                .first()
            )
            if not curr_player_id:
                return False, "player not in game", [], -1
            if curr_player_id[0] != player_id:
                return False, "curr player error", [], -1
            if curr_hints == ["", "", ""] or curr_answer == "":
                return False, "empty inputs", [], -1

            curr_hints = [hint.strip().capitalize() for hint in curr_hints]
            guess_the_player.curr_answer = curr_answer.strip().lower()
            guess_the_player.curr_hints = curr_hints
            guess_the_player.state = 2

            session.execute(
                delete(guess_the_player_guess_the_player_player_association)
                .where(guess_the_player_guess_the_player_player_association.c.id == id)
            )

            return True, "", curr_hints, chat_id
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", [], -1

def ask_question_guess_the_player(chat_id:int, player_id:int, question:str):
    try:
        with session.begin():
            guess_the_player = session.query(GuessThePlayer).filter(GuessThePlayer.chat_id == chat_id).first()
            if not guess_the_player:
                return False, "no game found", -1

            if guess_the_player.state != 2:
                return False, "state error", -1

            if guess_the_player.asking_player_id != None:
                return False, "there is askin player error", -1

            if guess_the_player.current_player_id == player_id:
                return False, "curr player error", -1

            player = (
                    session.query(GuessThePlayerPlayer)
                    .filter(GuessThePlayerPlayer.player_id == player_id,
                            GuessThePlayerPlayer.guess_the_player_id == chat_id)
                    .first()
            )

            if not player:
                return False, "player not in game", -1

            if player.questions <= 0:
                return False, "no questions", -1

            guess_the_player.curr_question = question.lower().strip()
            guess_the_player.asking_player_id = player.id
            curr_player = (
                    session.query(GuessThePlayerPlayer.player_id)
                    .filter(GuessThePlayerPlayer.id == guess_the_player.current_player_id)
                    .first()
            )
            if not curr_player:
                return False, "player not in game", -1

            return True, "", curr_player[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", -1

def answer_question_guess_the_player(chat_id:int, player_id:int, player_asked_id:int, question:str, answer:str):
    try:
        with session.begin():
            guess_the_player = session.query(GuessThePlayer).filter(GuessThePlayer.chat_id == chat_id).first()
            if not guess_the_player:
                return False, "game not found"

            if guess_the_player.state != 2:
                return False, "state error"

            curr_players = (
                session.query(GuessThePlayerPlayer)
                .filter(or_(GuessThePlayerPlayer.id == guess_the_player.asking_player_id,
                            GuessThePlayerPlayer.id == guess_the_player.current_player_id))
                .all()
            )
            asking_player = None
            curr_player = None
            if not curr_players[0] or not curr_players[1]:
                return False, "players not in game"
            if curr_players[0].player_id == player_asked_id:
                asking_player = curr_players[0]
                curr_player = curr_players[1]
            else:
                asking_player = curr_players[1]
                curr_player = curr_players[0]

            question = question.lower().strip()
            if guess_the_player.curr_question != question:
                return False, "not the question"

            if curr_player.player_id != player_id:
                return False, "curr player error"
    
            question_ = AskedQuestions(
                question=question,
                answer=answer.lower().strip(),
                guess_the_player_id=chat_id
            )

            asking_player.questions -= 1

            guess_the_player.asking_player_id = None
            guess_the_player.curr_question = ""

            session.add(question_)
            return True, ""
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception"

def proccess_answer_guess_the_player(chat_id:int, player_id:int, answer:str):
    try:
        with session.begin():
            guess_the_player = session.query(GuessThePlayer).filter(GuessThePlayer.chat_id == chat_id).first()
            if not guess_the_player:
                return False, "game not found"

            if guess_the_player.state != 2:
                return False, "state error"

            if guess_the_player.current_player_id == player_id:
                return False, "curr player error"

            player_ = (
                    session.query(GuessThePlayerPlayer)
                    .filter(GuessThePlayerPlayer.player_id == player_id,
                            GuessThePlayerPlayer.guess_the_player_id == chat_id)
                    .first()
            )
            if not player_:
                return False, "player not in game"
                
            if player_.muted:
                return False, "muted player"

            player_.answers -= 1
            if player_.answers == 0:
                player_.muted = True

            score = jaro_winkler_similarity(answer.strip().lower(), guess_the_player.curr_answer)
            if (len(answer.lower().strip()) > 10 and score > 0.85) or (len(answer.lower().strip()) <= 10 and score > 0.92):
                guess_the_player.state = 3
                guess_the_player.winning_player_id = player_.id
                return True, "correct"

            muted_players_count = (
                session.query(func.count(GuessThePlayerPlayer.id)) 
                .filter(
                    GuessThePlayerPlayer.guess_the_player_id == chat_id,
                    GuessThePlayerPlayer.muted == True
                )
                .scalar()
            )
            if muted_players_count == guess_the_player.num_players - 1:
                guess_the_player.state = 3
                guess_the_player.winning_player_id = None
                return True, "all players muted"

            return True, "false"
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception"

def end_round_guess_the_player(chat_id:int):
    try:
        with session.begin():
            guess_the_player = session.query(GuessThePlayer).filter(GuessThePlayer.chat_id == chat_id).first()
            if not guess_the_player:
                return False, "game not found", -1

            if guess_the_player.state != 3:
                return False, "state error", -1

            if guess_the_player.winning_player_id == None:
                curr_player = (
                        session.query(GuessThePlayerPlayer)
                        .filter(GuessThePlayerPlayer.guess_the_player_id == chat_id,
                                GuessThePlayerPlayer.id == guess_the_player.current_player_id)
                        .first()
                )
                if not curr_player:
                    return False, "player not in game", -1
                curr_player.score += 1
            else: 
                winning_player = (
                        session.query(GuessThePlayerPlayer)
                        .filter(GuessThePlayerPlayer.guess_the_player_id == chat_id,
                                GuessThePlayerPlayer.id == guess_the_player.winning_player_id)
                        .first()
                )
                if not winning_player:
                    return False, "player not in game", -1

                winning_player.score += 1

            guess_the_player.curr_hints = ["","","",]

            guess_the_player.curr_answer = ""
            guess_the_player.winning_player_id = None
            (
                session.query(GuessThePlayerPlayer).
                filter(GuessThePlayerPlayer.guess_the_player_id == chat_id)
                .update(
                    {
                        "muted": False,
                        "questions": 3,
                        "answers": 2
                    }
                )
            )
            (
                session.query(AskedQuestions)
                .filter(AskedQuestions.guess_the_player_id == chat_id)
                .delete()
            )
            next_player = (
                    session.query(GuessThePlayerPlayer.id, GuessThePlayerPlayer.player_id)
                    .filter(GuessThePlayerPlayer.guess_the_player_id == chat_id,
                            GuessThePlayerPlayer.picked == False)
                    .order_by(GuessThePlayerPlayer.time_join.asc())  
                    .first()
            )

            guess_the_player.state = 3

            if not next_player:
                return True, "game end", -1

            (
                session.query(GuessThePlayerPlayer)
                .filter(GuessThePlayerPlayer.id == next_player[0])
                .update({"picked":True})
            )

            guess_the_player.current_player_id = next_player[0]

            session.execute(
                insert(guess_the_player_guess_the_player_player_association).values(
                    guess_the_player_id=guess_the_player.chat_id,
                    guess_the_player_player_id=guess_the_player.current_player_id,
                    guess_the_player_player_player_id=next_player[1],
                    time_created=func.now()
                )
            )


            return True, "round end", next_player[1]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", -1

def end_game_guess_the_player(chat_id:int):
    try:
        with session.begin():
            game = session.query(Game).filter(Game.chat_id == chat_id).first()
            guess_the_player = session.query(GuessThePlayer).filter(GuessThePlayer.chat_id == chat_id).first()
            if not guess_the_player:
                return False, "game not found", {}, []

            players = (
                session.query(GuessThePlayerPlayer)
                .filter(GuessThePlayerPlayer.guess_the_player_id == chat_id)
                .all()
            )
        
            if not players:
                return False, "players not found", {}, []

            scores = {player.player_id:player.score for player in players}
            winners = []
            max_score = float('-inf')
            for player, score in scores.items():
                if score == max_score:
                    winners.append(player)
                if score > max_score:
                    max_score = score
                    winners = []
                    winners.append(player)

            session.delete(game)
            session.delete(guess_the_player)
            return True, "", scores, winners
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", {}, []

def cancel_game_guess_the_player(chat_id:int):
    try:
        with session.begin():
            game = session.query(Game).filter(Game.chat_id == chat_id).first()
            guess_the_player = session.query(GuessThePlayer).filter(GuessThePlayer.chat_id == chat_id).first()
            if not guess_the_player or not game:
                return False, "no game found"

            session.delete(game)
            session.delete(guess_the_player)
            return True, ""
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception"

def leave_game_guess_the_player(chat_id:int, player_id:int):
    try:
        with session.begin():
            guess_the_player = session.query(GuessThePlayer).filter(GuessThePlayer.chat_id == chat_id).first()
            if not guess_the_player:
                return False, "game not found", -1
    
            player = (
                session.query(GuessThePlayerPlayer)
                .filter(GuessThePlayerPlayer.player_id == player_id,
                        GuessThePlayerPlayer.guess_the_player_id == chat_id)
                .first()
            )

            if not player:
                return False, "player not in game", -1

            if guess_the_player.num_players <= 2:
                (
                    session.query(Game)
                    .filter(Game.chat_id == chat_id)
                    .delete()
                )
                session.delete(guess_the_player)
            if guess_the_player.current_player_id == player.id:
                next_player = (
                        session.query(GuessThePlayerPlayer.id, GuessThePlayerPlayer.player_id)
                        .filter(GuessThePlayerPlayer.guess_the_player_id == chat_id,
                                GuessThePlayerPlayer.picked == False)
                        .order_by(GuessThePlayerPlayer.time_join.asc())  
                        .first()
                )
                if not next_player:
                    return False, "game end", -1

                session.delete(player)
                guess_the_player.current_player_id = next_player[0]
                guess_the_player.state = 2
                guess_the_player.curr_hints = ["", "", ""]
                guess_the_player.curr_answer = ""
                (
                    session.query(GuessThePlayerPlayer).
                    filter(GuessThePlayerPlayer.guess_the_player_id == chat_id)
                    .update(
                        {
                            "muted": False,
                            "questions": 3,
                            "answers": 2
                        }
                    )
                )
                (
                    session.query(AskedQuestions)
                    .filter(AskedQuestions.guess_the_player_id == chat_id)
                    .delete()
                )

                guess_the_player.state = 3
                session.delete(player)
                return True, "new curr player", next_player[1]
            if guess_the_player.asking_player_id == player.id:
                guess_the_player.asking_player_id = None

            session.delete(player)
            return True, "", -1
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", -1

def get_asked_questions_guess_the_player(chat_id:int):
    try:
        with session.begin():
            questions = (
                session.query(AskedQuestions)
                .filter(AskedQuestions.guess_the_player_id == chat_id)
                .all()
            )
            if not questions:
                return False, "questions not found", {}

            return True, "", {q.question:q.answer for q in questions}
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", {}
