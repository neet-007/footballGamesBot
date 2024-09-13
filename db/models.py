from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase
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

