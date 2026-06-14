from __future__ import annotations

from sqlalchemy import String, Integer, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ----- Base --------------------
class Base(DeclarativeBase):
    pass


# ----- Tables --------------------
class Subject(Base):
    """
    Stores subject code and name of each UVic subject.
    """
    __tablename__ = "subjects"

    code : Mapped[str]  = mapped_column(String,  primary_key=True)
    name : Mapped[str]  = mapped_column(String,  nullable=False)


class Course(Base):
    """
    Stores the course code, subject, level, name, credits, and prereqs of each UVic course.
    """
    __tablename__ = "courses"

    code            : Mapped[str]           = mapped_column(String,  primary_key=True)
    subject         : Mapped[str]           = mapped_column(String,  nullable=False)
    lvl             : Mapped[int]           = mapped_column(Integer, nullable=False)
    name            : Mapped[str]           = mapped_column(String,  nullable=False)
    credits         : Mapped[float]         = mapped_column(Numeric, nullable=False)
    prereqs         : Mapped[dict | None]   = mapped_column(JSONB,   nullable=True)
    coreqs          : Mapped[dict | None]   = mapped_column(JSONB,   nullable=True)