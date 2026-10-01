import io
import json
import statistics
import time

from conftest import Mundo, como
from fastapi.testclient import TestClient
from openpyxl import Workbook
from real_agosto import AgostoReal, agosto_real  # noqa: F401
from sqlalchemy.orm import Session
from test_api_variance import _pedir, _preparar

from fpa.db import get_db
from fpa.identidad.dependencias import obtener_proveedor
from fpa.identidad.proveedor import ProveedorDesarrollo
from fpa.main import app
from fpa.servicios.cache_reportes import CacheReportes
from fpa.servicios.reportes import cache_variance

ANALISTA = "analista_a@test.local"
CONTRALOR = "contralor_ab@test.local"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class Reloj:
    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora


def _clave(cache: CacheReportes[str], org: int = 1, hotel: int = 1, periodo: str = "2026-08"):  # type: ignore[no-untyped-def]
    return cache.clave(
        organizacion_id=org,
        hotel_id=hotel,
        version_mapeo_id=None,
        version_plan_id=None,
        periodo=periodo,
    )


# --- La caché sola ----------------------------------------------------------------------------


def test_guardar_y_obtener() -> None:
    c: CacheReportes[str] = CacheReportes()
    k = _clave(c)
    assert c.obtener(k) is None
    c.guardar(k, "reporte")
    assert c.obtener(k) == "reporte"
    assert (c.aciertos, c.fallos) == (1, 1)


def test_vence_por_tiempo() -> None:
    reloj = Reloj()
    c: CacheReportes[str] = CacheReportes(ttl_segundos=60, reloj=reloj)
    k = _clave(c)
    c.guardar(k, "x")
    reloj.ahora += 59
    assert c.obtener(k) == "x"
    reloj.ahora += 2
    assert c.obtener(k) is None and len(c) == 0


def test_se_desaloja_lo_menos_usado() -> None:
    c: CacheReportes[str] = CacheReportes(max_entradas=2)
    a, b, d = (_clave(c, periodo=p) for p in ("2026-07", "2026-08", "2026-09"))
    c.guardar(a, "a")
    c.guardar(b, "b")
    assert c.obtener(a) == "a"  # a se usa: b queda como el menos reciente
    c.guardar(d, "d")
    assert c.obtener(b) is None and c.obtener(a) == "a" and c.obtener(d) == "d"


def test_invalidar_un_hotel_no_toca_a_los_demas() -> None:
    c: CacheReportes[str] = CacheReportes()
    uno, dos = _clave(c, hotel=1), _clave(c, hotel=2)
    c.guardar(uno, "uno")
    c.guardar(dos, "dos")
    c.invalidar_hotel(1)
    assert c.obtener(_clave(c, hotel=1)) is None  # la clave nueva ya es otra
    assert c.obtener(_clave(c, hotel=2)) == "dos"


def test_organizaciones_y_hoteles_nunca_comparten_entradas() -> None:
    c: CacheReportes[str] = CacheReportes()
    c.guardar(_clave(c, org=1, hotel=1), "de la org 1")
    assert c.obtener(_clave(c, org=2, hotel=1)) is None  # mismo hotel_id, otra organización
    assert c.obtener(_clave(c, org=1, hotel=2)) is None
    assert c.obtener(_clave(c, org=1, hotel=1)) == "de la org 1"


def test_apagada_con_ttl_cero() -> None:
    c: CacheReportes[str] = CacheReportes(ttl_segundos=0)
    k = _clave(c)
    c.guardar(k, "x")
    assert c.obtener(k) is None and not c.activa


def test_dos_cachés_tienen_epoca_distinta() -> None:
    # tras reiniciar el servidor, una clave vieja no puede coincidir con una nueva
    a: CacheReportes[str] = CacheReportes()
    b: CacheReportes[str] = CacheReportes()
    assert _clave(a)[-1] != _clave(b)[-1]


# --- Por la API: aciertos, resultados iguales e invalidación -----------------------------------


def _x_cache(r) -> str:  # type: ignore[no-untyped-def]
    return r.headers["x-cache"]


def test_la_segunda_peticion_sale_de_la_cache_con_el_mismo_resultado(
    cliente: TestClient, mundo: Mundo, db: Session
) -> None:
    _preparar(db, mundo)
    primera = _pedir(cliente, mundo)
    segunda = _pedir(cliente, mundo)
    assert (_x_cache(primera), _x_cache(segunda)) == ("miss", "hit")
    assert primera.content == segunda.content  # idéntico, byte por byte
    assert primera.headers["content-type"] == "application/json"
    assert primera.headers["cache-control"] == "no-store"  # el navegador nunca la guarda


def test_los_filtros_salen_de_la_misma_entrada(
    cliente: TestClient, mundo: Mundo, db: Session
) -> None:
    _preparar(db, mundo)
    base = f"/api/v1/hoteles/{mundo.hotel_a}/variance?periodo=2026-08"
    h = como(ANALISTA)
    assert _x_cache(cliente.get(base, headers=h)) == "miss"
    filtrado = cliente.get(f"{base}&tipo=total", headers=h)
    assert _x_cache(filtrado) == "hit"
    assert [x["descripcion"] for x in filtrado.json()["lineas"]] == ["Total"]
    # y el reporte completo no se contaminó con el filtro
    assert len(cliente.get(base, headers=h).json()["lineas"]) == 3


def test_con_y_sin_cache_el_resultado_es_el_mismo(
    cliente: TestClient, mundo: Mundo, db: Session
) -> None:
    _preparar(db, mundo)
    con = _pedir(cliente, mundo).content
    cache_variance.limpiar()
    sin = _pedir(cliente, mundo)
    assert _x_cache(sin) == "miss" and sin.content == con


def test_cargar_un_archivo_invalida(cliente: TestClient, mundo: Mundo, db: Session) -> None:
    _preparar(db, mundo)
    antes = _pedir(cliente, mundo)
    assert _x_cache(_pedir(cliente, mundo)) == "hit"
    # el mismo mes con otros importes: al confirmar el reemplazo cambia el reporte
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Base de Datos"
    ws.append([])
    ws.append([None, "Mes", "Fecha", "No Cuenta", "Nombre de la Cuenta", "Asiento - Salida",
               "Concepto - Nombre Articulo", "Cantidad", "Costo", "Débito", "Crédito"])  # fmt: skip
    import datetime as dt

    ws.append(
        [
            None,
            "Agosto",
            dt.datetime(2026, 8, 5),
            "6009001.001",
            "S",
            "8.1.1",
            "x",
            None,
            None,
            999.0,
            None,
        ]
    )
    ws.append(
        [
            None,
            "Agosto",
            dt.datetime(2026, 8, 6),
            "4001002.001",
            "I",
            "8.1.2",
            "x",
            None,
            None,
            None,
            5.0,
        ]
    )
    buf = io.BytesIO()
    wb.save(buf)
    r = cliente.post(
        f"/api/v1/hoteles/{mundo.hotel_a}/cargas",
        files={"archivo": ("nuevo.xlsx", buf.getvalue(), XLSX)},
        data={"fuente": "variance_base_datos", "confirmar_reemplazo": "true"},
        headers=como(ANALISTA),
    )
    assert r.status_code == 201, r.text
    despues = _pedir(cliente, mundo)
    assert _x_cache(despues) == "miss"  # la escritura invalidó
    assert despues.content != antes.content  # y el reporte refleja lo nuevo
    gasto = next(x for x in despues.json()["lineas"] if x["descripcion"] == "Gasto")
    assert gasto["mes"]["actual"] == "999.00"
    assert _x_cache(_pedir(cliente, mundo)) == "hit"


def test_editar_o_aprobar_el_mapeo_invalida(cliente: TestClient, mundo: Mundo, db: Session) -> None:
    _preparar(db, mundo)
    base = f"/api/v1/hoteles/{mundo.hotel_a}"
    _pedir(cliente, mundo)
    assert _x_cache(_pedir(cliente, mundo)) == "hit"
    # un borrador nuevo (copia del aprobado) es una escritura: invalida
    r = cliente.post(f"{base}/mapeo/versiones", headers=como(ANALISTA))
    assert r.status_code == 201
    borrador = r.json()["id"]
    assert _x_cache(_pedir(cliente, mundo)) == "miss"
    assert _x_cache(_pedir(cliente, mundo)) == "hit"
    # editar el borrador invalida
    r = cliente.put(
        f"{base}/mapeo/versiones/{borrador}/exclusiones",
        json={"cuenta_codigo": "9999999", "motivo": "prueba"},
        headers=como(ANALISTA),
    )
    assert r.status_code == 200
    assert _x_cache(_pedir(cliente, mundo)) == "miss"
    # aprobar invalida: el reporte ahora usa la versión nueva
    _pedir(cliente, mundo)
    r = cliente.post(f"{base}/mapeo/versiones/{borrador}/aprobar", headers=como(CONTRALOR))
    assert r.status_code == 200, r.text
    despues = _pedir(cliente, mundo)
    assert _x_cache(despues) == "miss" and despues.json()["version_mapeo_id"] == borrador


def test_importar_un_budget_invalida(cliente: TestClient, mundo: Mundo, db: Session) -> None:
    _preparar(db, mundo)
    _pedir(cliente, mundo)
    assert _x_cache(_pedir(cliente, mundo)) == "hit"
    # importar el Budget otra vez (aunque sea el mismo archivo) es una escritura del hotel
    from test_budget import libro_con_budget

    r = cliente.post(
        f"/api/v1/hoteles/{mundo.hotel_a}/budget/importar",
        files={"archivo": ("v.xlsx", libro_con_budget(), XLSX)},
        data={"periodo_corte": "2026-08", "confirmar_reemplazo": "true"},
        headers=como(ANALISTA),
    )
    assert r.status_code < 300, r.text
    assert _x_cache(_pedir(cliente, mundo)) == "miss"


def test_una_escritura_rechazada_no_invalida(
    cliente: TestClient, mundo: Mundo, db: Session
) -> None:
    _preparar(db, mundo)
    _pedir(cliente, mundo)
    base = f"/api/v1/hoteles/{mundo.hotel_a}"
    # sin permiso (403) y con datos inválidos (422): no cambian nada
    r = cliente.post(f"{base}/mapeo/versiones", headers=como("responsable_a@test.local"))
    assert r.status_code == 403
    r = cliente.put(
        f"{base}/mapeo/versiones/1/vinculos",
        json={"linea_id": 0, "cuenta_codigo": "", "signo": 9},
        headers=como(ANALISTA),
    )
    assert r.status_code == 422
    assert _x_cache(_pedir(cliente, mundo)) == "hit"


def test_las_lecturas_y_las_exportaciones_no_invalidan(
    cliente: TestClient, mundo: Mundo, db: Session
) -> None:
    _preparar(db, mundo)
    _pedir(cliente, mundo)
    base = f"/api/v1/hoteles/{mundo.hotel_a}"
    cliente.get(f"{base}/mapeo/versiones", headers=como(ANALISTA))
    cliente.get(f"{base}/variance/exportar?periodo=2026-08", headers=como(ANALISTA))
    assert _x_cache(_pedir(cliente, mundo)) == "hit"


def test_un_error_no_se_guarda_en_la_cache(cliente: TestClient, mundo: Mundo) -> None:
    # sin mapeo aprobado: 404 las dos veces, y nada queda guardado
    assert _pedir(cliente, mundo).status_code == 404
    assert len(cache_variance) == 0
    assert _pedir(cliente, mundo).status_code == 404


def test_otro_usuario_del_mismo_hotel_comparte_la_entrada_pero_pasa_por_la_autorizacion(
    cliente: TestClient, mundo: Mundo, db: Session
) -> None:
    _preparar(db, mundo)
    assert _x_cache(_pedir(cliente, mundo, usuario=ANALISTA)) == "miss"
    assert _x_cache(_pedir(cliente, mundo, usuario=CONTRALOR)) == "hit"
    # la caché no salta el permiso: sin permiso, 403 aunque la entrada exista
    assert _pedir(cliente, mundo, usuario="responsable_a@test.local").status_code == 403
    assert _pedir(cliente, mundo, usuario="contralor_c@test.local").status_code == 404


# --- Rendimiento con agosto real (objetivos de la sección 4.5 de la arquitectura) ---------------


def _p95(ms: list[float]) -> float:
    ordenados = sorted(ms)
    return ordenados[min(len(ordenados) - 1, int(len(ordenados) * 0.95))]


def test_agosto_real_cumple_los_objetivos_de_rendimiento(agosto_real: AgostoReal) -> None:  # noqa: F811
    """Variance mensual (~500 líneas): p95 < 2 s sin caché y p95 < 500 ms con caché."""
    a = agosto_real

    def sesion():  # type: ignore[no-untyped-def]
        with a.sesiones() as s:
            yield s

    # el mapeo del fixture es un borrador: se pide por versión explícita
    app.dependency_overrides[get_db] = sesion
    app.dependency_overrides[obtener_proveedor] = ProveedorDesarrollo
    try:
        cliente = TestClient(app)
        url = (
            f"/api/v1/hoteles/{a.hotel_id}/variance?periodo=2026-08"
            f"&version_mapeo_id={a.version_mapeo_id}&version_plan_id={a.version_plan_id}"
        )
        h = como(a.email_analista)

        sin_cache: list[float] = []
        for _ in range(15):
            cache_variance.limpiar()
            t = time.perf_counter()
            r = cliente.get(url, headers=h)
            sin_cache.append((time.perf_counter() - t) * 1000)
            assert r.status_code == 200 and r.headers["x-cache"] == "miss"
        cuerpo = r.json()
        assert len(cuerpo["lineas"]) > 450

        con_cache: list[float] = []
        for _ in range(100):
            t = time.perf_counter()
            r = cliente.get(url, headers=h)
            con_cache.append((time.perf_counter() - t) * 1000)
            assert r.headers["x-cache"] == "hit"
        assert r.json() == cuerpo  # con y sin caché, lo mismo

        resumen = {
            "sin_cache_p95_ms": round(_p95(sin_cache)),
            "sin_cache_mediana_ms": round(statistics.median(sin_cache)),
            "con_cache_p95_ms": round(_p95(con_cache)),
            "con_cache_mediana_ms": round(statistics.median(con_cache)),
        }
        print(json.dumps(resumen))
        assert _p95(sin_cache) < 2000, resumen
        assert _p95(con_cache) < 500, resumen
        # la caché sirve: un acierto cuesta bastante menos que calcular
        assert statistics.median(con_cache) < statistics.median(sin_cache), resumen
    finally:
        app.dependency_overrides.clear()


def test_la_conversacion_de_un_mes_sin_datos_no_rompe_la_cache(
    cliente: TestClient, mundo: Mundo, db: Session
) -> None:
    _preparar(db, mundo)
    r = _pedir(cliente, mundo, periodo="2026-09")
    assert r.status_code == 200 and _x_cache(r) == "miss"
    assert _x_cache(_pedir(cliente, mundo, periodo="2026-09")) == "hit"
    assert _x_cache(_pedir(cliente, mundo)) == "miss"  # otro periodo = otra clave
