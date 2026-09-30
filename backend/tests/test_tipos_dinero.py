from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy import Engine, create_engine
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from fpa.modelos.tipos import Dinero


class _Base(DeclarativeBase):
    pass


class _Prueba(_Base):
    __tablename__ = "prueba_dinero"
    id: Mapped[int] = mapped_column(primary_key=True)
    monto: Mapped[Decimal | None] = mapped_column(Dinero, nullable=True)


def _engine() -> Engine:
    eng = create_engine("sqlite://")
    _Base.metadata.create_all(eng)
    return eng


@pytest.mark.parametrize(
    "texto",
    ["0.00", "0.10", "0.01", "57835193.08", "-2328039.98", "16037192.06", "9999999999999999.99"],
)
def test_ida_y_vuelta_exacta_en_sqlite(texto: str) -> None:
    eng = _engine()
    valor = Decimal(texto)
    with Session(eng) as s:
        s.add(_Prueba(id=1, monto=valor))
        s.commit()
    with Session(eng) as s:
        leido = s.get(_Prueba, 1)
        assert leido is not None
        assert leido.monto == valor
        assert isinstance(leido.monto, Decimal)


def test_none_se_conserva() -> None:
    eng = _engine()
    with Session(eng) as s:
        s.add(_Prueba(id=1, monto=None))
        s.commit()
        assert s.get(_Prueba, 1).monto is None  # type: ignore[union-attr]


def test_rechaza_float() -> None:
    eng = _engine()
    with Session(eng) as s:
        s.add(_Prueba(id=1, monto=0.1))  # type: ignore[arg-type]
        with pytest.raises(Exception, match="nunca float"):
            s.commit()


def test_rechaza_mas_de_dos_decimales() -> None:
    eng = _engine()
    with Session(eng) as s:
        s.add(_Prueba(id=1, monto=Decimal("1.234")))
        with pytest.raises(Exception, match="más de 2 decimales"):
            s.commit()


def test_en_sqlite_se_guarda_como_texto_exacto() -> None:
    tipo = Dinero()
    assert tipo.process_bind_param(Decimal("10.50"), sqlite.dialect()) == "10.50"


def test_en_postgresql_se_entrega_decimal() -> None:
    tipo = Dinero()
    valor = tipo.process_bind_param(Decimal("10.50"), postgresql.dialect())
    assert isinstance(valor, Decimal)
    assert valor == Decimal("10.50")


@given(
    st.decimals(
        min_value=Decimal("-9999999999999.99"), max_value=Decimal("9999999999999.99"), places=2
    )
)
def test_propiedad_ida_y_vuelta(valor: Decimal) -> None:
    tipo = Dinero()
    guardado = tipo.process_bind_param(valor, sqlite.dialect())
    assert tipo.process_result_value(guardado, sqlite.dialect()) == valor
