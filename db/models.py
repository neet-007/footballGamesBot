from sqlalchemy import Boolean, Column, ForeignKey, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, String, Table
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

class Base(DeclarativeBase):
    pass

class Foo(Base):
    __tablename__ = "foo"
    id: Mapped[str] = mapped_column(primary_key=True)
    bar: Mapped[str] = mapped_column(String(100))
    def __repr__(self) -> str:
        return f"Item(id={self.id!r}, bar={self.bar!r})"

player_draft_association= Table(
    "player_draft", Base.metadata,
    Column('player_id', Integer, ForeignKey('player.player_id')),
    Column('draft_id', Integer, ForeignKey('draft.chat_id')),
    Column('picked', Boolean, default=False)
)

draft_team_association = Table(
    "draft_team", Base.metadata,
    Column('draft_id', Integer, ForeignKey('draft.chat_id')),
    Column('team_id', Integer, ForeignKey('team.id'))
)

class Player(Base):
    __tablename__ = "player"
    player_id:Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id:Mapped[int] = mapped_column(Integer, primary_key=True)
    game_where_curr = relationship("Draft", back_populates="curr_player")
    drafts = relationship("Draft", secondary=player_draft_association, back_populates="players")
    team = relationship("PlayerTeam", back_populates="player")

    __table_args__ = (
        PrimaryKeyConstraint(
            "player_id",
            "chat_id"
        ),
    )

class Draft(Base):
    __tablename__ = "draft"
    chat_id:Mapped[int] = mapped_column(Integer, primary_key=True)
    num_players:Mapped[int] = mapped_column(Integer, nullable=False)
    category:Mapped[str] = mapped_column(String(50), nullable=False)
    formation_name:Mapped[str] = mapped_column(String(8), nullable=False)

    teams = relationship("Team", secondary=draft_team_association, back_populates="drafts")
    players = relationship("Player", secondary=player_draft_association, back_populates="drafts")
    start_player_idx:Mapped[int] = mapped_column(Integer, nullable=False)

    player_id:Mapped[int] = mapped_column(Integer, nullable=False)
    chat_key_id:Mapped[int] = mapped_column(Integer, nullable=False)
    curr_player = relationship("Player", back_populates="game_where_curr")

    state:Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    curr_pos:Mapped[str] = mapped_column(String(3), nullable=False, default="p1")

    __table_args__ = (
        ForeignKeyConstraint(
            ["player_id", "chat_key_id"],
            ["player.player_id", "player.chat_id"]
        ),
    )

class Team(Base):
    __tablename__ = "team"
    id:Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name:Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    drafts = relationship("Draft", secondary=draft_team_association, back_populates="teams")

class PlayerTeam(Base):
    __tablename__ = "player_team"
    chat_id:Mapped[int] = mapped_column(Integer, primary_key=True)

    player_id:Mapped[int] = mapped_column(Integer, nullable=False)
    chat_key_id:Mapped[int] = mapped_column(Integer, nullable=False)
    player = relationship("Player", back_populates="team")

    p1:Mapped[str] = mapped_column(String(50), nullable=False)
    p2:Mapped[str] = mapped_column(String(50), nullable=False)
    p3:Mapped[str] = mapped_column(String(50), nullable=False)
    p4:Mapped[str] = mapped_column(String(50), nullable=False)
    p5:Mapped[str] = mapped_column(String(50), nullable=False)
    p6:Mapped[str] = mapped_column(String(50), nullable=False)
    p7:Mapped[str] = mapped_column(String(50), nullable=False)
    p8:Mapped[str] = mapped_column(String(50), nullable=False)
    p9:Mapped[str] = mapped_column(String(50), nullable=False)
    p10:Mapped[str] = mapped_column(String(50), nullable=False)
    p11:Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["player_id", "chat_key_id"],
            ["player.player_id", "player.chat_id"]
        ),
    )


