"""Contrato de la API: el OpenAPI describe lo que la API hace (Schemathesis, solo desarrollo).

Se recorren todas las rutas de **lectura** (GET) con entradas generadas, con identidad de
desarrollo y una base sembrada: nunca debe haber un 5xx, y los códigos de estado y los cuerpos
tienen que coincidir con lo documentado. Las rutas que escriben o suben archivos se prueban
una por una en sus propios módulos.
"""

import pytest
import schemathesis
from conftest import Mundo, como
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, settings
from schemathesis.specs.openapi.checks import (
    allow_header_conformance,
    positive_data_acceptance,
    unsupported_method,
)
from sqlalchemy.orm import Session
from test_api_variance import _preparar

from fpa.main import app

schema = schemathesis.openapi.from_asgi("/openapi.json", app)


@pytest.fixture
def sembrado(cliente: TestClient, mundo: Mundo, db: Session) -> Mundo:
    _preparar(db, mundo)
    return mundo


def test_el_openapi_se_publica_y_documenta_los_errores(cliente: TestClient) -> None:
    r = cliente.get("/openapi.json")
    assert r.status_code == 200
    ruta = r.json()["paths"]["/api/v1/hoteles/{hotel_id}/variance"]["get"]
    assert {"200", "401", "403", "404", "409", "422"} <= set(ruta["responses"])


@schema.include(method="GET").parametrize()
@settings(
    max_examples=8,
    deadline=None,
    suppress_health_check=list(HealthCheck),
)
def test_las_rutas_de_lectura_cumplen_su_contrato(case, sembrado: Mundo) -> None:  # type: ignore[no-untyped-def]
    valor = (case.path_parameters or {}).get("hotel_id")
    if isinstance(valor, int):
        # la mitad de las veces el hotel real, para llegar más allá del 404
        case.path_parameters["hotel_id"] = sembrado.hotel_a if valor % 2 == 0 else sembrado.hotel_b
    # Se excluyen las comprobaciones de `Allow` en un 405: Starlette lista un solo método cuando
    # la ruta tiene varios (GET y POST son rutas separadas); no es un defecto nuestro.
    excluidas = [unsupported_method, allow_header_conformance]
    if case.operation.path.endswith("/movimientos"):
        # El cursor es opaco: cualquier texto cumple el esquema, pero solo los que entregó la API
        # sirven. Rechazar el resto con 422 es justo lo que se quiere.
        excluidas.append(positive_data_acceptance)
    case.call_and_validate(headers=como("contralor_ab@test.local"), excluded_checks=excluidas)
