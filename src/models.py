from datetime import datetime, timezone

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Type(Base):
    __tablename__ = "types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    products: Mapped[list["Product"]] = relationship(back_populates="type")


class SubType(Base):
    __tablename__ = "subtypes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    products: Mapped[list["Product"]] = relationship(back_populates="subtype")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=True)
    price: Mapped[float] = mapped_column(nullable=True)
    type_id: Mapped[int] = mapped_column(ForeignKey("types.id"), nullable=True)
    type: Mapped["Type"] = relationship(back_populates="products")
    subtype_id: Mapped[int] = mapped_column(ForeignKey("subtypes.id"))
    subtype: Mapped["SubType"] = relationship(back_populates="products")
    count: Mapped[int] = mapped_column(default=1)
    exist: Mapped[float] = mapped_column(default=0)
    image: Mapped[str] = mapped_column(nullable=True)
    link: Mapped[str] = mapped_column(nullable=True)
    ccals: Mapped[float] = mapped_column(nullable=True)
    prots: Mapped[float] = mapped_column(nullable=True)
    fats: Mapped[float] = mapped_column(nullable=True)
    carbs: Mapped[float] = mapped_column(nullable=True)
    rate: Mapped[float] = mapped_column(nullable=True)
    weight: Mapped[float] = mapped_column(nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
