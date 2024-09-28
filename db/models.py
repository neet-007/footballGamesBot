from datetime import datetime
from typing import Optional
from sqlalchemy import JSON, TIMESTAMP, Boolean, Column, ForeignKey, Integer, PrimaryKeyConstraint, String, Table, UniqueConstraint, func, null, text
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

draft_team_association = Table(
    "draft_team", Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("draft_id", Integer, ForeignKey('draft.chat_id', ondelete="CASCADE"), nullable=False),
    Column("team_id", Integer, ForeignKey('team.id', ondelete="CASCADE"), nullable=False),
    Column("picked", Boolean, default=False),
    UniqueConstraint("draft_id", "team_id", name="uq_draft_team")
)

guess_the_player_guess_the_player_player_association = Table(
    "guess_the_player_guess_the_player_player", Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("guess_the_player_id", Integer, ForeignKey('guess_the_player.chat_id', ondelete="CASCADE"), nullable=False),
    Column("guess_the_player_player_id", Integer, ForeignKey('guess_the_player_player.id', ondelete="CASCADE"), nullable=False),
    Column("guess_the_player_player_player_id", Integer, nullable=False),
    Column("time_created", TIMESTAMP(timezone=True), server_default=func.now(text('6'))),
    UniqueConstraint("guess_the_player_id", "guess_the_player_player_id", name="uq_guess_the_player_guess_the_player_player")
)

class Game(Base):
    __tablename__ = "game"
    chat_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_id:Mapped[int] = mapped_column(Integer, ForeignKey("draft.chat_id", ondelete="CASCADE"), nullable=True)
    draft = relationship("Draft", uselist=False, back_populates="game")
    guess_the_player_id:Mapped[int] = mapped_column(Integer, ForeignKey("guess_the_player.chat_id", ondelete="CASCADE"), nullable=True)
    guess_the_player = relationship("GuessThePlayer", uselist=False, back_populates="game")

class GuessThePlayer(Base):
    __tablename__ = "guess_the_player"
    chat_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    num_players: Mapped[int] = mapped_column(Integer, default=0)
    curr_answer:Mapped[str] = mapped_column(String(40), default="")
    curr_question:Mapped[str] = mapped_column(String(40), default="")
    state: Mapped[int] = mapped_column(Integer, default=0)
    curr_hints: Mapped[list[str]] = mapped_column(JSON, default=["", "", ""])

    game = relationship("Game", uselist=False, cascade="all, delete-orphan")

    players = relationship("GuessThePlayerPlayer", backref="GuessThePlayer", foreign_keys="GuessThePlayerPlayer.guess_the_player_id",
                           cascade="all, delete-orphan")

    current_players = relationship(
        "GuessThePlayerPlayer",
        secondary=guess_the_player_guess_the_player_player_association,
        primaryjoin="GuessThePlayer.chat_id == guess_the_player_guess_the_player_player.c.guess_the_player_id",
        secondaryjoin="GuessThePlayerPlayer.id == guess_the_player_guess_the_player_player.c.guess_the_player_player_id",
        back_populates="guess_the_players",
        cascade="all"
    )

    current_player_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("guess_the_player_player.id", ondelete="SET NULL", use_alter=True), nullable=True)
    asking_player_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("guess_the_player_player.id", ondelete="SET NULL", use_alter=True), nullable=True)
    winning_player_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("guess_the_player_player.id", ondelete="SET NULL", use_alter=True), nullable=True)

    asked_questions = relationship("AskedQuestions", backref="guess_the_player", cascade="all, delete-orphan")

class Draft(Base):
    __tablename__ = "draft"
    chat_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    num_players: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(50), nullable=True)
    formation_name: Mapped[str] = mapped_column(String(8), nullable=True)

    game = relationship("Game", uselist=False, cascade="all, delete-orphan")

    players = relationship("DraftPlayer", backref="draft", foreign_keys="DraftPlayer.draft_id", cascade="all, delete-orphan")

    teams = relationship("Team", secondary=draft_team_association, back_populates="drafts", cascade="save-update")

    current_player_id: Mapped[int] = mapped_column(Integer, ForeignKey("draft_player.id", ondelete="SET NULL", use_alter=True), nullable=True)
    picking_player_id: Mapped[int] = mapped_column(Integer, ForeignKey("draft_player.id", ondelete="SET NULL", use_alter=True), nullable=True)
    curr_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("team.id", ondelete="SET NULL", use_alter=True), nullable=True)

    state: Mapped[int] = mapped_column(Integer, default=0)
    curr_pos: Mapped[str] = mapped_column(String(3), default="p1")


class GuessThePlayerPlayer(Base):
    __tablename__ = "guess_the_player_player"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer)
    guess_the_player_id: Mapped[int] = mapped_column(Integer, ForeignKey('guess_the_player.chat_id', ondelete="CASCADE", use_alter=True))

    picked: Mapped[bool] = mapped_column(Boolean, default=False)
    muted: Mapped[bool] = mapped_column(Boolean, default=False)
    questions: Mapped[int] = mapped_column(Integer, default=3)
    answers: Mapped[int] = mapped_column(Integer, default=2)
    score: Mapped[int] = mapped_column(Integer, default=0)
    time_join: Mapped[datetime] = mapped_column(TIMESTAMP, default=func.now())

    guess_the_players = relationship(
        "GuessThePlayer",
        secondary=guess_the_player_guess_the_player_player_association,
        primaryjoin="GuessThePlayerPlayer.id == guess_the_player_guess_the_player_player.c.guess_the_player_player_id",
        secondaryjoin="GuessThePlayer.chat_id == guess_the_player_guess_the_player_player.c.guess_the_player_id",
        back_populates="current_players",
        cascade="all"
    )

    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "guess_the_player_id",
            name="uq_player_draft"
        ),
    )

class DraftPlayer(Base):
    __tablename__ = "draft_player"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer)
    draft_id: Mapped[int] = mapped_column(Integer, ForeignKey('draft.chat_id', ondelete="CASCADE", use_alter=True))

    picked: Mapped[bool] = mapped_column(Boolean, default=False)
    picking: Mapped[bool] = mapped_column(Boolean, default=False)
    time_join: Mapped[datetime] = mapped_column(TIMESTAMP, default=func.now())

    team = relationship("DraftPlayerTeam", uselist=False, backref="player", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint(
            "player_id",
            "draft_id",
            name="uq_player_draft"
        ),
    )

class AskedQuestions(Base):
    __tablename__ = "asked_questions"
    id:Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question:Mapped[str] = mapped_column(String(40))
    answer:Mapped[str] = mapped_column(String(40))
    
    guess_the_player_id: Mapped[int] = mapped_column(Integer, ForeignKey("guess_the_player.chat_id", ondelete="CASCADE"))

class Team(Base):
    __tablename__ = "team"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    
    drafts = relationship("Draft", secondary=draft_team_association, back_populates="teams")

class DraftPlayerTeam(Base):
    __tablename__ = "draft_player_team"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey('draft_player.id', ondelete='CASCADE'))
    chat_id: Mapped[int] = mapped_column(Integer)

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

class DraftVote(Base):
    __tablename__ = "draft_vote"
    chat_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    questions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    num_players: Mapped[int] = mapped_column(Integer, nullable=False)
    answers: Mapped[int] = mapped_column(Integer, nullable=False)
    players = relationship("DraftVotePlayer", uselist=False, backref="vote", cascade="all, delete-orphan")

class DraftVotePlayer(Base):
    __tablename__ = "draft_vote_player"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    draft_vote: Mapped[int] = mapped_column(Integer, ForeignKey("draft_vote.chat_id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(Integer, nullable=False)
    option_id: Mapped[int] = mapped_column(Integer, nullable=False)
    votes: Mapped[int] = mapped_column(Integer, default=0)

    UniqueConstraint(
        draft_vote,
        player_id
    )

class RateLimits(Base):
    __tablename__ = "rate_limits"
    player_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    time_created: Mapped[datetime] = mapped_column(TIMESTAMP, default=func.now())

class UserRateLimitTrack(Base):
    __tablename__ = "user_rate_limit_track"
    player_id: Mapped[int] = mapped_column(Integer)
    time_created: Mapped[datetime] = mapped_column(TIMESTAMP, default=func.now())

    PrimaryKeyConstraint(
        player_id,
        time_created
    )


