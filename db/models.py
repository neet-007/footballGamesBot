from sqlalchemy import Boolean, Column, ForeignKey, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, String, Table, UniqueConstraint, null
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

player_draft_association = Table(
    "player_draft", Base.metadata,
    Column('player_id', Integer, nullable=False),
    Column('chat_key_id', Integer, nullable=False),
    Column('draft_id', Integer, ForeignKey('draft.chat_id'), nullable=False),
    Column('picked', Boolean, default=False),
    ForeignKeyConstraint(
        ['player_id', 'chat_key_id'],
        ['player.player_id', 'player.chat_id']
    ),
    PrimaryKeyConstraint('player_id', 'draft_id')  
)

draft_team_association = Table(
    "draft_team", Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("draft_id", Integer, ForeignKey('draft.chat_id'), nullable=False),
    Column("team_id", Integer, ForeignKey('team.id'), nullable=False),
    Column("picked", Boolean, default=False),
    UniqueConstraint("draft_id", "team_id", name="uq_draft_team")
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
    num_players:Mapped[int] = mapped_column(Integer, default=0)
    category:Mapped[str] = mapped_column(String(50), nullable=True)
    formation_name:Mapped[str] = mapped_column(String(8), nullable=True)

    teams = relationship("Team", secondary=draft_team_association, back_populates="drafts")
    players = relationship("Player", secondary=player_draft_association, back_populates="drafts")
    start_player_idx:Mapped[int] = mapped_column(Integer, nullable=True)

    player_id:Mapped[int] = mapped_column(Integer, nullable=True)
    chat_key_id:Mapped[int] = mapped_column(Integer, nullable=True)
    curr_player = relationship("Player", back_populates="game_where_curr")

    curr_team_id:Mapped[int] = mapped_column(Integer, nullable=True)
    curr_team = relationship("Team", back_populates="draft_where_curr")

    state:Mapped[int] = mapped_column(Integer, default=0)
    curr_pos:Mapped[str] = mapped_column(String(3), default="p1")

    __table_args__ = (
        ForeignKeyConstraint(
            ["player_id", "chat_key_id"],  
            ["player.player_id", "player.chat_id"],  
        ),
        ForeignKeyConstraint(
            ["curr_team_id"],  
            ["team.id"], 
        ),
    )

class Team(Base):
    __tablename__ = "team"
    id:Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name:Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    drafts = relationship("Draft", secondary=draft_team_association, back_populates="teams")
    draft_where_curr = relationship("Draft", back_populates="curr_team")

class PlayerTeam(Base):
    __tablename__ = "player_team"
    id:Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id:Mapped[int] = mapped_column(Integer)

    player_id:Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    chat_key_id:Mapped[int] = mapped_column(Integer, nullable=False)
    player = relationship("Player", back_populates="team")

    p1:Mapped[str] = mapped_column(String(50), nullable=True, default=null())
    p2:Mapped[str] = mapped_column(String(50),  nullable=True, default=null())
    p3:Mapped[str] = mapped_column(String(50), nullable=True, default=null())
    p4:Mapped[str] = mapped_column(String(50), nullable=True, default=null())
    p5:Mapped[str] = mapped_column(String(50), nullable=True, default=null())
    p6:Mapped[str] = mapped_column(String(50), nullable=True, default=null())
    p7:Mapped[str] = mapped_column(String(50), nullable=True, default=null())
    p8:Mapped[str] = mapped_column(String(50), nullable=True, default=null())
    p9:Mapped[str] = mapped_column(String(50), nullable=True, default=null())
    p10:Mapped[str] = mapped_column(String(50), nullable=True, default=null())
    p11:Mapped[str] = mapped_column(String(50), nullable=True, default=null())

    __table_args__ = (
        ForeignKeyConstraint(
            ["player_id", "chat_key_id"],
            ["player.player_id", "player.chat_id"]
        ),
    )


