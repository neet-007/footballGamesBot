from typing import Optional, Union
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
import telegram
import telegram.ext
from typing import Literal 
from random import shuffle, randint
from db.connection import get_session, new_db
from db.models import Draft as d, DraftPlayer, DraftPlayerTeam, Game, Team, draft_team_association
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

def new_game_draft(chat_id: int, session: Session):
    try:
        with session.begin():
            new_db()
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

            player_db = session.query(DraftPlayer).filter(DraftPlayer.player_id == player_id).first()
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
                return False, "no game"

            if draft.state != 0:
                return False, "game has started"

            player_ids = session.query(DraftPlayer).with_entities(DraftPlayer.player_id).filter(DraftPlayer.draft_id == draft.chat_id).all()

            if not player_ids:
                return False, "no players associated with the game"

            num_players = len(player_ids)

            if num_players < 2 or num_players != draft.num_players:
                return False, "number of players is less than 2 or not as expected"

            teams = [DraftPlayerTeam(player_id=player_id[0]) for player_id in player_ids]

            draft.state = 1
            session.add_all(teams)

            return True, ""
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "exception"

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

            teams_ = [Team()] * len(teams)
            draft_teams = [{}] * len(teams)
            for i in range(len(teams)):
                team = Team(
                    name=teams[i],
                    
                )

                teams_[i] = team

            session.add_all(teams_)
            session.flush()
 
            for i in range(len(teams)):
                draft_teams[i] = {
                    "team_id":teams_[i].id,
                    "draft_id":game.chat_id
                }

            session.execute(
                draft_team_association.insert(),
                draft_teams
            )

            game.category = category
            
            #do this
            player_id_ = session.query(DraftPlayer).filter(DraftPlayer.draft_id == chat_id).first()
            if not player_id_:
                return False, "game error", []

            player_id_ = player_id_.player_id
            game.current_player_id = player_id
            #self.curr_player_idx = 0
            #shuffle(self.players_ids)

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
                return False , "no game found", [None, None, None]

            if game.state != 2:
                return False, "game error", [None, None, None]

            player = session.query(DraftPlayer).with_entities(DraftPlayer.player_id).filter(DraftPlayer.player_id == player_id).first()
            
            if not player:
                return False, "player not in game", [None, None, None]
            
            if game.current_player_id != player_id:
                return False, "curr_player_error", [None, None, None]

            #this is not right
            curr_team = session.execute(draft_team_association.select().filter(draft_team_association.c.draft_id == chat_id,
                                                                      draft_team_association.c.team_id == game.curr_team_id)).first()
            if not curr_team or curr_team.picked:
                return False, "picked_team_error", [None, None, None]

            #this also not right
            player_team = session.query(DraftPlayerTeam).filter(
                DraftPlayerTeam.player_id == player[0],
            ).first()

            if not player_team:
                return False, "player does not exist in team", [None, None, None]

            if getattr(player_team, game.curr_pos):
                return False, "picked_pos_error", [None, None, None]

            added_player_lower = added_player.lower()
            position_filter = or_(
                PlayerTeam.p1.ilike(added_player_lower),
                PlayerTeam.p2.ilike(added_player_lower),
                PlayerTeam.p3.ilike(added_player_lower),
                PlayerTeam.p4.ilike(added_player_lower),
                PlayerTeam.p5.ilike(added_player_lower),
                PlayerTeam.p6.ilike(added_player_lower),
                PlayerTeam.p7.ilike(added_player_lower),
                PlayerTeam.p8.ilike(added_player_lower),
                PlayerTeam.p9.ilike(added_player_lower),
                PlayerTeam.p10.ilike(added_player_lower),
                PlayerTeam.p11.ilike(added_player_lower)
            )

            matching_player_teams = session.query(PlayerTeam).filter(
                PlayerTeam.chat_id == chat_id,
                position_filter
            ).all()

            if matching_player_teams:
                return False, "taken player error", [None, None, None]
                    
            setattr(player_team, game.curr_pos, added_player_lower)
            
            session.query(DraftPlayer).filter(DraftPlayer.player_id == player_id).update({"picked": True})

            session.flush()
            non_picked_players = session.query(DraftPlayer).filter(DraftPlayer.draft_id == chat_id, DraftPlayer.picked == False).all()

            if len(non_picked_players) == 0:
                if game.curr_pos == "p11":
                    game.state = 3
                    other = [game.current_player_id, game.formation_name, game.curr_pos]
                    return True,"end_game", other

                session.query(DraftPlayer).filter(DraftPlayer.draft_id == chat_id).update({"picked": False})
                non_picked_players = session.query(DraftPlayer).filter(DraftPlayer.draft_id == chat_id, DraftPlayer.picked == False).all()

                game.current_player_id = non_picked_players[randint(0, len(non_picked_players) - 1)].player_id
                session.execute(
                    draft_team_association.update()
                    .where(
                        draft_team_association.c.draft_id == chat_id,
                        draft_team_association.c.team_id == game.curr_team_id
                    )
                    .values(picked=True)
                )
                print("GAME CURR POS BEFORE", game.curr_pos)
                game.curr_pos = "p" + f"{int(game.curr_pos[1]) + 1}" if len(game.curr_pos) == 2 else  "p" + f"{int(game.curr_pos[1:3]) + 1}"
                print("GAME CURR POS AFTER", game.curr_pos)
                other = [game.current_player_id, game.formation_name, game.curr_pos]
                session.commit()
                return True, "new_pos", other

            game.current_player_id = non_picked_players[randint(0, len(non_picked_players) - 1)].player_id
            other = [game.current_player_id, game.formation_name, game.curr_pos]
            return True, "same_pos", other
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "expection", [None, None, None]

def rand_team_draft(chat_id:int, player_id:int, session:Session):
    try:
        with session.begin():
            game = session.query(d).filter(d.chat_id == chat_id).first()
            if not game:
                return False , "no game found", "", ""

            if not session.query(DraftPlayer).filter(DraftPlayer.player_id == player_id).first():
                return False, "player not in game", "", ""
            
            if game.state != 2:
                return False, "game error", "", ""

            if game.current_player_id != player_id:
                return False, "curr_player_error", "", ""

            non_picked_teams = session.execute(
                select(draft_team_association).where(draft_team_association.c.picked == False)
            ).fetchall()
            if len(non_picked_teams) == 0:
                return False, "game error", "", ""

            rand_team = non_picked_teams[randint(0, len(non_picked_teams) - 1)]
            print("rand_team", rand_team)
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

def end_game_draft(chat_id:int, votes:dict[int, int]):
    try:
        with session.begin():
            game = session.query(Game).filter(Game.chat_id == chat_id).first
            draft = session.query(d).filter(d.chat_id == chat_id).first()
            if not game or not draft:
                session.delete(game)
                session.delete(draft)
                return False , "no game found"

            if draft.state != 3:
                return []

            max_vote = float("-inf")
            max_vote_ids = []
            for id, vote_count in votes.items():
                if vote_count > max_vote:
                    max_vote = vote_count
                    max_vote_ids.clear()
                    max_vote_ids.append(id)
                elif vote_count == max_vote:
                    max_vote_ids.append(id)

            session.commit()
            session.delete(game)
            session.delete(draft)
            return max_vote_ids
    except Exception as e:
        print(f"An error occurred: {e}")
        return False, "expection"

class Draft():
    def __init__(self) -> None:
        self.players = {}
        self.num_players = 0
        self.category = ""
        self.formation = ["", {}]
        self.teams = None
        self.picked_teams = None
        self.players_ids = []
        self.start_player_idx = -1
        self.curr_player_idx = -1
        self.state = 0
        self.curr_pos = "p1"
        self.curr_team_idx = -1

    def join_game(self, player:telegram.User):
        if self.state != 0 or player.id in self.players:
            return False

        self.players[player.id] = [player, {"p1":None, "p2":None, "p3":None, "p4":None, "p5":None,
                                            "p6":None, "p7":None, "p8":None, "p9":None, "p10":None,
                                            "p11":None}]
        self.players_ids.append(player.id)
        self.num_players += 1

        return True

    def start_game(self):
        if self.state != 0 or self.num_players < 2:
            return False

        self.teams = [""] * (11 + self.num_players)
        self.picked_teams = [False] * len(self.teams)
        self.state = 1
        return True

    def set_game_states(self, category:str, teams:list[str], formation:str) -> tuple[bool, Literal["game error", "no category error", "num of teams error", "formation error", "duplicate teams error", ""]]:
        if self.state != 1 or self.teams == None:
            return False, "game error"
        if not category:
            return False, "no category error"
        if len(teams) != (11 + self.num_players):
            return False, "num of teams error"
        formation_ = FORMATIONS.get(formation, None)
        if formation_ == None:
            return False, "formation error"

        if len(set(teams)) != len(teams):
            return False, "duplicate teams error"

        self.formation[0] = formation
        self.formation[1] = formation_

        for i in range(len(teams)):
            self.teams[i] = teams[i].strip()

        self.category = category
        self.start_player_idx = 0
        self.curr_player_idx = 0
        shuffle(self.players_ids)
        self.state = 2

        return True, ""

    def add_pos_to_team(self, player:telegram.User, added_player:str) -> tuple[bool, Literal["game_error", "curr_player_error", "picked_team_error", "picked_pos_error", "taken_player_error", "new_pos", "same_pos", "end_game"]]:
        if self.state != 2 or (not player.id in self.players) or self.picked_teams == None:
            return False, "game_error"

        if self.players_ids[self.curr_player_idx] != player.id:
            return False, "curr_player_error"

        if self.picked_teams[self.curr_team_idx]:
            return False, "picked_team_error"

        player_ = self.players[player.id]
        if player_[1][self.curr_pos] != None:
            return False, "picked_pos_error"

        if added_player.lower() in [
            value
            for player in self.players.values() 
            for value in player[1].values()
        ]:
            return False, "taken_player_error"

        player_[1][self.curr_pos] = added_player.lower()
        if self.curr_player_idx == (self.start_player_idx + self.num_players - 1) % self.num_players:
            if self.curr_pos == "p11":
                self.state = 3
                return True, "end_game"

            self.start_player_idx = (self.start_player_idx + 1) % self.num_players
            self.picked_teams[self.curr_team_idx] = True
            self.curr_pos = "p" + f"{int(self.curr_pos[1]) + 1}" if len(self.curr_pos) == 2 else  "p" + f"{int(self.curr_pos[1:3]) + 1}"
            return True, "new_pos"

        self.curr_player_idx = (self.curr_player_idx + 1) % self.num_players
        return True, "same_pos"

    def rand_team(self, player_id):
        if self.state != 2 or self.picked_teams == None or self.teams == None:
            return ""

        if player_id != self.players_ids[self.start_player_idx]:
            return ""

        self.curr_team_idx = randint(0, len(self.teams) - 1)
        while self.picked_teams[self.curr_team_idx]:
            self.curr_team_idx = randint(0, len(self.teams) - 1)

        return self.teams[self.curr_team_idx]

    def end_game(self, votes:dict[int, int]):
        if self.state != 3:
            return []

        max_vote = float("-inf")
        max_vote_ids = []
        for id, vote_count in votes.items():
            if vote_count > max_vote:
                max_vote = vote_count
                max_vote_ids.clear()
                max_vote_ids.append(id)
            elif vote_count == max_vote:
                max_vote_ids.append(id)

        return [self.players[x] for x in max_vote_ids]

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

class GuessThePlayer:
    def __init__(self) -> None:
        self.players = {}
        self.muted_players:list[int] = []
        self.players_ids:list[int] = []
        self.curr_player_idx:int = -1
        self.num_players:int = 0 
        self.curr_hints:list[str] = ["","","",]
        self.curr_answer:str = ""
        self.curr_asking_player:int = -1
        self.curr_question = ""
        self.asked_questions = {}
        self.state:int = 0
        self.winner_id:int = -1

    def join_game(self, player:telegram.User):
        if self.state != 0:
            return False
        if player.id in self.players:
            return False
        self.num_players += 1
        self.players[player.id] = [player, 3, 3, 0]
        self.players_ids.append(player.id)
        return True

    def leave_game(self, player:telegram.User):
        try:
            del self.players[player.id]
        except KeyError:
            return False, "player not in game error"

        self.num_players -= 1
        idx = self.players_ids.index(player.id)
        self.players_ids.remove(player.id)
        if player.id in self.muted_players:
            self.muted_players.remove(player.id)

        if self.num_players == 1:
            self.state = 4
            self.winner_id = -2
            return False, "end game"
            
        if len(self.muted_players) == self.num_players or self.curr_player_idx == idx:
            self.winner_id = -2
            self.state = 3
            return False, "end round"

        return True, ""

    def start_game(self):
        if self.state != 0:
            return False, "game error"
        if self.num_players < PLAYERS_COUNT:
            return False, "num players error"
    
        shuffle(self.players_ids)
        self.curr_player_idx = 0
        self.state = 1
        return True, ""

    def start_round(self, player: telegram.User, curr_hints:list[str], curr_answer:str):
        if self.state != 1 and self.state != 3:
            return False, "game error"
        if len(curr_hints) != 3:
            return False, "num hints error"
        if self.players[self.players_ids[self.curr_player_idx]][0].id != player.id:
            return False, "curr player error"
        if curr_hints == ["", "", ""] or curr_answer == "":
            return False, "empty inputs"

        self.curr_answer = curr_answer.strip().lower()
        self.curr_hints = [hint.strip().capitalize() for hint in curr_hints]
        self.state = 2

        return True, ""

    def ask_question(self, player:telegram.User, question:str):
        if self.state != 2:
            return False, "game_error"

        if self.curr_asking_player != -1:
            return False, "there is askin player error"

        if self.players[self.players_ids[self.curr_player_idx]][0].id == player.id:
            return False, "curr player error"

        if self.players[player.id][1] <= 0:
            return False, "no questions"

        self.curr_question = question.lower().strip()
        self.curr_asking_player = player.id
        return True, ""

    def answer_question(self, player:telegram.User, player_asked:telegram.User, question:str, answer:str):
        if self.state != 2:
            return False, "game error"
    
        if self.curr_asking_player == -1:
            return False, "no asking player error"

        if self.curr_asking_player != player_asked.id:
            return False, "player is not the asking error"

        question = question.lower().strip()
        if self.curr_question != question:
            return False, "not the question"

        if self.players[self.players_ids[self.curr_player_idx]][0].id != player.id:
            return False, "curr player error"

        self.asked_questions[question] = answer.lower().strip()
        self.players[self.curr_asking_player][1] -= 1
        self.curr_asking_player = -1
        self.curr_question = ""

        return True, ""

    def proccess_answer(self, player:telegram.User, answer:str):
        if self.state != 2:
            return False, "game error"

        if self.players[self.players_ids[self.curr_player_idx]][0].id == player.id:
            return False, "curr player error"

        player_ = self.players[player.id]
        if player.id in self.muted_players:
            return False, "muted player"

        player_[2] -= 1
        if player_[2] == 0:
            self.muted_players.append(player.id)

        print(answer.strip().lower(), self.curr_answer, jaro_winkler_similarity(answer.strip().lower(), self.curr_answer))
        score = jaro_winkler_similarity(answer.strip().lower(), self.curr_answer)
        if (len(answer.lower().strip()) > 10 and score > 0.85) or (len(answer.lower().strip()) <= 10 and score > 0.92):
            self.state = 3
            self.winner_id = player.id
            return True, "correct"

        if len(self.muted_players) == self.num_players - 1:
            self.state = 3
            self.winner_id = -1
            return True, "all players muted"

        return True, "false"

    def end_round(self):
        if self.state != 3:
            return False, "game error"

        if self.winner_id == -1:
            self.players[self.players_ids[self.curr_player_idx]][3] += 1
        elif self.winner_id == -2:
            pass
        else: 
            self.players[self.winner_id][3] += 1

        self.curr_hints = ["","","",]
        for id, player in self.players.items():
            self.players[id] = [player[0], 3, 3, player[3]]
        self.curr_answer = ""
        self.winner_id = -1
        self.asked_questions = {}
        self.muted_players = []
        self.curr_state = 2

        self.curr_player_idx += 1
        if self.curr_player_idx == self.num_players:
            self.state = 4
            return True, "game end"

        return True, "round end"

    def end_game(self):
        scores = {player[0]:player[3] for player in self.players.values()}
        winners = ""
        max_score = float('-inf')
        for player, score in scores.items():
            if score == max_score:
                winners += f"{player.mention_html()}\n"
            if score > max_score:
                max_score = score
                winners = ""
                winners += f"{player.mention_html()}\n"

        self.players = {}
        self.curr_hints = ["", "", ""]
        self.curr_answer = ""
        self.curr_player_idx = -1
        self.state = 0
        self.muted_players = []
        self.asked_questions = {}
        self.winner_id = -1
        return scores, winners


games:dict[int, Optional[Union[GuessThePlayer, Draft, Wilty]]] = {}


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
