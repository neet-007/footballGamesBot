from sqlalchemy import delete, func, insert, or_, select, update
from sqlalchemy.orm import Session
import telegram
import telegram.ext
from random import shuffle, randint
from db.connection import get_session 
from db.models import AskedQuestions, Draft as d, DraftPlayer, DraftPlayerTeam, Game, GuessThePlayerPlayer, Team, draft_team_association, GuessThePlayer as GuessThePlayer, guess_the_player_guess_the_player_player_association
def remove_jobs(name:str, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if not context.job_queue:
        return

    jobs = context.job_queue.get_jobs_by_name(name)
    if not jobs:
        return

    for job in jobs:
        job.schedule_removal()

session = get_session()

FORMATIONS = {
    "442":{"p1":"gk", "p2":"rb", "p3":"rcb", "p4":"lcb", "p5":"lb",
           "p6":"rw", "p7":"rcm", "p8":"lcm", "p9":"lw", "p10":"rst",
          "p11":"lst"},
    "433":{"p1":"gk", "p2":"rb", "p3":"rcb", "p4":"lcb", "p5":"lb",
           "p6":"rcm", "p7":"cdm", "p8":"lcm", "p9":"rw", "p10":"lw",
           "p11":"st"},
    "4231":{"p1":"gk", "p2":"rb", "p3":"rcb", "p4":"lcb", "p5":"lb",
            "p6":"rcdm", "p7":"lcdm", "p8":"rw", "p9":"am", "p10":"lw",
            "p11":"st"},
    "352":{"p1":"gk", "p2":"rcb", "p3":"cb", "p4":"lcb", "p5":"rwb",
           "p6":"rcm","p7":"cdm", "p8":"lcm", "p9":"lwb", "p10":"rst", 
           "p11":"lst"},
    "532":{"p1":"gk", "p2":"rwb", "p3":"rcb", "p4":"cb", "p5":"lcb",
           "p6":"lwb", "p7":"rcm", "p8":"cdm", "p9":"lcm", "p10":"rst",
           "p11":"lst"}
}

def check_draft(chat_id:int):
    try:
        with session.begin():
            game = session.query(d.state, d.num_players).filter(d.chat_id == chat_id).first()
            if not game:
                return False, -1, -1

            return True, game[0], game[1]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, -1, -1

def get_vote_data(chat_id:int):
    try:
        with session.begin():
            state = session.query(d.state).filter(d.chat_id == chat_id).first()
            players = session.query(DraftPlayer.player_id).filter(DraftPlayer.draft_id == chat_id).all()
            if not state or not players:
                return False, -1, None

            return True, state[0], players
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, -1, None

def new_game_draft(chat_id: int, session: Session):
    try:
        with session.begin():
            game = session.query(Game).filter(Game.chat_id == chat_id).first()
            if game:
                return False, "a game has started"

            draft = d(
                chat_id=chat_id,
                num_players=0,
                category="",
                formation_name="",
            )
            game = Game(
                chat_id=chat_id,
            )

            session.add_all([game, draft])
            return True, ""
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception"

def join_game_draft(chat_id: int, player_id: int, session: Session):
    try:
        with session.begin():
            draft = session.query(d).filter(d.chat_id == chat_id).first()
            if not draft:
                return False, "no game"

            if draft.state != 0:
                return False, "game has started"

            player_db = session.query(DraftPlayer).filter(DraftPlayer.player_id == player_id,
                                                          DraftPlayer.draft_id == chat_id).first()
            if player_db:
                return False, "player already in game"

            player_db = DraftPlayer(
                player_id=player_id,
                draft_id=chat_id,
            )
            session.add(player_db)

            draft.num_players += 1

            return True, ""
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception"

def start_game_draft(chat_id: int, session: Session):
    try:
        with session.begin():
            draft = session.query(d).filter(d.chat_id == chat_id).first()
            if not draft:
                return False, "no game", -1

            if draft.state != 0:
                return False, "game has started", -1

            player_ids = session.query(DraftPlayer).with_entities(DraftPlayer.id).filter(DraftPlayer.draft_id == draft.chat_id).all()

            if not player_ids:
                return False, "no players associated with the game", -1

            num_players = len(player_ids)

            if num_players < 2 or num_players != draft.num_players:
                return False, "number of players is less than 2 or not as expected", -1

            print("WHAT I SHOUDLLLLLLLLLLLLLLLLLLLLLLD", draft.chat_id)
            print("WHAT I PUUUUUUUUUUUUUUUUT",chat_id)
            teams = []
            for player_id in player_ids:
                print(player_id[0])
                teams.append(DraftPlayerTeam(player_id=player_id[0], chat_id=chat_id))

            draft.state = 1
            session.add_all(teams)

            return True, "", num_players
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", -1

def set_game_states_draft(chat_id:int, player_id:int, category:str, teams:list[str], formation:str, session:Session):
    try:
        with session.begin():
            game = session.query(d).filter(d.chat_id == chat_id).first()
            if not game:
                return False , "no game found", []

            if game.state != 1 or teams == None:
                return False, "game error", []

            if not category:
                return False, "no category error", []

            if len(teams) != (11 + game.num_players):
                return False, "num of teams error", []

            if FORMATIONS.get(formation, None) == None:
                return False, "formation error", []

            if len(set(teams)) != len(teams):
                return False, "duplicate teams error", []

            if not session.query(DraftPlayer).filter(DraftPlayer.player_id == player_id, DraftPlayer.draft_id == chat_id).limit(1):
                return False, "player not in game", []

            game.formation_name = formation
            teams = [team.lower().strip() for team in teams]

            existing_teams = [team for team in session.query(Team).all()]
            existing_teams_names = [team.name for team in existing_teams]

            print("================================\n", existing_teams, "\n================================\n")

            teams_to_add = [Team(name=team) for team in teams if team not in existing_teams_names]
            
            session.add_all(teams_to_add)
            session.flush()  
            
            print("================================\n", teams_to_add, "\n================================\n")

            all_teams = existing_teams + teams_to_add

            print("================================\n", all_teams, "\n================================\n")
            draft_teams = [{
                "team_id": team.id,
                "draft_id": chat_id
            } for team in all_teams]
                
            session.execute(draft_team_association.insert(), draft_teams)

            game.category = category
            
            player = (
                session.query(DraftPlayer)
                .filter(DraftPlayer.draft_id == chat_id)
                .order_by(DraftPlayer.time_join.asc())  
                .first()  
            )
            if not player_id or not player:
                return False, "game error", []

            player_id_ = player.player_id
            game.current_player_id = player.id
            game.picking_player_id = player.id

            game.state = 2
            other = [game.category, game.formation_name, " ".join([team.name for team in game.teams]), player_id_]
            session.commit()

            return True, "", other
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "expection", []

def add_pos_to_team_draft(chat_id:int, player_id:int, added_player:str, session:Session):
    try:
        with session.begin():
            game = session.query(d).filter(d.chat_id == chat_id).first()
            if not game:
                return False , "no game found", [None, None, None, None]

            if game.state != 2:
                return False, "game error", [None, None, None, None]

            player = session.query(DraftPlayer).filter(DraftPlayer.player_id == player_id,
                                                       DraftPlayer.draft_id == chat_id).first()
            
            if not player:
                return False, "player not in game", [None, None, None, None]
            
            if game.current_player_id != player.id:
                return False, "curr_player_error", [None, None, None, None]

            curr_team = session.execute(draft_team_association.select().filter(draft_team_association.c.draft_id == chat_id,
                                                                      draft_team_association.c.team_id == game.curr_team_id)).first()
            if not curr_team or curr_team.picked:
                return False, "picked_team_error", [None, None, None, None]

            player_team = session.query(DraftPlayerTeam).filter(
                DraftPlayerTeam.player_id == player.id,
            ).first()

            if not player_team:
                return False, "player does not exist in team", [None, None, None, None]

            if getattr(player_team, game.curr_pos):
                return False, "picked_pos_error", [None, None, None, None]

            added_player_lower = added_player.lower()
            position_filter = or_(
                DraftPlayerTeam.p1.ilike(added_player_lower),
                DraftPlayerTeam.p2.ilike(added_player_lower),
                DraftPlayerTeam.p3.ilike(added_player_lower),
                DraftPlayerTeam.p4.ilike(added_player_lower),
                DraftPlayerTeam.p5.ilike(added_player_lower),
                DraftPlayerTeam.p6.ilike(added_player_lower),
                DraftPlayerTeam.p7.ilike(added_player_lower),
                DraftPlayerTeam.p8.ilike(added_player_lower),
                DraftPlayerTeam.p9.ilike(added_player_lower),
                DraftPlayerTeam.p10.ilike(added_player_lower),
                DraftPlayerTeam.p11.ilike(added_player_lower)
            )

            matching_player_teams = session.query(DraftPlayerTeam).filter(
                DraftPlayerTeam.chat_id == chat_id,
                position_filter
            ).all()

            if matching_player_teams:
                return False, "taken player error", [None, None, None, None]
                    
            setattr(player_team, game.curr_pos, added_player_lower)
            
            session.query(DraftPlayer).filter(DraftPlayer.id == game.current_player_id).update({"picked": True}) 

            session.flush()
            non_picked_players = (
                    session.query(DraftPlayer)
                    .filter(DraftPlayer.draft_id == chat_id, DraftPlayer.picked == False)
                    .order_by(DraftPlayer.time_join.asc())
                    .all()
            )

            if len(non_picked_players) == 0:
                if game.curr_pos == "p11":
                    game.state = 3
                    curr_player = session.query(DraftPlayer).filter(DraftPlayer.id == game.current_player_id).first()
                    if not curr_player:
                        return False, "", [None, None, None, None]

                    query_results = (
                        session.query(
                            DraftPlayerTeam.player_id,
                            *[getattr(DraftPlayerTeam, f'p{i}') for i in range(1, 12)]
                        )
                        .filter(DraftPlayerTeam.chat_id == chat_id)
                        .all()
                    )

                    player_ids = [result[0] for result in query_results]

                    players = (
                        session.query(DraftPlayer.player_id)
                        .filter(DraftPlayer.id.in_(player_ids))
                        .all()
                    )
                    player_dict = {player_ids[i]: players[i] for i in range (len(players))}
                    teams = [
                        (player_dict[result[0]][0], {f'p{i+1}': result[i+1] for i in range(11)})
                        for result in query_results
                    ]
                    other = [curr_player.player_id, game.formation_name, game.curr_pos, teams]
                    return True,"end_game", other

                session.query(DraftPlayer).filter(DraftPlayer.draft_id == chat_id).update({"picked": False})
                session.flush()
                non_picked_players = (
                        session.query(DraftPlayer)
                        .filter(DraftPlayer.draft_id == chat_id, DraftPlayer.picking == False)
                        .order_by(DraftPlayer.time_join.asc())
                        .all()
                )
                if len(non_picked_players) == 0:
                    session.query(DraftPlayer).filter(DraftPlayer.draft_id == chat_id).update({"picking": False})
                    session.flush()
                    non_picked_players = (
                            session.query(DraftPlayer)
                            .filter(DraftPlayer.draft_id == chat_id, DraftPlayer.picking == False)
                            .order_by(DraftPlayer.time_join.asc())
                            .all()
                    )

                game.picking_player_id = non_picked_players[0].id
                game.current_player_id = non_picked_players[0].id
                session.execute(
                    draft_team_association.update()
                    .where(
                        draft_team_association.c.draft_id == chat_id,
                        draft_team_association.c.team_id == game.curr_team_id
                    )
                    .values(picked=True)
                )
                game.curr_pos = "p" + f"{int(game.curr_pos[1]) + 1}" if len(game.curr_pos) == 2 else  "p" + f"{int(game.curr_pos[1:3]) + 1}"
                curr_player = session.query(DraftPlayer).filter(DraftPlayer.id == game.current_player_id).first()
                if not curr_player:
                    return False, "", [None, None, None, None]

                other = [curr_player.player_id, game.formation_name, game.curr_pos]
                session.commit()
                return True, "new_pos", other

            game.current_player_id = non_picked_players[0].id
            session.flush()
            curr_player = session.query(DraftPlayer).filter(DraftPlayer.id == game.current_player_id).first()
            if not curr_player:
                return False, "", [None, None, None, None]

            other = [curr_player.player_id, game.formation_name, game.curr_pos]
            session.commit()
            return True, "same_pos", other
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "expection", [None, None, None, None]

def rand_team_draft(chat_id:int, player_id:int, session:Session):
    try:
        with session.begin():
            game = session.query(d).filter(d.chat_id == chat_id).first()
            if not game:
                return False , "no game found", "", ""

            player = session.query(DraftPlayer).filter(DraftPlayer.player_id == player_id,
                                                       DraftPlayer.draft_id == chat_id).first()
            if not player:
                return False, "player not in game", "", ""
            
            if game.state != 2:
                return False, "game error", "", ""

            if game.picking_player_id != player.id:
                return False, "curr_player_error", "", ""

            session.query(DraftPlayer).filter(DraftPlayer.id == game.picking_player_id).update({"picking":True})
            non_picked_teams = session.execute(
                select(draft_team_association).where(draft_team_association.c.picked == False,
                                                     draft_team_association.c.draft_id == chat_id)
            ).fetchall()
            if len(non_picked_teams) == 0:
                return False, "game error", "", ""

            rand_team = non_picked_teams[randint(0, len(non_picked_teams) - 1)]
            game.curr_team_id = rand_team.team_id
            team_instance = session.query(Team).filter(Team.id == rand_team.team_id).first()
            if not team_instance:
                return False, "", "", ""

            team_name = team_instance.name
            formation = game.formation_name
            curr_pos = game.curr_pos
            session.commit()

            return True, team_name, formation, curr_pos
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "expection", "", ""

def end_game_draft(chat_id:int):
    try:
        with session.begin():
            game = session.query(Game).filter(Game.chat_id == chat_id).first()
            draft = session.query(d).filter(d.chat_id == chat_id).first()
            formation = session.query(d.formation_name).filter(d.chat_id == chat_id).first()
            query_results = (
                session.query(
                    DraftPlayerTeam.player_id,
                    *[getattr(DraftPlayerTeam, f'p{i}') for i in range(1, 12)]
                )
                .filter(DraftPlayerTeam.chat_id == chat_id)
                .all()
            )

            player_ids = [result[0] for result in query_results]

            players = (
                session.query(DraftPlayer.player_id)
                .filter(DraftPlayer.id.in_(player_ids))
                .all()
            )
            player_dict = {player_ids[i]: players[i] for i in range (len(players))}
            teams = [
                (player_dict[result[0]][0], {f'p{i+1}': result[i+1] for i in range(11)})
                for result in query_results
            ]
            if not game or not players or not formation:
                session.delete(game)
                session.delete(draft)
                return False , None, None

            formation = formation[0]
            session.delete(game)
            session.delete(draft)
            return True, teams, formation
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, None, None

def cancel_game_draft(chat_id:int ,session:Session):
    try:
        with session.begin():
            game = session.query(Game).filter(Game.chat_id == chat_id).first()
            draft = session.query(d).filter(d.chat_id == chat_id).first()

            session.delete(game)
            session.delete(draft)
            return True
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

def check_guess_the_player(chat_id:int):
    try:
        with session.begin():
            game = session.query(GuessThePlayer.state, GuessThePlayer.num_players).filter(GuessThePlayer.chat_id == chat_id).first()
            if not game:
                return False, -1, -1

            return True, game[0], game[1]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, -1, -1

def new_game_guess_the_player(chat_id:int, session:Session):
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

def join_game_guess_the_player(chat_id:int, player_id:int, session:Session):
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
                return False, "a game has started", -1

            if guess_the_player.state != 0:
                return False, "game error", -1

            player_ids = (
                    session.query(GuessThePlayerPlayer)
                    .with_entities(GuessThePlayerPlayer.id)
                    .filter(GuessThePlayerPlayer.guess_the_player_id == guess_the_player.chat_id)
                    .order_by(GuessThePlayerPlayer.time_join.asc())  
                    .all()
            )

            if not player_ids:
                print("=================\n", "heeeeeeeree\n", "=================")
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
                print("=================\n", "heeeeeeeree\n", "=================")
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
            
            print(result)
            if not result:
                return False, "player not found or not in game", [], -1

            id, chat_id = result

            guess_the_player = session.query(GuessThePlayer).filter(GuessThePlayer.chat_id == chat_id).first()
            if not guess_the_player:
                return False, "a game has started", [], -1

            print("==========\n", guess_the_player.state, "\n==========\n")
            if guess_the_player.state != 1 and guess_the_player.state != 3:
                return False, "game error", [], -1
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
                return False, "a game has started", -1

            if guess_the_player.state != 2:
                return False, "game_error", -1

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
                return False, "a game has started"

            if guess_the_player.state != 2:
                return False, "game error"

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
                return False, "a game has started"

            if guess_the_player.state != 2:
                return False, "game error"

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
                return False, "a game has started", -1

            if guess_the_player.state != 3:
                return False, "game error", -1

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

            print(next_player)
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
                return False, "a game has started", {}, []

            players = (
                session.query(GuessThePlayerPlayer)
                .filter(GuessThePlayerPlayer.guess_the_player_id == chat_id)
                .all()
            )

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
            if not guess_the_player:
                return False, "a game has started"

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
                return False, "a game has started", -1
    
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
            
            return True, "", {q.question:q.answer for q in questions}
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", {}
    

WILTY_ROUNDS = {
    0:"none",
    1:"transfers",
    2:"managers",
    3:"players comparisions",
    4:"predections",
    5:"young talents"
}

class Wilty():
    def __init__(self) -> None:
        self.num_players:int = 0
        self.players = dict()
        self.players_ids = []
        self.curr_mod_idx = -1
        self.curr_player_idx = -1
        self.state = 0
        self.round_type:int = 0
        self.mod_statement = ""
        self.curr_statement = ""
        self.statements = {}

    def join_game(self, player: telegram.User):
        if self.state != 0:
            return False

        if player.id in self.players:
            return False

        self.players[player.id] = [player, 0]
        self.players_ids.append(player.id)
        self.num_players += 1

        return True

    def start_game(self):
        if self.state != 0:
            return False, "game error"

        if self.num_players < 3:
            return False, "num players error"

        shuffle(self.players_ids)
        self.state = 1
        return True, ""

    def get_statements(self, player: telegram.User, statements:list[str]):
        if self.state != 1:
            return False, "game error"

        if player.id in self.statements:
            return False, "player has submited error"
        if len(statements) != 5:
            return False, "statements length error"

        statements = [x.strip().lower() for x in statements]
        self.statements[player.id] = statements
        
        if len(self.statements) == self.num_players:
            self.state = 2
            return True, "start game"

        return True, ""

    def start_round(self):
        if self.state != 2:
            return False, "game error"

        if self.round_type == 0:
            self.curr_mod_idx = 0
            self.curr_player_idx = 1
            self.round_type = 1
        else:
            self.curr_mod_idx = self.curr_mod_idx + 1 % (self.num_players - 1)
            if self.curr_mod_idx == 1:
                self.curr_player_idx = 0
            else:
                self.curr_player_idx = 1

        self.state = 3
        return True, ""

    def get_mod_statement(self, player:telegram.User, statement:str):
        if self.state != 3:
            return False, "game error"

        if player.id != self.players_ids[self.curr_mod_idx]:
            return False, "curr mod error"

        statement = statement.strip().lower()
        if statement == "__same__":
            self.curr_statement = self.statements[self.players_ids[self.curr_player_idx]][self.round_type]
        else:
            self.curr_statement = statement

        self.state = 4
        return True, ""

    def play(self, vote:bool):
        if self.state != 4:
            return False, "game error"

        if vote:
            if self.curr_statement != self.statements[self.players_ids[self.curr_player_idx]][self.round_type]:
                self.players[self.players_ids[self.curr_player_idx]][1] += 1
            else:
                for id, player in self.players:
                    if id == self.players_ids[self.curr_player_idx] or id == self.players_ids[self.curr_mod_idx]:
                        continue
                    player[1] += 1
        else:
            if self.curr_statement == self.statements[self.players_ids[self.curr_player_idx]][self.round_type]:
                self.players[self.players_ids[self.curr_player_idx]][1] += 1
            else:
                for id, player in self.players:
                    if id == self.players_ids[self.curr_player_idx] or id == self.players_ids[self.curr_mod_idx]:
                        continue
                    player[1] += 1

        self.curr_player_idx = self.curr_player_idx + 1 % (self.num_players - 1) 
        if self.curr_mod_idx == 1:
            if self.curr_player_idx == 0:
                self.state = 5
                return True, "end round"

            return True, "continue"

        if self.curr_player_idx == 1:
            self.state = 5
            return True, "end round"
    
        return True, "continue"


    def end_round(self):
        if self.state != 5:
            return False, "game error"

        if self.round_type == 5:
            self.state = 6
            return True, "end game"

        self.round_type += 1
        self.state = 2
        return True, "next round"

    def end_game(self):
        if self.state != 6:
            return "", []

        winners = []
        max_score = float("-inf")
        text = ""
        for player in self.players.values():
            if player[1] > max_score:
                max_score = player[1]
                winners.clear()
                winners.append(player[0])
            elif player[1] == max_score:
                winners.append(player[0])

            text += f"{player[0].mention_html()}:{player[1]}\n"

        return text, winners

PLAYERS_COUNT = 2

games:dict[int, Wilty] = {}


def jaro_winkler_similarity(s1: str, s2: str) -> float:
    def jaro(s1: str, s2: str) -> float:
        if s1 == s2:
            return 1.0
        len_s1, len_s2 = len(s1), len(s2)
        if len_s1 == 0 or len_s2 == 0:
            return 0.0

        match_distance = int(max(len_s1, len_s2) / 2) - 1
        matches = 0
        transpositions = 0
        s1_matches = [False] * len_s1
        s2_matches = [False] * len_s2

        for i in range(len_s1):
            start = max(0, i - match_distance)
            end = min(i + match_distance + 1, len_s2)
            for j in range(start, end):
                if s2_matches[j]:
                    continue
                if s1[i] != s2[j]:
                    continue
                s1_matches[i] = True
                s2_matches[j] = True
                matches += 1
                break

        if matches == 0:
            return 0.0

        k = 0
        for i in range(len_s1):
            if s1_matches[i]:
                while not s2_matches[k]:
                    k += 1
                if s1[i] != s2[k]:
                    transpositions += 1
                k += 1
        transpositions //= 2

        jaro_score = (matches / len_s1 + matches / len_s2 + (matches - transpositions) / matches) / 3.0
        return jaro_score

    jaro_score = jaro(s1, s2)
    prefix_length = 0
    max_prefix_length = 4

    for i in range(min(len(s1), len(s2), max_prefix_length)):
        if s1[i] != s2[i]:
            break
        prefix_length += 1

    return jaro_score + (prefix_length * 0.1 * (1 - jaro_score))
games = {}
