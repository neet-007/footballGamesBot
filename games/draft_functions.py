import logging
import traceback
from random import randint
from sqlalchemy import and_, exists, or_, select, update
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from db.models import Draft, DraftPlayer, DraftPlayerTeam, DraftVote, DraftVotePlayer, Game, Team, draft_team_association

logger = logging.getLogger(__name__)

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

def check_draft(chat_id:int, session:Session):
    try:
        with session.begin():
            game = session.query(Draft.state, Draft.num_players).filter(Draft.chat_id == chat_id).first()
            if not game:
                return False, "no game found", -1, -1

            return True, "", game[0], game[1]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", -1, -1

def get_vote_data(chat_id:int, session:Session):
    try:
        with session.begin():
            state = session.query(Draft.state).filter(Draft.chat_id == chat_id).first()
            players = session.query(DraftPlayer.player_id).filter(DraftPlayer.draft_id == chat_id).all()
            if not state:
                return False, "no game", -1, None
            if not players:
                return False, "no players associated with the game", -1, None

            return True, "", state[0], players
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", -1, None

def new_game_draft(chat_id: int, session:Session):
    logger.info("first log")
    try:
        with session.begin():
            if session.query(exists().where(Game.chat_id == chat_id)).scalar():
                return False, "a game has started in this chat"

            session.add_all([Game(chat_id=chat_id,),  Draft(chat_id=chat_id, num_players=0, category="", formation_name="")])
            return True, ""
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
        return False, "exception"

def join_game_draft(chat_id: int, player_id: int, session:Session):
    try:
        with session.begin():
            draft_state = session.query(Draft.state).filter(Draft.chat_id == chat_id).first()
            if not draft_state:
                return False, "no game"

            if draft_state[0] != 0:
                return False, "game has started"

            if session.query(exists().where(DraftPlayer.player_id == player_id, DraftPlayer.draft_id == chat_id)).scalar():
                return False, "player already in game"

            session.add( DraftPlayer(player_id=player_id, draft_id=chat_id,))

            session.query(Draft).filter(Draft.chat_id == chat_id).update({Draft.num_players:Draft.num_players + 1})

            return True, ""
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception"

def start_game_draft(chat_id: int, session:Session):
    try:
        with session.begin():
            draft_state = session.query(Draft.state).filter(Draft.chat_id == chat_id).first()
            if not draft_state:
                return False, "no game", -1

            if draft_state[0] != 0:
                return False, "state error", -1

            player_ids = session.query(DraftPlayer.id).filter(DraftPlayer.draft_id == chat_id).all()

            if not player_ids:
                session.query(Draft).filter(Draft.chat_id == chat_id).delete()
                session.query(Game).filter(Game.chat_id == chat_id).delete()
                return False, "no players associated with the game", -1

            num_players = len(player_ids)

            if num_players < 2:
                session.query(Draft).filter(Draft.chat_id == chat_id).delete()
                session.query(Game).filter(Game.chat_id == chat_id).delete()
                return False, "number of players is less than 2 or not as expected", -1

            teams = []
            for player_id in player_ids:
                teams.append(DraftPlayerTeam(player_id=player_id[0], chat_id=chat_id))

            (session.query(Draft)
             .filter(Draft.chat_id == chat_id)
             .update({Draft.state:1,
                      Draft.num_players:num_players}))

            session.add_all(teams)

            return True, "", num_players
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", -1

def set_game_states_draft(chat_id:int, player_id:int, category:str, teams:list[str], formation:str, session:Session):
    try:
        with session.begin():
            draft_details = session.query(Draft.state, Draft.num_players).filter(Draft.chat_id == chat_id).first()
            if not draft_details:
                return False , "no game found", -1, "", "", "", 0

            if draft_details[0] != 1 or teams == None:
                return False, "state error", draft_details[1], "", "", "", 0

            if not category:
                return False, "no category error", draft_details[1], "", "", "", 0

            if len(teams) != (11 + draft_details[1]):
                return False, "num of teams error", draft_details[1], "", "", "", 0

            if FORMATIONS.get(formation, None) == None:
                return False, "formation error", draft_details[1], "", "", "", 0

            if len(set(teams)) != len(teams):
                return False, "duplicate teams error", draft_details[1], "", "", "", 0

            if not session.query(exists().where(DraftPlayer.player_id == player_id, DraftPlayer.draft_id == chat_id)).scalar():
                return False, "player not in game", draft_details[1], "", "", "", 0

            teams = [team.lower().strip() for team in teams]
            teams_add = [{"name":team} for team in teams]

            stmt = sqlite_insert(Team).values(teams_add)
            stmt = stmt.on_conflict_do_nothing(index_elements=['name']) 

            session.execute(stmt) 
            session.flush()  
            
            all_teams = session.query(Team.id).filter(Team.name.in_(teams)).all()

            draft_teams = [{
                "team_id": team.id,
                "draft_id": chat_id
            } for team in all_teams]
                
            session.execute(draft_team_association.insert(), draft_teams)
            
            player_id_player_id = (
                session.query(DraftPlayer.id, DraftPlayer.player_id)
                .filter(DraftPlayer.draft_id == chat_id)
                .order_by(DraftPlayer.time_join.asc())  
                .first()  
            )
            if not player_id or not player_id_player_id:
                return False, "game error", draft_details[1], "", "", "", 0

            (
             session.query(Draft)
             .filter(Draft.chat_id == chat_id)
             .update({Draft.formation_name:formation,
                      Draft.category:category,
                      Draft.current_player_id:player_id_player_id[0],
                      Draft.picking_player_id:player_id_player_id[0],
                      Draft.state:2})
            )
            team_names = session.execute(
                select(Team.name)
                .join(Draft.teams) 
                .where(Draft.chat_id == chat_id)  
            ).scalars().all() or []

            return True, "", draft_details[1], category, formation, "\n".join([team_name for team_name in team_names]), player_id_player_id[1]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "expection", -1, "", "", "", 0

def add_pos_to_team_draft(chat_id:int, player_id:int, added_player:str, session:Session):
    try:
        with session.begin():
            draft_details = (
                session.query(Draft.state,
                              Draft.current_player_id,
                              Draft.curr_team_id,
                              Draft.curr_pos,
                              Draft.formation_name)
                        .filter(Draft.chat_id == chat_id)
                        .first()
            )

            if not draft_details:
                return False , "no game found", None, None, None

            if draft_details[0] != 3 and draft_details[0] != 4:
                return False, "state error", None, None, None

            player_db_id = session.query(DraftPlayer.id).filter(DraftPlayer.player_id == player_id,
                                                       DraftPlayer.draft_id == chat_id).first()
            
            if not player_db_id:
                return False, "player not in game", None, None, None
            
            if draft_details[1] != player_db_id[0]:
                return False, "curr_player_error", None, None, None

            curr_team_picked = (
                session.execute(
                    select(draft_team_association.c.picked)  
                    .where(
                        draft_team_association.c.draft_id == chat_id,
                        draft_team_association.c.team_id == draft_details[2]
                    )
                ).scalars().first()  
            )

            if curr_team_picked is None or curr_team_picked:
                return False, "picked_team_error", None, None, None

            pos_filled = session.query(
                exists().where(
                    and_(
                        DraftPlayerTeam.player_id == player_db_id[0],
                        getattr(DraftPlayerTeam, draft_details[3]) != None  
                    )
                )
            ).scalar()

            if draft_details[0] == 3 and pos_filled:
                return False, "picked_pos_error", None, None, None

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

            if (session.query(exists(DraftPlayerTeam.id).where(DraftPlayerTeam.chat_id == chat_id,position_filter))).scalar():
                return False, "taken player error", None, None, None
             
            session.execute(
                update(DraftPlayerTeam)
                .where(DraftPlayerTeam.player_id == player_db_id[0])
                .values({draft_details[3]: added_player_lower})
            )

            session.query(DraftPlayer).filter(DraftPlayer.id == draft_details[1]).update({"picked": True}) 

            non_picked_player_q = (
                session.query(DraftPlayer.id, DraftPlayer.player_id)
                .filter(DraftPlayer.draft_id == chat_id, 
                        DraftPlayer.picked == False,
                        DraftPlayer.id != draft_details[1])
                .order_by(DraftPlayer.time_join.asc())
            )

            non_picked_player = non_picked_player_q.first()

            non_picked_count = non_picked_player_q.count()

            if draft_details[0] == 4 or non_picked_count == 0 or not non_picked_player:
                return True, "end round", None, None, None

            (
                session.query(Draft)
                .filter(Draft.chat_id == chat_id)
                .update({Draft.current_player_id:non_picked_player[0]})
            )

            return True, "same_pos", non_picked_player[1],  draft_details[3], draft_details[4]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "expection", None, None, None

def end_round_draft(chat_id:int, session:Session):
    try:
        with session.begin():
            draft_details = (
                session.query(Draft.state,
                              Draft.current_player_id,
                              Draft.curr_pos,
                              Draft.curr_team_id,
                              Draft.formation_name)
                        .filter(Draft.chat_id == chat_id)
                        .first()
            )

            if not draft_details:
                return False, "no game found", None, None, None

            if draft_details[0] == 4:
                session.execute(
                    draft_team_association.update()
                    .where(
                        draft_team_association.c.draft_id == chat_id,
                        draft_team_association.c.team_id == draft_details[3]
                    )
                    .values(picked=True)
                )

                non_picked_player_q = (
                    session.query(DraftPlayer.id, DraftPlayer.player_id)
                    .filter(DraftPlayer.draft_id == chat_id, DraftPlayer.picking == False, DraftPlayer.transferd == False)
                    .order_by(DraftPlayer.time_join.asc())
                )

                non_picked_player = non_picked_player_q.first()

                non_picked_players_count = non_picked_player_q.count()

                if non_picked_players_count == 0 or non_picked_player is None:
                    session.query(Draft).filter(Draft.chat_id == chat_id).update({Draft.state:5})
                    curr_player_player_id = session.query(DraftPlayer.player_id).filter(DraftPlayer.id == draft_details[1]).first()
                    if not curr_player_player_id:
                        return False, "", None, None, None

                    query_results = (
                        session.query(
                            DraftPlayerTeam.player_id,
                            DraftPlayer.player_id.label("actual_player_id"),
                            *[getattr(DraftPlayerTeam, f'p{i}') for i in range(1, 12)]
                        )
                        .join(DraftPlayer, DraftPlayer.id == DraftPlayerTeam.player_id)
                        .filter(DraftPlayerTeam.chat_id == chat_id)
                        .all()
                    )
                    
                    teams = [
                        (result.actual_player_id, {f'p{i+1}': result[i+2] for i in range(11)})
                        for result in query_results
                    ]

                    return True,"end_game", curr_player_player_id[0], draft_details[4], teams
                (
                    session.query(Draft)
                           .filter(Draft.chat_id == chat_id)
                           .update({Draft.picking_player_id:non_picked_player[0],
                                    Draft.current_player_id:non_picked_player[0]})
                )

                return True, "new_transfer", non_picked_player[1], draft_details[4], None

            if draft_details[2] == "p11":
                session.query(Draft).filter(Draft.chat_id == chat_id).update({Draft.state:4})
                session.query(DraftPlayer).filter(DraftPlayer.draft_id == chat_id).update({DraftPlayer.picking: False, DraftPlayer.picked: False})
                session.flush()

                non_picked_player= (
                    session.query(DraftPlayer.id, DraftPlayer.player_id)
                    .filter(DraftPlayer.draft_id == chat_id, DraftPlayer.picking == False)
                    .order_by(DraftPlayer.time_join.asc())
                    .first()
                )
    
                if not non_picked_player:
                    return False, "game error", None, None, None

                query_results = (
                    session.query(
                        DraftPlayerTeam.player_id,
                        DraftPlayer.player_id.label("actual_player_id"),
                        *[getattr(DraftPlayerTeam, f'p{i}') for i in range(1, 12)]
                    )
                    .join(DraftPlayer, DraftPlayer.id == DraftPlayerTeam.player_id)
                    .filter(DraftPlayerTeam.chat_id == chat_id)
                    .all()
                )
                
                teams = [
                    (result.actual_player_id, {f'p{i+1}': result[i+2] for i in range(11)})
                    for result in query_results
                ]

                (
                    session.query(Draft)
                           .filter(Draft.chat_id == chat_id)
                           .update({Draft.picking_player_id:non_picked_player[0],
                                    Draft.current_player_id:non_picked_player[0]})
                )

                session.execute(
                    draft_team_association.update()
                    .where(
                        draft_team_association.c.draft_id == chat_id,
                        draft_team_association.c.team_id == draft_details[3]
                    )
                    .values(picked=True)
                )

                return True,"transfer_start", non_picked_player[1], draft_details[4], teams

            session.query(DraftPlayer).filter(DraftPlayer.draft_id == chat_id).update({DraftPlayer.picked: False})
            session.flush()

            non_picked_player_q = (
                session.query(DraftPlayer.id, DraftPlayer.player_id)
                .filter(DraftPlayer.draft_id == chat_id,
                        DraftPlayer.picking == False)
                .order_by(DraftPlayer.time_join.asc())
            )

            non_picked_player = non_picked_player_q.first()

            non_picked_players_count = non_picked_player_q.count()

            if non_picked_players_count == 0 or non_picked_player is None:
                session.query(DraftPlayer).filter(DraftPlayer.draft_id == chat_id).update({DraftPlayer.picking: False})
                session.flush()

                non_picked_player = (
                        session.query(DraftPlayer.id, DraftPlayer.player_id)
                        .filter(DraftPlayer.draft_id == chat_id, DraftPlayer.picking == False)
                        .order_by(DraftPlayer.time_join.asc())
                        .first()
                )
                if non_picked_player is None:
                    return False, "", None, None, None

            (
                session.query(Draft)
                       .filter(Draft.chat_id == chat_id)
                       .update({Draft.picking_player_id:non_picked_player[0],
                                Draft.current_player_id:non_picked_player[0]})
            )
            session.execute(
                draft_team_association.update()
                .where(
                    draft_team_association.c.draft_id == chat_id,
                    draft_team_association.c.team_id == draft_details[3]
                )
                .values(picked=True)
            )

            (
                session.query(Draft)
                .filter(Draft.chat_id == chat_id)
                .update({Draft.curr_pos:"p" + f"{int(draft_details[2][1]) + 1}" if len(draft_details[2]) == 2 else  "p" + f"{int(draft_details[2][1:3]) + 1}",
                         Draft.state:2})
            )
            
            return True, "new_pos", non_picked_player[1], draft_details[4], None
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "expection", None, None, None

def transfers(chat_id:int, player_id:int, position:str, session:Session):
    try:
        with session.begin():
            if position not in ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10", "p11", "skip"]:
                return False, "invalid posistion", None, None, None, None, None, None

            draft_details = (
                    session.query(Draft.state,
                                  Draft.picking_player_id,
                                  Draft.formation_name,
                                  Draft.curr_pos)
                           .filter(Draft.chat_id == chat_id)
                           .first()
            )
            if not draft_details:
                return False, "no game found", None, None, None, None, None, None

            player_details = session.query(DraftPlayer.id, DraftPlayer.transferd).filter(DraftPlayer.player_id == player_id,
                                                       DraftPlayer.draft_id == chat_id).first()
            if not player_details:
                return False, "player not in game", None, None, None, None, None, None
            
            if draft_details[0] != 4:
                return False, "state error", None, None, None, None, None, None

            if player_details[1]:
                return False, "player has transferd error", None, None, None, None, None, None

            if draft_details[1] != player_details[0]:
                return False, "curr_player_error", None, None, None, None, None, None

            session.query(DraftPlayer).filter(DraftPlayer.id == draft_details[1]).update({"picking":True})

            non_picked_teams = session.execute(
                select(Team.id, Team.name)
                .join(draft_team_association, Team.id == draft_team_association.c.team_id)
                .where(draft_team_association.c.picked == False,
                      draft_team_association.c.draft_id == chat_id)
            ).fetchall()

            if len(non_picked_teams) == 0:
                return False, "game error", None, None, None, None, None, None

            if position == "skip":
                session.query(DraftPlayer).filter(DraftPlayer.id == player_details[0]).update({DraftPlayer.transferd:True})
    
                next_player = (session.query(DraftPlayer.id, DraftPlayer.player_id)
                               .filter(DraftPlayer.draft_id == chat_id, DraftPlayer.transferd == False,
                                       DraftPlayer.picked == False, DraftPlayer.picking == False,
                                       DraftPlayer.id != player_details[0])
                               .order_by(DraftPlayer.time_join.asc())
                               .first()
                               ) 
                if not next_player:
                    session.query(Draft).filter(Draft.chat_id == chat_id).update({Draft.state:5})
                    query_results = (
                        session.query(
                            DraftPlayerTeam.player_id,
                            DraftPlayer.player_id.label("actual_player_id"),
                            *[getattr(DraftPlayerTeam, f'p{i}') for i in range(1, 12)]
                        )
                        .join(DraftPlayer, DraftPlayer.id == DraftPlayerTeam.player_id)
                        .filter(DraftPlayerTeam.chat_id == chat_id)
                        .all()
                    )
                    
                    teams = [
                        (result.actual_player_id, {f'p{i+1}': result[i+2] for i in range(11)})
                        for result in query_results
                    ]
                    return True, "end_game", None, draft_details[2], None, None, teams, None

                (
                    session.query(Draft)
                    .filter(Draft.chat_id == chat_id)
                    .update({Draft.current_player_id:next_player[0],
                             Draft.picking_player_id:next_player[0]})
                )

                return True, "skipped", None, draft_details[2], None, next_player[1], None, None

            rand_team = non_picked_teams[randint(0, len(non_picked_teams) - 1)]

            session.query(DraftPlayer).filter(DraftPlayer.id == player_details[0]).update({DraftPlayer.transferd:True})
            (
                session.query(Draft)
                .filter(Draft.chat_id == chat_id)
                .update({Draft.curr_team_id:rand_team[0],
                         Draft.curr_pos:position})
            )
            return True, "", rand_team[1], draft_details[2], position, None, None, [team[1] for team in non_picked_teams if team[0] != rand_team[0]]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "expection", None, None, None, None, None, None

def rand_team_draft(chat_id:int, player_id:int, session:Session):
    try:
        with session.begin():
            draft_details = (
                session.query(Draft.state,
                              Draft.picking_player_id,
                              Draft.formation_name,
                              Draft.curr_pos)
                .filter(Draft.chat_id == chat_id)
                .first()
            )
            if not draft_details:
                return False , "no game found", "", "", "", []

            player_db_id = session.query(DraftPlayer.id).filter(DraftPlayer.player_id == player_id,
                                                       DraftPlayer.draft_id == chat_id).first()
            if not player_db_id:
                return False, "player not in game", "", "", "", []
            
            if draft_details[0] != 2:
                return False, "state error", "", "", "", []

            if draft_details[1] != player_db_id[0]:
                return False, "curr_player_error", "", "", "", []

            session.query(DraftPlayer).filter(DraftPlayer.id == draft_details[1]).update({"picking":True})
            non_picked_teams = session.execute(
                select(Team.id, Team.name)
                .join(draft_team_association, Team.id == draft_team_association.c.team_id)
                .where(draft_team_association.c.picked == False,
                      draft_team_association.c.draft_id == chat_id)
            ).fetchall()

            if len(non_picked_teams) == 0:
                return False, "game error", "", "", "", []

            rand_team = non_picked_teams[randint(0, len(non_picked_teams) - 1)]

            (
                session.query(Draft)
                .filter(Draft.chat_id == chat_id)
                .update({Draft.curr_team_id:rand_team[0],
                    Draft.state:3})
            )

            team_name = rand_team[1]
            formation = draft_details[2]
            curr_pos = draft_details[3]

            non_picked_teams = [team[1] for team in non_picked_teams if team[0] != rand_team[0]]
            return True, "", team_name, formation, curr_pos, non_picked_teams
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "expection", "", "", "", []

def make_vote(chat_id:int, players, message_id:int, poll_id:str, session:Session):
    try:
        with session.begin():
            draft_num_players = session.query(Draft.num_players).filter(Draft.chat_id == chat_id).first()

            if not draft_num_players:
                return False, "no game found"
        
            session.add(DraftVote(
                    chat_id=chat_id,
                    num_players=draft_num_players[0],
                    message_id=message_id,
                    answers=0,
                    poll_id=poll_id,
                )
            )
            session.flush()  
            
            session.bulk_save_objects([
                DraftVotePlayer(draft_vote=chat_id, player_id=player_id[0], option_id=i)
                for i, player_id in enumerate(players)
            ])
            return True, ""
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception"

def add_vote(poll_id:str, option_id:int, session:Session):
    try:
        with session.begin():
            vote_details = session.query(DraftVote.chat_id, DraftVote.num_players).filter(DraftVote.poll_id == poll_id).first()

            if not vote_details:
                return False, "no game found", 0
        
            (
                session.query(DraftVotePlayer)
                .filter(DraftVotePlayer.draft_vote == vote_details[0], DraftVotePlayer.option_id == option_id)
                .update({
                    DraftVotePlayer.votes: DraftVotePlayer.votes + 1
                })
            )

            answers = (
                session.execute(
                    update(DraftVote)
                    .where(DraftVote.poll_id == poll_id)
                    .values(answers=DraftVote.answers + 1)
                    .returning(DraftVote.answers)
                )
            ).fetchone()

            if not answers:
                return False, "game error", 0

            if answers[0] == vote_details[1]:
                return True, "end vote", vote_details[0]

            return True, "continue", vote_details[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", 0
    
def get_vote_results(chat_id:int, session:Session):
    try:
        with session.begin():
            message_id = session.query(DraftVote.message_id).filter(DraftVote.chat_id == chat_id).first()
            draft_votes_players = (
                session.query(DraftVotePlayer.player_id, DraftVotePlayer.votes)
                .filter(DraftVotePlayer.draft_vote == chat_id)
                .all()
            )
    
            if not message_id or not draft_votes_players:
                return False, "no game", 0, {}

            votes = {player_id_:vote_ for (player_id_, vote_) in draft_votes_players}
            return True, "", message_id[0], votes

    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", 0, {}

def end_game_draft(chat_id:int, session:Session):
    try:
        with session.begin():
            draft_formation = session.query(Draft.formation_name).filter(Draft.chat_id == chat_id).first()
            if not draft_formation:
                return False, "no game found", None, None

            query_results = (
                session.query(
                    DraftPlayerTeam.player_id,
                    DraftPlayer.player_id.label("actual_player_id"),
                    *[getattr(DraftPlayerTeam, f'p{i}') for i in range(1, 12)]
                )
                .join(DraftPlayer, DraftPlayer.id == DraftPlayerTeam.player_id)
                .filter(DraftPlayerTeam.chat_id == chat_id)
                .all()
            )
            
            teams = [
                (result.actual_player_id, {f'p{i+1}': result[i+2] for i in range(11)})
                for result in query_results
            ]

            session.query(Game).filter(Game.chat_id == chat_id).delete()
            session.query(Draft).filter(Draft.chat_id == chat_id).delete()
            session.query(DraftVote).filter(DraftVote.chat_id == chat_id).delete()

            if not teams:
                return False, "no players no formation" , None, None

            return True, "", teams, draft_formation[0]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", None, None

def leave_game_draft(chat_id:int, player_id:int, session:Session):
    try:
        with session.begin():
            draft = session.query(Draft).filter(Draft.chat_id == chat_id).first()
            player = session.query(DraftPlayer).filter(DraftPlayer.draft_id == chat_id, DraftPlayer.player_id == player_id).first()
            if not draft:
                return False, "no game found", "", "", "", 0, [], []
        
            if not player:
                return False, "player not in game", "", "", "", 0, [], []

            if draft.state < 1:
                draft.num_players -= 1
                session.delete(player)
                
                return True, "", "", "", "", 0, [], []

            if draft.num_players <= 2:
                if draft.state < 4:
                    session.query(Game).filter(Game.chat_id == chat_id).delete()
                    session.delete(draft)

                    return True, "game canceld", "", "", "", 0, [], []

                query_results = (
                    session.query(
                        DraftPlayerTeam.player_id,
                        DraftPlayer.player_id.label("actual_player_id"),
                        *[getattr(DraftPlayerTeam, f'p{i}') for i in range(1, 12)]
                    )
                    .join(DraftPlayer, DraftPlayer.id == DraftPlayerTeam.player_id)
                    .filter(DraftPlayerTeam.chat_id == chat_id,
                            DraftPlayerTeam.player_id != player.id)
                    .all()
                )

                teams = [
                    (result.actual_player_id, {f'p{i+1}': result[i+2] for i in range(11)})
                    for result in query_results
                ]
                session.query(Game).filter(Game.chat_id == chat_id).delete()
                session.delete(draft)

                return True, "game end", draft.formation_name, "", "", 0, [], teams

            # the above is mostly complete the bottom is not
            if draft.state == 4 and (draft.picking_player_id == player.id or draft.current_player_id == player.id):
                next_player = (
                    session.query(DraftPlayer.id, DraftPlayer.player_id)
                    .filter(DraftPlayer.draft_id == chat_id,
                            DraftPlayer.picking == False,
                            DraftPlayer.id != player.id,
                            DraftPlayer.transferd == False)
                    .order_by(DraftPlayer.time_join.asc())
                    .first()
                )

                session.delete(player)
                draft.num_players -= 1
                if not next_player:
                    return True, "end game", draft.formation_name, "", "", 0, [], []

                non_picked_teams = session.execute(
                    select(Team.name)
                    .join(draft_team_association, Team.id == draft_team_association.c.team_id)
                    .where(draft_team_association.c.picked == False,
                          draft_team_association.c.draft_id == chat_id)
                ).fetchall()
                draft.picking_player_id = next_player[0]
                draft.current_player_id = next_player[0]
                return True, "new transfer player", draft.formation_name, draft.curr_pos, "", next_player[1], [team[0] for team in non_picked_teams], []

            if draft.state == 2 and draft.picking_player_id == player.id:
                next_player = (
                    session.query(DraftPlayer.id, DraftPlayer.player_id)
                    .filter(DraftPlayer.draft_id == chat_id,
                            DraftPlayer.picking == False,
                            DraftPlayer.id != player.id)
                    .order_by(DraftPlayer.time_join.asc())
                    .first()
                )

                draft.num_players -= 1
                session.delete(player)
                if not next_player:
                    session.query(DraftPlayer).filter(DraftPlayer.draft_id == chat_id).update({DraftPlayer.picking: False})
                    session.flush()
                    next_player = (
                        session.query(DraftPlayer.id, DraftPlayer.player_id)
                        .filter(DraftPlayer.draft_id == chat_id,
                                DraftPlayer.picking == False,
                                DraftPlayer.id != player.id)
                        .order_by(DraftPlayer.time_join.asc())
                        .first()
                    )

                    if not next_player:
                        return False, "game error", "", "", "", 0, [], []
    
                draft.picking_player_id = next_player[0]
                draft.current_player_id = next_player[0]
                return True, "new picking player", draft.formation_name, draft.curr_pos, "", next_player[1] , [], []

            if draft.state == 3 and draft.current_player_id == player.id:
                next_player = (
                    session.query(DraftPlayer.id, DraftPlayer.player_id)
                    .filter(DraftPlayer.draft_id == chat_id,
                            DraftPlayer.picked == False,
                            DraftPlayer.id != player.id)
                    .order_by(DraftPlayer.time_join.asc())
                    .first()
                )

                draft.num_players -= 1
                session.delete(player)
                if not next_player:
                    return True, "end round", "", "", "", 0, [], []

                draft.current_player_id = next_player[0]
                team = session.query(Team.name).filter(Team.id == draft.curr_team_id).first() 
                if not team:
                    return False, "game error", "", "", "", 0, [], []

                non_picked_teams = session.execute(
                    select(Team.name)
                    .join(draft_team_association, Team.id == draft_team_association.c.team_id)
                    .where(draft_team_association.c.picked == False,
                          draft_team_association.c.draft_id == chat_id)
                ).fetchall()
                return True, "new current player", draft.formation_name, draft.curr_pos, team[0], next_player[1], [team[0] for team in non_picked_teams], []

            draft.num_players -= 1
            session.delete(player)
            return True, "", "", "", "", 0, [], []
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", "", "", "", 0, [], []

def cancel_game_draft(chat_id:int, session:Session):
    try:
        with session.begin():
            game_deleted = session.query(Game).filter(Game.chat_id == chat_id).delete()
            draft_deleted = session.query(Draft).filter(Draft.chat_id == chat_id).delete()

            if game_deleted == 0 or draft_deleted == 0:
                return False, "no game found"

            return True, ""
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception"

