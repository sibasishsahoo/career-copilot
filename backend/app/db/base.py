"""The parent class of every ORM model.

`Base.metadata` collects every table that inherits from Base, so one call
(`Base.metadata.create_all`) can create all of them.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
