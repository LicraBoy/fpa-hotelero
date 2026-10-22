"""Pruebas de observabilidad (Fase 6.5): request_id de correlación, métricas y alertas."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from fpa.observabilidad.alertas import alertar
from fpa.observabilidad.peticion import CABECERA_ID
from fpa.observabilidad.registro import FormateadorJSON, fijar_id_de_peticion, id_de_peticion_actual


def test_cada_peticion_trae_un_request_id(cliente: TestClient) -> None:
    respuesta = cliente.get("/api/health")
    assert CABECERA_ID in respuesta.headers
    assert len(respuesta.headers[CABECERA_ID]) > 0


def test_request_id_se_respeta_si_el_cliente_lo_manda(cliente: TestClient) -> None:
    respuesta = cliente.get("/api/health", headers={CABECERA_ID: "pedido-por-el-cliente"})
    assert respuesta.headers[CABECERA_ID] == "pedido-por-el-cliente"


def test_metrics_responde_formato_prometheus(cliente: TestClient) -> None:
    cliente.get("/api/health")  # genera al menos una métrica
    respuesta = cliente.get("/api/metrics")
    assert respuesta.status_code == 200
    assert "fpa_peticiones_total" in respuesta.text


def test_formateador_json_incluye_request_id_cuando_hay_uno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fijar_id_de_peticion("abc123")
    try:
        registro = logging.LogRecord(
            name="prueba", level=logging.INFO, pathname="", lineno=0,
            msg="hola", args=(), exc_info=None,
        )
        import json

        salida = json.loads(FormateadorJSON().format(registro))
        assert salida["request_id"] == "abc123"
        assert salida["mensaje"] == "hola"
    finally:
        fijar_id_de_peticion(None)
    assert id_de_peticion_actual() is None


def test_alertar_no_truena_sin_webhook_configurado(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("FPA_ALERTA_WEBHOOK", raising=False)
    with caplog.at_level(logging.CRITICAL):
        alertar("algo se cayó")
    assert "algo se cayó" in caplog.text


def test_alertar_no_truena_si_el_webhook_falla(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("FPA_ALERTA_WEBHOOK", "http://localhost:0/no-existe")
    with caplog.at_level(logging.CRITICAL):
        alertar("algo se cayó")  # no debe lanzar, aunque el webhook no responda
    assert "algo se cayó" in caplog.text
