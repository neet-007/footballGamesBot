from random import shuffle

from telegram import User


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

    def join_game(self, player: User):
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

    def get_statements(self, player: User, statements:list[str]):
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

    def get_mod_statement(self, player:User, statement:str):
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
