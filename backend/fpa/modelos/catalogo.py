"""Catálogo de cuentas locales (las de Novohit), por hotel.

Se alimenta de los reportes y se **acumula** entre cargas: el CON130 de un mes solo lista las
cuentas con movimiento de ese mes (108 de las 296 del Variance aparecen en septiembre), así que
el catálogo completo se va formando con cada archivo.

Un mismo código puede ser a la vez una cuenta con movimientos y un título de grupo: `4002007`
tiene movimientos en julio–agosto (Variance) y aparece como título en el CON130 de septiembre.
Por eso `con_movimientos` y `es_titulo` son independientes.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from fpa.modelos.base import Base, ahora_utc


class CuentaLocal(Base):
    __tablename__ = "cuenta_local"
    __table_args__ = (UniqueConstraint("hotel_id", "codigo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), index=True)
    codigo: Mapped[str] = mapped_column(String(40))
    descripcion: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Clase contable = primer carácter del código (1 activo, 2 pasivo, 4 ingresos... por validar)
    clase: Mapped[str] = mapped_column(String(1))
    # Profundidad en el árbol (0 = raíz); None si la cuenta aún no tiene jerarquía conocida
    nivel: Mapped[int | None] = mapped_column(Integer, nullable=True)
    padre_codigo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Ha tenido movimientos en alguna carga (cuenta "posteable")
    con_movimientos: Mapped[bool] = mapped_column(Boolean)
    # Apareció como título de la jerarquía en un CON130
    es_titulo: Mapped[bool] = mapped_column(Boolean, default=False)
    # Cuenta con movimientos para la que ningún CON130 ha dado aún su jerarquía
    sin_jerarquia: Mapped[bool] = mapped_column(Boolean, default=False)
    origen: Mapped[str] = mapped_column(String(40))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=ahora_utc)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=ahora_utc, onupdate=ahora_utc
    )
