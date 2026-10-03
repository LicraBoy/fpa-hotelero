"""Formato de Mazatlán de punta a punta con el libro sintético: importar, calcular, exportar."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.config import settings
from fpa.ingesta.contrato import Fuente, ResultadoLectura
from fpa.ingesta.contrato import Movimiento as MovimientoLeido
from fpa.ingesta.variance_lectura import leer_variance
from fpa.ingesta.variance_mzt import leer_hojas_mzt, leer_valores_mensuales_mzt
from fpa.modelos import CuentaLocal
from fpa.modelos.mapeo import MapeoLineaCuenta
from fpa.modelos.plan import LineaPlanMensual, ValorCapturado
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.budget import importar_budget_mensual
from fpa.servicios.cargar_archivo import Resolucion, cargar_archivo
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.estructura_reporte import importar_estructura_reporte
from fpa.servicios.mapeo import importar_mapeo
from fpa.servicios.reglas_suma import importar_reglas_suma
from fpa.servicios.variance import calcular_variance
from fpa.servicios.versionado_mapeo import aprobar
from tests.mzt_sintetico import crear_libro_mzt

D = Decimal
ANALISTA = "analista_a@test.local"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture(autouse=True)
def almacenamiento(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path / "storage"))
    return tmp_path / "storage"


def _mov(cuenta: str, debito: str, credito: str, dia: date) -> MovimientoLeido:
    return MovimientoLeido(
        cuenta_codigo=cuenta,
        cuenta_descripcion=cuenta,
        asiento="1.1.1",
        fecha=dia,
        concepto="x",
        debito=D(debito),
        credito=D(credito),
        fila=1,
    )


class Libro:
    """El libro sintético ya importado: estructura, reglas, mapeo aprobado y movimientos."""

    def __init__(self, db: Session, mundo: Mundo, ruta: Path, con_movimientos: bool = True) -> None:
        self.db, self.mundo, self.ruta = db, mundo, ruta
        self.kw = {"organizacion_id": mundo.org1, "hotel_id": mundo.hotel_a, "usuario_id": None}
        self.archivo = DatosArchivo(nombre="mzt.xlsx", sha256="a" * 64)
        for codigo in ("4002011", "4002001.010", "6009001.001", "6009001.002"):
            db.add(
                CuentaLocal(
                    hotel_id=mundo.hotel_a,
                    codigo=codigo,
                    descripcion=codigo,
                    clase=codigo[0],
                    con_movimientos=True,
                    origen="catalogo_oficial",
                )
            )
        if con_movimientos:
            lectura = ResultadoLectura(fuente=Fuente.VARIANCE_BASE_DATOS, controla_balance=False)
            lectura.movimientos = [
                _mov("4002011", "0", "100", date(2026, 7, 5)),
                _mov("6009001.001", "30", "0", date(2026, 7, 6)),
                _mov("6009001.002", "10", "0", date(2026, 7, 6)),
                _mov("4002011", "0", "120", date(2026, 8, 5)),
                _mov("6009001.001", "35", "0", date(2026, 8, 6)),
                _mov("6009001.002", "15", "0", date(2026, 8, 6)),
            ]
            res = cargar_archivo(
                db,
                organizacion_id=mundo.org1,
                hotel_id=mundo.hotel_a,
                usuario_id=None,
                resultado=lectura,
                archivo=DatosArchivo(nombre="m.xlsx", sha256="m" * 64),
            )
            assert res.resolucion is Resolucion.CREADA
        self.lectura = leer_variance(ruta)
        self.estructura = importar_estructura_reporte(
            db, resultado=self.lectura.estructura, archivo=self.archivo, **self.kw
        ).version
        assert self.estructura is not None
        importar_reglas_suma(db, version=self.estructura, leidas=self.lectura.reglas, **self.kw)
        self.mapeo = importar_mapeo(
            db,
            version_estructura=self.estructura,
            leido=self.lectura.mapeo,
            archivo=self.archivo,
            **self.kw,
        ).version
        assert self.mapeo is not None
        db.commit()

    def aprobar_y_cargar_budget(self) -> None:
        assert self.mapeo is not None and self.estructura is not None
        aprobar(self.db, version_id=self.mapeo.id, **self.kw)  # type: ignore[arg-type]
        resultado = importar_budget_mensual(
            self.db,
            version_estructura=self.estructura,
            por_periodo=leer_valores_mensuales_mzt(leer_hojas_mzt(self.ruta)).por_periodo,
            archivo=self.archivo,
            ano_fiscal="2026/27",
            filas_con_cuentas={v.fila_origen for v in self.lectura.mapeo.vinculos},
            **self.kw,
        )
        assert resultado.resolucion is Resolucion.CREADA, resultado.motivos
        self.db.commit()


@pytest.fixture
def libro(db: Session, mundo: Mundo, tmp_path: Path) -> Libro:
    return Libro(db, mundo, crear_libro_mzt(tmp_path / "mzt.xlsx"))


def test_el_codigo_pegado_sin_cero_final_se_resuelve_con_el_catalogo(libro: Libro) -> None:
    assert libro.mapeo is not None
    codigos = set(
        libro.db.scalars(
            select(MapeoLineaCuenta.cuenta_codigo).where(
                MapeoLineaCuenta.version_mapeo_id == libro.mapeo.id
            )
        )
    )
    assert "4002001.010" in codigos and "4002001.01" not in codigos


def test_budget_mensual_guarda_cada_mes_y_los_valores_capturados(libro: Libro) -> None:
    libro.aprobar_y_cargar_budget()
    por_fila = {
        x.fila_origen: x.id
        for x in RepositorioReporte(libro.db, libro.mundo.hotel_a).lineas(libro.estructura.id)
    }  # type: ignore[union-attr]
    mensuales = {
        (x.linea_id, x.periodo): x.importe for x in libro.db.scalars(select(LineaPlanMensual))
    }
    assert mensuales[(por_fila[11], "2026-07")] == D("90")
    assert mensuales[(por_fila[11], "2026-08")] == D("110")
    capturados = {
        (x.linea_id, x.periodo): (x.importe, x.origen)
        for x in libro.db.scalars(select(ValorCapturado))
    }
    assert capturados[(por_fila[9], "2026-08")] == (D("17.1337"), "excel")
    assert capturados[(por_fila[9], "2026-07")] == (D("17.2175"), "excel")
    assert (
        por_fila[11],
        "2026-08",
    ) not in capturados  # tiene cuentas: su Actual sale de los saldos


def test_variance_usa_el_budget_del_mes_y_suma_los_meses_del_acumulado(libro: Libro) -> None:
    libro.aprobar_y_cargar_budget()
    r = calcular_variance(libro.db, hotel_id=libro.mundo.hotel_a, periodo="2026-08")
    assert r.periodos_ytd == ["2026-07", "2026-08"]
    por = {x.descripcion: r.resultado[x.id] for x in r.lineas}
    renta = por["Rental Income"]
    assert (renta.mes.actual, renta.mes.budget, renta.mes.var) == (D("120"), D("110"), D("10"))
    assert (renta.ytd.actual, renta.ytd.budget) == (D("220"), D("200"))  # 90 + 110
    sueldos = por["Salaries"]
    assert (sueldos.mes.actual, sueldos.mes.budget) == (D("50"), D("48"))
    assert (sueldos.ytd.actual, sueldos.ytd.budget) == (D("90"), D("93"))
    assert por["Total Expenses"].ytd.budget == D("93")  # los totales también se suman por regla
    assert not any("Budget" in a and "falta" in a for a in r.advertencias)


def test_julio_tambien_se_calcula_con_su_propio_budget(libro: Libro) -> None:
    libro.aprobar_y_cargar_budget()
    r = calcular_variance(libro.db, hotel_id=libro.mundo.hotel_a, periodo="2026-07")
    renta = next(r.resultado[x.id] for x in r.lineas if x.descripcion == "Rental Income")
    assert (renta.mes.actual, renta.mes.budget) == (D("100"), D("90"))
    assert (renta.ytd.actual, renta.ytd.budget) == (D("100"), D("90"))


def test_tipo_de_cambio_es_capturado_var_es_budget_menos_actual_y_no_se_acumula(
    libro: Libro,
) -> None:
    libro.aprobar_y_cargar_budget()
    r = calcular_variance(libro.db, hotel_id=libro.mundo.hotel_a, periodo="2026-08")
    linea = next(x for x in r.lineas if x.fila_origen == 9)
    cambio = r.resultado[linea.id]
    assert (cambio.mes.actual, cambio.mes.budget) == (D("17.1337"), D("18"))
    assert cambio.mes.var == D("0.8663")
    assert cambio.mes.pct == D("0.8663") / D("18")
    # un tipo de cambio no se suma: su acumulado es el promedio de los meses capturados
    promedio = (D("17.2175") + D("17.1337")) / 2
    assert (cambio.ytd.actual, cambio.ytd.budget) == (promedio, D("18"))
    assert linea.id in r.capturadas


def renta_sin_budget(r) -> bool:  # type: ignore[no-untyped-def]
    renta = next(r.resultado[x.id] for x in r.lineas if x.descripcion == "Rental Income")
    return renta.mes.budget is None and renta.mes.var is None and renta.mes.pct is None


def test_un_mes_sin_budget_deja_el_acumulado_vacio_y_avisa(libro: Libro) -> None:
    libro.aprobar_y_cargar_budget()
    r = calcular_variance(libro.db, hotel_id=libro.mundo.hotel_a, periodo="2026-09")
    assert any("No hay Budget para 2026-09" in a for a in r.advertencias)
    assert any("Captúralo en la pestaña Budget" in a for a in r.advertencias)
    assert renta_sin_budget(r)
    renta = next(r.resultado[x.id] for x in r.lineas if x.descripcion == "Rental Income")
    assert renta.mes.budget is None and renta.ytd.budget is None


def test_api_importa_el_libro_de_mazatlan_y_calcula(
    cliente: TestClient, mundo: Mundo, tmp_path: Path
) -> None:
    contenido = crear_libro_mzt(tmp_path / "api.xlsx").read_bytes()
    base = f"/api/v1/hoteles/{mundo.hotel_a}"
    r = cliente.post(
        f"{base}/reporte/importar",
        files={"archivo": ("mzt.xlsx", contenido, XLSX)},
        headers=como(ANALISTA),
    )
    assert r.status_code == 201, r.text
    assert r.json()["formato"] == "mzt" and r.json()["n_reglas_suma"] == 3
    # el periodo de corte no es obligatorio: el archivo trae sus meses
    b = cliente.post(
        f"{base}/budget/importar",
        files={"archivo": ("mzt.xlsx", contenido, XLSX)},
        headers=como(ANALISTA),
    )
    assert b.status_code == 201, b.text
    version = b.json()["version"]
    assert b.json()["formato"] == "mzt"
    assert (version["ano_fiscal"], version["periodo_corte"]) == ("2026/27", "2026-08")


def test_api_exige_el_periodo_de_corte_en_el_formato_de_vallarta(
    cliente: TestClient, mundo: Mundo
) -> None:
    from test_budget import importar_reporte, libro_con_budget

    importar_reporte(cliente, mundo)
    r = cliente.post(
        f"/api/v1/hoteles/{mundo.hotel_a}/budget/importar",
        files={"archivo": ("v.xlsx", libro_con_budget(), XLSX)},
        headers=como(ANALISTA),
    )
    assert r.status_code == 422
