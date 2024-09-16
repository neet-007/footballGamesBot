from datetime import datetime
from sqlalchemy import TIMESTAMP, Boolean, Column, ForeignKey, ForeignKeyConstraint, Integer, String, Table, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

draft_team_association = Table(
    "draft_team", Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("draft_id", Integer, ForeignKey('draft.chat_id'), nullable=False),
    Column("team_id", Integer, ForeignKey('team.id'), nullable=False),
    Column("picked", Boolean, default=False),
    UniqueConstraint("draft_id", "team_id", name="uq_draft_team")
)

class Game(Base):
    __tablename__ = "game"
    chat_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_id:Mapped[int] = mapped_column(Integer, ForeignKey("draft.chat_id"), nullable=True)
    draft = relationship("Draft", uselist=False, back_populates="game")
    #guess_the_player_id:Mapped[int] = mapped_column(Integer, ForeignKey("draft.chat_id"), nullable=True)
    #guess_the_player = relationship("GuessThePlayer", uselist=False, back_populates="game")

class Draft(Base):
    __tablename__ = "draft"
    chat_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    num_players: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(50), nullable=True)
    formation_name: Mapped[str] = mapped_column(String(8), nullable=True)

    game = relationship("Game", uselist=False, back_populates="draft")
    players = relationship("DraftPlayer", backref="draft")

    teams = relationship("Team", secondary=draft_team_association, back_populates="drafts")

    current_player = relationship("DraftPlayer", uselist=False, back_populates="draft_current", overlaps="players,draft")
    picking_player = relationship("DraftPlayer", uselist=False, back_populates="draft_picking", overlaps="current_player,players,draft")

    curr_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("team.id"), nullable=True)

    state: Mapped[int] = mapped_column(Integer, default=0)
    curr_pos: Mapped[str] = mapped_column(String(3), default="p1")

class Team(Base):
    __tablename__ = "team"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    drafts = relationship("Draft", secondary=draft_team_association, back_populates="teams")

class DraftPlayer(Base):
    __tablename__ = "draft_player"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer)
    draft_id: Mapped[int] = mapped_column(Integer, ForeignKey('draft.chat_id'))
    picked: Mapped[bool] = mapped_column(Boolean, default=False)
    time_join: Mapped[datetime] = mapped_column(TIMESTAMP, default=func.now())

    draft_current = relationship("Draft", uselist=False, back_populates="current_player", overlaps="draft,picking_player,players")
    draft_picking = relationship("Draft", uselist=False, back_populates="picking_player", overlaps="current_player,draft,draft_current,players")
    team = relationship("DraftPlayerTeam", uselist=False, back_populates="player", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "draft_id",
            name="uq_player_draft"
        ),
    )

class DraftPlayerTeam(Base):
    __tablename__ = "draft_player_team"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey('draft_player.id', ondelete='CASCADE'))
    chat_id: Mapped[int] = mapped_column(Integer)
    player = relationship("DraftPlayer", uselist=False, back_populates="team")

    p1: Mapped[str] = mapped_column(String(50), nullable=True)
    p2: Mapped[str] = mapped_column(String(50), nullable=True)
    p3: Mapped[str] = mapped_column(String(50), nullable=True)
    p4: Mapped[str] = mapped_column(String(50), nullable=True)
    p5: Mapped[str] = mapped_column(String(50), nullable=True)
    p6: Mapped[str] = mapped_column(String(50), nullable=True)
    p7: Mapped[str] = mapped_column(String(50), nullable=True)
    p8: Mapped[str] = mapped_column(String(50), nullable=True)
    p9: Mapped[str] = mapped_column(String(50), nullable=True)
    p10: Mapped[str] = mapped_column(String(50), nullable=True)
    p11: Mapped[str] = mapped_column(String(50), nullable=True)
