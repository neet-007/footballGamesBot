from sqlalchemy import delete, exists, func, insert, or_, select, update
from sqlalchemy.orm import Session, query
from db.models import AskedQuestions, Game, GuessThePlayer, GuessThePlayerPlayer, guess_the_player_guess_the_player_player_association
from utils.jaro_winkler import jaro_winkler_similarity

def check_guess_the_player(chat_id:int, session:Session):
    try:
        with session.begin():
            game = session.query(GuessThePlayer.state, GuessThePlayer.num_players).filter(GuessThePlayer.chat_id == chat_id).first()
            if not game:
                return False, "no game found", -1, -1

            return True, "", game[0], game[1]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", -1, -1

def new_game_guess_the_player(chat_id:int, num_rounds:int | None, session:Session):
    try:
        with session.begin():
            if session.query(exists().where(Game.chat_id == chat_id)).scalar():
                return False, "a game has started"

            if num_rounds:
                if num_rounds < 1:
                    return False, "num of rounds less than 1"
                session.add_all([Game(chat_id=chat_id), GuessThePlayer(chat_id=chat_id,num_rounds=num_rounds)])
            else:
                session.add_all([Game(chat_id=chat_id), GuessThePlayer(chat_id=chat_id)])

            return True, ""
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception"

def join_game_guess_the_player(chat_id:int, player_id:int, session:Session):
    try:
        with session.begin():
            guess_the_player_state = session.query(GuessThePlayer.state).filter(GuessThePlayer.chat_id == chat_id).first()
            if not guess_the_player_state:
                return False, "no game"

            if guess_the_player_state[0] != 0:
                return False, "state error"

            if session.query(exists().where(GuessThePlayerPlayer.player_id == player_id, GuessThePlayerPlayer.guess_the_player_id == chat_id)).scalar():
                return False, "player already in game"

            session.add(GuessThePlayerPlayer(player_id=player_id, guess_the_player_id=chat_id))

            num_players = (
                session.execute(
                    update(GuessThePlayer)
                    .where(GuessThePlayer.chat_id == chat_id)
                    .values(num_players=GuessThePlayer.num_players + 1)
                    .returning(GuessThePlayer.num_players)
                )
            ).fetchone()

            return True, ""
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception"

def start_game_guess_the_player(chat_id:int, session:Session):
    try:
        with session.begin():
            guess_the_player_state = session.query(GuessThePlayer.state).filter(GuessThePlayer.chat_id == chat_id).first()
            if not guess_the_player_state:
                return False, "no game error", -1

            if guess_the_player_state[0] != 0:
                return False, "state error", -1

            player_id = (
                    session.query(GuessThePlayerPlayer.id)
                    .filter(GuessThePlayerPlayer.guess_the_player_id == chat_id)
                    .order_by(GuessThePlayerPlayer.time_join.asc())  
                    .first()
            )

            if not player_id:
                (
                    session.query(Game)
                    .filter(Game.chat_id == chat_id)
                    .delete()
                )
                (
                    session.query(GuessThePlayer)
                    .filter(GuessThePlayer.chat_id == chat_id)
                    .delete()
                )
                session.execute(
                     delete(guess_the_player_guess_the_player_player_association).where(
                            guess_the_player_guess_the_player_player_association.c.guess_the_player_id == chat_id,
                    )
                )
                return False, "no players associated with the game", -1

            num_players = (
                session.query(GuessThePlayerPlayer.id)
                .filter(GuessThePlayerPlayer.guess_the_player_id == chat_id)
            ).count() 

            if num_players < 2:
                (
                    session.query(Game)
                    .filter(Game.chat_id == chat_id)
                    .delete()
                )
                (
                    session.query(GuessThePlayer)
                    .filter(GuessThePlayer.chat_id == chat_id)
                    .delete()
                )
                session.execute(
                     delete(guess_the_player_guess_the_player_player_association).where(
                            guess_the_player_guess_the_player_player_association.c.guess_the_player_id == chat_id,
                    )
                )
                return False, "number of players is less than 2 or not as expected", -1

            curr_player = (
                session.execute(
                    update(GuessThePlayerPlayer)
                    .where(GuessThePlayerPlayer.id == player_id[0])
                    .values(picked=True)
                    .returning(GuessThePlayerPlayer.player_id)
                )
            ).fetchone()

            if not curr_player:
                return False, "player not in game", -1

            session.execute(
                insert(guess_the_player_guess_the_player_player_association).values(
                    guess_the_player_id=chat_id,
                    guess_the_player_player_id=player_id[0],
                    guess_the_player_player_player_id=curr_player[0],
                    time_created=func.now()
                )
            )
    
            (
                session.query(GuessThePlayer)
                .filter(GuessThePlayer.chat_id == chat_id)
                .update({GuessThePlayer.current_player_id:player_id[0],
                         GuessThePlayer.state:1,
                         GuessThePlayer.num_players:num_players})
            )

            return True, "", curr_player[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", -1

def start_round_guess_the_player(player_id:int, curr_hints:list[str], curr_answer:str, session:Session):
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
                .with_for_update(read=True)
                .limit(1)
            ).first()
            
            if not result:
                return False, "player not found or not in game", [], -1

            id, chat_id = result

            guess_the_player_state_curr_player = (
                    session.query(GuessThePlayer.state, GuessThePlayer.current_player_id)
                    .filter(GuessThePlayer.chat_id == chat_id)
                    .first()
            )
            if not guess_the_player_state_curr_player:
                return False, "no game found", [], -1

            if guess_the_player_state_curr_player[0] != 1:
                return False, "state error", [], -1
            if len(curr_hints) != 3:
                return False, "num hints error", [], -1
            if not session.query(exists().where(GuessThePlayerPlayer.id == guess_the_player_state_curr_player[1], 
                                                GuessThePlayerPlayer.player_id == player_id)).scalar():

                return False, "player not in game", [], -1

            if curr_hints == ["", "", ""] or curr_answer == "":
                return False, "empty inputs", [], -1

            curr_hints = [hint.strip().capitalize() for hint in curr_hints]
            (
                session.query(GuessThePlayer)
                .filter(GuessThePlayer.chat_id == chat_id)
                .update({GuessThePlayer.curr_answer:curr_answer.strip().lower(),
                          GuessThePlayer.curr_hints:curr_hints,
                          GuessThePlayer.state:2})
            )

            session.execute(
                delete(guess_the_player_guess_the_player_player_association)
                .where(guess_the_player_guess_the_player_player_association.c.id == id)
            )

            return True, "", curr_hints, chat_id
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", [], -1

def ask_question_guess_the_player(chat_id:int, player_id:int, question:str, session:Session):
    try:
        with session.begin():
            #state, askingplayer, current player
            guess_the_player_state_asking_player_curr_player = (
                session.query(GuessThePlayer.state, GuessThePlayer.asking_player_id, GuessThePlayer.current_player_id)
                .filter(GuessThePlayer.chat_id == chat_id)
                .first()
            )
            if not guess_the_player_state_asking_player_curr_player:
                return False, "no game found", -1

            if guess_the_player_state_asking_player_curr_player[0] != 2:
                return False, "state error", -1

            if guess_the_player_state_asking_player_curr_player[1] != None:
                return False, "there is askin player error", -1

            if guess_the_player_state_asking_player_curr_player[2] == player_id:
                return False, "curr player error", -1

            player_id_questions = (
                    session.query(GuessThePlayerPlayer.id, GuessThePlayerPlayer.questions)
                    .filter(GuessThePlayerPlayer.player_id == player_id,
                            GuessThePlayerPlayer.guess_the_player_id == chat_id)
                    .first()
            )

            if not player_id_questions:
                return False, "player not in game", -1

            if player_id_questions[1] <= 0:
                return False, "no questions", -1

            (
                session.query(GuessThePlayer)
                .filter(GuessThePlayer.chat_id == chat_id)
                .update({GuessThePlayer.curr_question:question.lower().strip(),
                         GuessThePlayer.asking_player_id:player_id_questions[0]})
            )
            curr_player = (
                    session.query(GuessThePlayerPlayer.player_id)
                    .filter(GuessThePlayerPlayer.id == guess_the_player_state_asking_player_curr_player[2])
                    .first()
            )
            if not curr_player:
                return False, "player not in game", -1

            return True, "", curr_player[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", -1

def answer_question_guess_the_player(chat_id:int, player_id:int, answer:str, session:Session):
    try:
        with session.begin():
            guess_the_player_state_asking_player_current_player_curr_question = (
                    session.query(GuessThePlayer.state,
                                  GuessThePlayer.asking_player_id,
                                  GuessThePlayer.current_player_id,
                                  GuessThePlayer.curr_question)
                           .filter(GuessThePlayer.chat_id == chat_id)
                           .first()
            )
            if not guess_the_player_state_asking_player_current_player_curr_question:
                return False, "game not found", 0, 0

            if guess_the_player_state_asking_player_current_player_curr_question[0] != 2:
                return False, "state error", 0, 0

            curr_player = (
                session.query(GuessThePlayerPlayer.player_id)
                .filter(GuessThePlayerPlayer.id == guess_the_player_state_asking_player_current_player_curr_question[2])
                .first()
            )

            if not curr_player:
                return False, "players not in game", 0, 0

            if curr_player[0] != player_id:
                return False, "curr player error", 0, 0
    
            session.add(AskedQuestions(
                    question=guess_the_player_state_asking_player_current_player_curr_question[3],
                    answer=answer.lower().strip(),
                    guess_the_player_id=chat_id
                )
            )

            player_player_id_questions = (
                session.execute(
                update(GuessThePlayerPlayer)
                .where(GuessThePlayerPlayer.id == guess_the_player_state_asking_player_current_player_curr_question[1])
                .values(questions=GuessThePlayerPlayer.questions - 1)
                .returning(GuessThePlayerPlayer.questions, GuessThePlayerPlayer.player_id)
                )
            ).fetchone()

            (
                session.query(GuessThePlayer)
                .filter(GuessThePlayer.chat_id == chat_id)
                .update({GuessThePlayer.asking_player_id:None,
                         GuessThePlayer.curr_question:""})
            )

            if not player_player_id_questions:
                return False, "state error", 0, 0

            return True, "", player_player_id_questions[0], player_player_id_questions[1]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", 0, 0

def proccess_answer_guess_the_player(chat_id:int, player_id:int, answer:str, session:Session):
    try:
        with session.begin():
            guess_the_player_state_curr_player_curr_answer = (
                session.query(GuessThePlayer.state,
                              GuessThePlayer.current_player_id,
                              GuessThePlayer.curr_answer,
                              GuessThePlayer.num_players)
                        .filter(GuessThePlayer.chat_id == chat_id)
                        .first()
            )
            if not guess_the_player_state_curr_player_curr_answer:
                return False, "game not found"

            if guess_the_player_state_curr_player_curr_answer[0] != 2:
                return False, "state error"

            if guess_the_player_state_curr_player_curr_answer[1] == player_id:
                return False, "curr player error"

            player_id_muted = (
                    session.query(GuessThePlayerPlayer.id,
                                  GuessThePlayerPlayer.muted)
                    .filter(GuessThePlayerPlayer.player_id == player_id,
                            GuessThePlayerPlayer.guess_the_player_id == chat_id)
                    .first()
            )
            if not player_id_muted:
                return False, "player not in game"
                
            if player_id_muted[1]:
                return False, "muted player"

            answers = (
                session.execute(
                    update(GuessThePlayerPlayer)
                    .where(GuessThePlayerPlayer.id == player_id_muted[0])
                    .values(answers=GuessThePlayerPlayer.answers - 1)
                    .returning(GuessThePlayerPlayer.answers)
                )
            ).fetchone()

            if not answers:
                return False, "game error"

            if answers[0] == 0:
                (
                    session.execute(
                        update(GuessThePlayerPlayer)
                        .where(GuessThePlayerPlayer.id == player_id_muted[0])
                        .values(muted=True)
                    )
                )
                session.flush()

            score = jaro_winkler_similarity(answer.strip().lower(), guess_the_player_state_curr_player_curr_answer[2])
            if (len(answer.lower().strip()) > 10 and score > 0.85) or (len(answer.lower().strip()) <= 10 and score > 0.92):
                (
                    session.query(GuessThePlayer)
                    .filter(GuessThePlayer.chat_id == chat_id)
                    .update({GuessThePlayer.state:3,
                             GuessThePlayer.winning_player_id:player_id_muted[0]})
                )
                return True, "correct"

            muted_players_count = (
                session.query(func.count(GuessThePlayerPlayer.id)) 
                .filter(
                    GuessThePlayerPlayer.guess_the_player_id == chat_id,
                    GuessThePlayerPlayer.muted == True
                )
                .scalar()
            )

            if muted_players_count == guess_the_player_state_curr_player_curr_answer[3] - 1:
                (
                    session.query(GuessThePlayer)
                    .filter(GuessThePlayer.chat_id == chat_id)
                    .update({GuessThePlayer.state:3,
                             GuessThePlayer.winning_player_id:None})
                )
                return True, "all players muted"

            return True, "false"
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception"

def end_round_guess_the_player(chat_id:int, session:Session):
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

            guess_the_player.state = 1

            if not next_player:
                if guess_the_player.curr_round < guess_the_player.num_rounds:
                    (
                        session.query(GuessThePlayerPlayer).
                        filter(GuessThePlayerPlayer.guess_the_player_id == chat_id)
                        .update(
                            {
                                "muted": False,
                                "questions": 3,
                                "answers": 2,
                                "picked":False,
                            }
                        )
                    )
                
                    session.flush()

                    next_player = (
                            session.query(GuessThePlayerPlayer.id, GuessThePlayerPlayer.player_id)
                            .filter(GuessThePlayerPlayer.guess_the_player_id == chat_id,
                                    GuessThePlayerPlayer.picked == False)
                            .order_by(GuessThePlayerPlayer.time_join.asc())  
                            .first()
                    )
                    if not next_player:
                        return False, "player not in game", -1
                    
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
                    guess_the_player.curr_round += 1
                    guess_the_player.state = 1
                    return True, "new round", next_player[1]

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

def end_game_guess_the_player(chat_id:int, session:Session):
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

def cancel_game_guess_the_player(chat_id:int, session:Session):
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

def leave_game_guess_the_player(chat_id:int, player_id:int, session:Session):
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

            player_intance_id = player.id
            (
                session.query(GuessThePlayerPlayer)
                .filter(GuessThePlayerPlayer.id == player.id)
                .delete()
            )
            num_players = guess_the_player.num_players - 1
            guess_the_player.num_players = num_players
    
            if guess_the_player.state == 0:
                return True, "", -1

            if num_players < 2:
                return True, "end game", -1

            if guess_the_player.asking_player_id == player_intance_id:
                guess_the_player.asking_player_id = None

            elif guess_the_player.current_player_id == player.id:
                next_player = (
                        session.query(GuessThePlayerPlayer.id, GuessThePlayerPlayer.player_id)
                        .filter(GuessThePlayerPlayer.guess_the_player_id == chat_id,
                                GuessThePlayerPlayer.picked == False,
                                GuessThePlayerPlayer.id != player_intance_id)
                        .order_by(GuessThePlayerPlayer.time_join.asc())  
                        .first()
                )
                if not next_player:
                    return True, "end round", -1

                guess_the_player.current_player_id = next_player[0]
                guess_the_player.state = 3
                guess_the_player.curr_hints = ["", "", ""]
                guess_the_player.curr_answer = ""
                  
                session.execute(
                    insert(guess_the_player_guess_the_player_player_association).values(
                        guess_the_player_id=chat_id,
                        guess_the_player_player_id=next_player[0],
                        guess_the_player_player_player_id=next_player[1],
                        time_created=func.now()
                    )
                )

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

                return True, "new curr player", next_player[1]

            return True, "", -1
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", -1

def get_asked_questions_guess_the_player(chat_id:int, session:Session):
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
