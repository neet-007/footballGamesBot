from random import randint
from sqlalchemy import or_, select
from db.connection import get_session
from db.models import Draft, DraftPlayer, DraftPlayerTeam, Game, Team, draft_team_association


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

session = get_session()

def check_draft(chat_id:int):
    try:
        with session.begin():
            game = session.query(Draft.state, Draft.num_players).filter(Draft.chat_id == chat_id).first()
            if not game:
                return False, "no game found", -1, -1

            return True, "", game[0], game[1]
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "", -1, -1

def get_vote_data(chat_id:int):
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

def new_game_draft(chat_id: int):
    try:
        with session.begin():
            game = session.query(Game).filter(Game.chat_id == chat_id).first()
            if game:
                return False, "a game has started in this chat"

            draft = Draft(
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

def join_game_draft(chat_id: int, player_id: int):
    try:
        with session.begin():
            draft = session.query(Draft).filter(Draft.chat_id == chat_id).first()
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

def start_game_draft(chat_id: int):
    try:
        with session.begin():
            draft = session.query(Draft).filter(Draft.chat_id == chat_id).first()
            if not draft:
                return False, "no game", -1

            if draft.state != 0:
                return False, "state error", -1

            player_ids = session.query(DraftPlayer).with_entities(DraftPlayer.id).filter(DraftPlayer.draft_id == draft.chat_id).all()

            if not player_ids:
                session.delete(draft)
                session.query(Game).filter(Game.chat_id == chat_id).delete()
                return False, "no players associated with the game", -1

            num_players = len(player_ids)

            if num_players < 2 or num_players != draft.num_players:
                session.delete(draft)
                session.query(Game).filter(Game.chat_id == chat_id).delete()
                return False, "number of players is less than 2 or not as expected", -1

            teams = []
            for player_id in player_ids:
                teams.append(DraftPlayerTeam(player_id=player_id[0], chat_id=chat_id))

            draft.state = 1
            session.add_all(teams)

            return True, "", num_players
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", -1

def set_game_states_draft(chat_id:int, player_id:int, category:str, teams:list[str], formation:str):
    try:
        with session.begin():
            game = session.query(Draft).filter(Draft.chat_id == chat_id).first()
            if not game:
                return False , "no game found", [-1]

            if game.state != 1 or teams == None:
                return False, "game error", [game.num_players]

            if not category:
                return False, "no category error", [game.num_players]

            if len(teams) != (11 + game.num_players):
                return False, "num of teams error", [game.num_players]

            if FORMATIONS.get(formation, None) == None:
                return False, "formation error", [game.num_players]

            if len(set(teams)) != len(teams):
                return False, "duplicate teams error", [game.num_players]

            if not session.query(DraftPlayer).filter(DraftPlayer.player_id == player_id, DraftPlayer.draft_id == chat_id).limit(1):
                return False, "player not in game", [game.num_players]

            game.formation_name = formation
            teams = [team.lower().strip() for team in teams]

            existing_teams = [team for team in session.query(Team).all()]
            existing_teams_names = [team.name for team in existing_teams]

            teams_to_add = [Team(name=team) for team in teams if team not in existing_teams_names]
            
            session.add_all(teams_to_add)
            session.flush()  
            
            all_teams = existing_teams + teams_to_add

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
                return False, "game error", [game.num_players]

            player_id_ = player.player_id
            game.current_player_id = player.id
            game.picking_player_id = player.id

            game.state = 2
            other = [game.num_players, game.category, game.formation_name, " ".join([team.name for team in game.teams]), player_id_]
            session.commit()

            return True, "", other
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "expection", [-1]

def add_pos_to_team_draft(chat_id:int, player_id:int, added_player:str):
    try:
        with session.begin():
            game = session.query(Draft).filter(Draft.chat_id == chat_id).first()
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

def rand_team_draft(chat_id:int, player_id:int):
    try:
        with session.begin():
            game = session.query(Draft).filter(Draft.chat_id == chat_id).first()
            if not game:
                return False , "no game found", "", "", ""

            player = session.query(DraftPlayer).filter(DraftPlayer.player_id == player_id,
                                                       DraftPlayer.draft_id == chat_id).first()
            if not player:
                return False, "player not in game", "", "", ""
            
            if game.state != 2:
                return False, "game error", "", "", ""

            if game.picking_player_id != player.id:
                return False, "curr_player_error", "", "", ""

            session.query(DraftPlayer).filter(DraftPlayer.id == game.picking_player_id).update({"picking":True})
            non_picked_teams = session.execute(
                select(draft_team_association).where(draft_team_association.c.picked == False,
                                                     draft_team_association.c.draft_id == chat_id)
            ).fetchall()
            if len(non_picked_teams) == 0:
                return False, "game error", "", "", ""

            rand_team = non_picked_teams[randint(0, len(non_picked_teams) - 1)]
            game.curr_team_id = rand_team.team_id
            team_instance = session.query(Team).filter(Team.id == rand_team.team_id).first()
            if not team_instance:
                return False, "", "", "", ""

            team_name = team_instance.name
            formation = game.formation_name
            curr_pos = game.curr_pos
            session.commit()

            return True, "", team_name, formation, curr_pos
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "expection", "", "", ""

def end_game_draft(chat_id:int):
    try:
        with session.begin():
            game = session.query(Game).filter(Game.chat_id == chat_id).first()
            draft = session.query(Draft).filter(Draft.chat_id == chat_id).first()
            if not draft or not game:
                return False, "no game found", None, None

            formation = draft.formation_name
            #formation = session.query(d.formation_name).filter(d.chat_id == chat_id).first()
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
            if not players or not formation:
                session.delete(game)
                session.delete(draft)
                return False, "no players no formation" , None, None

            session.delete(game)
            session.delete(draft)
            return True, "", teams, formation
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception", None, None

def cancel_game_draft(chat_id:int):
    try:
        with session.begin():
            game = session.query(Game).filter(Game.chat_id == chat_id).first()
            draft = session.query(Draft).filter(Draft.chat_id == chat_id).first()

            if not game or not draft:
                return False, "no game found"

            session.delete(game)
            session.delete(draft)
            return True, ""
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception"

