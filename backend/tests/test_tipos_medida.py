from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy.dialects import postgresql, sqlite

from fpa.modelos.tipos import Medida


@pytest.mark.parametrize("texto", ["0", "2.5", "10.333333", "0.000001", "12345678901234.123456"])
def test_ida_y_vuelta_exacta(texto: str) -> None:
    tipo = Medida()
    guardado = tipo.process_bind_param(Decimal(texto), sqlite.dialect())
    assert isinstance(guardado, str)
    assert tipo.process_result_value(guardado, sqlite.dialect()) == Decimal(texto)


def test_rechaza_float_y_mas_de_seis_decimales() -> None:
    tipo = Medida()
    with pytest.raises(TypeError, match="nunca float"):
        tipo.process_bind_param(2.5, sqlite.dialect())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="más de 6 decimales"):
        tipo.process_bind_param(Decimal("1.1234567"), sqlite.dialect())


def test_en_postgresql_se_entrega_decimal() -> None:
    valor = Medida().process_bind_param(Decimal("2.5"), postgresql.dialect())
    assert isinstance(valor, Decimal) and valor == Decimal("2.5")


@given(
    st.decimals(min_value=Decimal("-99999999999999"), max_value=Decimal("99999999999999"), places=6)
)
def test_propiedad_ida_y_vuelta(valor: Decimal) -> None:
    tipo = Medida()
    guardado = tipo.process_bind_param(valor, sqlite.dialect())
    assert tipo.process_result_value(guardado, sqlite.dialect()) == valor
