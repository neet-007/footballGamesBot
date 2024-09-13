from sqlalchemy import Integer, String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.types import JSON

class Base(DeclarativeBase):
    pass

class Foo(Base):
    __tablename__ = "foo"
    id: Mapped[str] = mapped_column(primary_key=True)
    bar: Mapped[str] = mapped_column(String(100))
    def __repr__(self) -> str:
        return f"Item(id={self.id!r}, bar={self.bar!r})"

class Draft(Base):
    __tablename__ = "draft"
    chat_id:Mapped[int] = mapped_column(Integer(), primary_key=True)
    num_players:Mapped[int] = mapped_column(Integer())
    category:Mapped[str] = mapped_column(String(50))
    formation_name:Mapped[str] = mapped_column(String(4))
    teams:Mapped[list] = mapped_column(JSON())
    picked_teams:Mapped[list] = mapped_column(JSON())
    players_ids:Mapped[list] = mapped_column(JSON())
    start_player_idx:Mapped[int] = mapped_column(Integer())
    curr_player_idx:Mapped[int] = mapped_column(Integer())
    state:Mapped[int] = mapped_column(Integer())
    curr_team_idx:Mapped[int] = mapped_column(Integer())
    curr_pos:Mapped[str] = mapped_column(String(4))

class Formation(Base):
    __tablename__ = "formation"
    chat_id:Mapped[int] = mapped_column(Integer(), primary_key=True)
    p1:Mapped[str] = mapped_column(String(50))
    p2:Mapped[str] = mapped_column(String(50))
    p3:Mapped[str] = mapped_column(String(50))
    p4:Mapped[str] = mapped_column(String(50))
    p5:Mapped[str] = mapped_column(String(50))
    p6:Mapped[str] = mapped_column(String(50))
    p7:Mapped[str] = mapped_column(String(50))
    p8:Mapped[str] = mapped_column(String(50))
    p9:Mapped[str] = mapped_column(String(50))
    p10:Mapped[str] = mapped_column(String(50))
    p11:Mapped[str] = mapped_column(String(50))


