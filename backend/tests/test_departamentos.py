"""Vista «Por departamento»: importes del Variance agrupados por el departamento de la cuenta."""

from decimal import Decimal

import pytest
from conftest import Mundo, como
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_acceso_usuarios import _asignar
from test_versionado_mapeo import Escenario

from fpa.modelos import CuentaLocal
from fpa.servicios.departamentos import DatosCuenta, agrupar, tipo_de_grupo
from fpa.servicios.versionado_mapeo import aprobar, crear_borrador_desde, quitar_vinculo

D = Decimal
ANALISTA = "analista_a@test.local"
CONTRALOR = "contralor_ab@test.local"
RESPONSABLE = "responsable_a@test.local"
OTRA_ORG = "contralor_c@test.local"


def _url(mundo: Mundo, periodo: str = "2026-08") -> str:
    return f"/api/v1/hoteles/{mundo.hotel_a}/variance/departamentos?periodo={periodo}"


def _catalogo(db: Session, mundo: Mundo, cambios: dict[str, tuple[str | None, str | None]]) -> None:
    for codigo, (depto, grupo) in cambios.items():
        cuenta = db.scalars(
            select(CuentaLocal).where(
                CuentaLocal.hotel_id == mundo.hotel_a, CuentaLocal.codigo == codigo
            )
        ).one()
        cuenta.depto_ef, cuenta.grupo_ef = depto, grupo
    db.commit()


@pytest.fixture
def con_deptos(esc: Escenario, db: Session, mundo: Mundo) -> Escenario:
    _catalogo(
        db,
        mundo,
        {
            "4001002.001": ("ROOMS", "INCOME"),
            "6009001.001": ("HOUSEKEEPING", "PAYROLL EXPENS"),
        },
    )
    return esc


# --- Función pura -------------------------------------------------------------------------------


def test_tipos_de_grupo() -> None:
    assert tipo_de_grupo("INCOME") == "ingreso"
    assert tipo_de_grupo(" payroll expens ") == "nomina"
    assert tipo_de_grupo("OPS EXPENSES") == "operacion"
    assert tipo_de_grupo("COST OF GOODS") == "costo"
    assert tipo_de_grupo("OTHER EXPENSES") == "otros"
    assert tipo_de_grupo("ALGO NUEVO") == "otros"
    assert tipo_de_grupo(None) == "sin_tipo" and tipo_de_grupo("  ") == "sin_tipo"


def test_agrupar_suma_mes_y_acumulado_con_el_signo_del_vinculo() -> None:
    catalogo = {
        "A": DatosCuenta("Sueldos", "HOUSEKEEPING", "PAYROLL EXPENS"),
        "B": DatosCuenta("Insumos", "HOUSEKEEPING", "OPS EXPENSES"),
        "C": DatosCuenta("Cuarto", "ROOMS", "INCOME"),
        "D": DatosCuenta("Sin datos", None, None),
    }
    netos = {
        "2026-07": {"A": D("10"), "C": D("-100")},
        "2026-08": {"A": D("20"), "B": D("5"), "C": D("-200"), "D": D("7")},
    }
    filas = agrupar(
        [(1, "A", 1), (2, "B", 1), (3, "C", -1), (4, "D", 1)],
        netos,
        periodo="2026-08",
        meses=["2026-07", "2026-08"],
        catalogo=catalogo,
    )
    por = {f.departamento: f for f in filas}
    hk = por["HOUSEKEEPING"]
    assert (hk.por_tipo["nomina"].mes, hk.por_tipo["nomina"].ytd) == (D("20"), D("30"))
    assert (hk.gasto.mes, hk.gasto.ytd) == (D("25"), D("35"))
    assert (por["ROOMS"].ingreso.mes, por["ROOMS"].ingreso.ytd) == (D("200"), D("300"))
    assert por[None].por_tipo["sin_tipo"].mes == D("7")
    assert filas[-1].departamento is None  # «Sin departamento» va al final


def test_una_cuenta_vinculada_a_dos_lineas_cuenta_una_vez_por_vinculo() -> None:
    filas = agrupar(
        [(1, "A", 1), (2, "A", 1)],
        {"2026-08": {"A": D("10")}},
        periodo="2026-08",
        meses=["2026-08"],
        catalogo={"A": DatosCuenta("x", "BAR", "OPS EXPENSES")},
    )
    assert filas[0].gasto.mes == D("20") and filas[0].cuentas["A"].n_lineas == 2


def test_un_signo_invalido_se_rechaza() -> None:
    with pytest.raises(ValueError):
        agrupar([(1, "A", 2)], {}, periodo="2026-08", meses=["2026-08"], catalogo={})


# --- API ----------------------------------------------------------------------------------------


def test_por_departamento_agrupa_y_cuadra_con_el_variance(
    cliente: TestClient, mundo: Mundo, con_deptos: Escenario
) -> None:
    r = cliente.get(_url(mundo), headers=como(ANALISTA))
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    por = {x["departamento"]: x for x in cuerpo["departamentos"]}
    assert set(por) == {"ROOMS", "HOUSEKEEPING"}
    assert por["ROOMS"]["ingreso"]["mes"] == "100.00"
    assert por["HOUSEKEEPING"]["por_tipo"]["nomina"] == {"mes": "30.00", "ytd": "30.00"}
    assert por["HOUSEKEEPING"]["resultado"]["mes"] == "-30.00"
    assert cuerpo["total"]["resultado"]["mes"] == "70.00"
    assert cuerpo["cuentas_vinculadas"] == 2 and cuerpo["cuentas_sin_departamento"] == 0
    # cuadre: lo que suman los departamentos es el Actual de las líneas de detalle del Variance
    v = cliente.get(
        f"/api/v1/hoteles/{mundo.hotel_a}/variance?periodo=2026-08", headers=como(ANALISTA)
    )
    detalle = {x["descripcion"]: D(x["mes"]["actual"]) for x in v.json()["lineas"]}
    assert D(por["ROOMS"]["ingreso"]["mes"]) == detalle["Ingreso"]
    assert D(por["HOUSEKEEPING"]["gasto"]["mes"]) == detalle["Gasto"]
    assert cuerpo["periodos_sin_datos"] == ["2026-07"]


def test_las_cuentas_sin_departamento_se_reportan_aparte(
    cliente: TestClient, mundo: Mundo, esc: Escenario, db: Session
) -> None:
    _catalogo(db, mundo, {"4001002.001": ("ROOMS", "INCOME")})  # el gasto queda sin datos
    cuerpo = cliente.get(_url(mundo), headers=como(ANALISTA)).json()
    assert cuerpo["cuentas_sin_departamento"] == 1 and cuerpo["cuentas_sin_tipo"] == 1
    sin = cuerpo["departamentos"][-1]
    assert sin["departamento"] is None and sin["por_tipo"]["sin_tipo"]["mes"] == "30.00"
    # lo que no tiene tipo no entra en el gasto ni en el resultado
    assert sin["gasto"]["mes"] == "0.00"


def test_el_detalle_de_cuentas_exige_drilldown(
    cliente: TestClient, mundo: Mundo, con_deptos: Escenario, db: Session
) -> None:
    ve = cliente.get(_url(mundo), headers=como(ANALISTA)).json()
    assert ve["detalle_de_cuentas"] is True
    hk = next(x for x in ve["departamentos"] if x["departamento"] == "HOUSEKEEPING")
    assert hk["cuentas"][0]["codigo"] == "6009001.001" and hk["cuentas"][0]["mes"] == "30.00"
    # Dirección (sin `drilldown:leer`) ve los totales pero no las cuentas
    from fpa.identidad.permisos import Permiso, RolCodigo, rol_tiene_permiso

    assert rol_tiene_permiso(RolCodigo.DIRECCION, Permiso.VARIANCE_LEER)
    assert not rol_tiene_permiso(RolCodigo.DIRECCION, Permiso.DRILLDOWN_LEER)


def test_permisos_y_aislamiento(
    cliente: TestClient, mundo: Mundo, con_deptos: Escenario, db: Session
) -> None:
    assert cliente.get(_url(mundo)).status_code == 401
    assert cliente.get(_url(mundo), headers=como(OTRA_ORG)).status_code == 404
    assert cliente.get(_url(mundo, "2026-13"), headers=como(ANALISTA)).status_code == 422
    # un departamento cruza secciones: quien tiene el acceso limitado no lo ve
    _asignar(db, mundo, "Rooms")
    assert cliente.get(_url(mundo), headers=como(RESPONSABLE)).status_code == 403
    # el hotel B no ve nada del A
    otro = f"/api/v1/hoteles/{mundo.hotel_b}/variance/departamentos?periodo=2026-08"
    assert cliente.get(otro, headers=como(CONTRALOR)).status_code == 404


def test_sin_mapeo_aprobado_es_404(cliente: TestClient, mundo: Mundo) -> None:
    r = cliente.get(_url(mundo), headers=como(ANALISTA))
    assert r.status_code == 404 and "mapeo" in r.json()["detail"].lower()


def test_un_periodo_cerrado_usa_el_mapeo_congelado(
    cliente: TestClient, mundo: Mundo, con_deptos: Escenario, db: Session
) -> None:
    base = f"/api/v1/hoteles/{mundo.hotel_a}"
    for hacia in ("comentado", "revisado", "aprobado"):
        usuario = CONTRALOR if hacia == "aprobado" else ANALISTA
        cliente.post(
            f"{base}/cierres/2026-08/transiciones", json={"hacia": hacia}, headers=como(usuario)
        )
    kw = con_deptos.kw
    nuevo = crear_borrador_desde(
        db, organizacion_id=mundo.org1, hotel_id=mundo.hotel_a, usuario_id=None
    )
    quitar_vinculo(
        db,
        version_id=nuevo.id,
        linea_id=con_deptos.linea("Gasto"),
        cuenta_codigo="6009001.001",
        **kw,  # type: ignore[arg-type]
    )
    from fpa.servicios.versionado_mapeo import excluir_cuenta

    excluir_cuenta(db, version_id=nuevo.id, cuenta_codigo="6009001.001", motivo="x", **kw)  # type: ignore[arg-type]
    aprobar(db, version_id=nuevo.id, **kw)  # type: ignore[arg-type]
    db.commit()
    cerrado = cliente.get(_url(mundo), headers=como(ANALISTA)).json()
    assert cerrado["version_mapeo_id"] == con_deptos.borrador.id  # type: ignore[union-attr]
    assert any(x["departamento"] == "HOUSEKEEPING" for x in cerrado["departamentos"])
    abierto = cliente.get(_url(mundo, "2026-07"), headers=como(ANALISTA)).json()
    assert abierto["version_mapeo_id"] == nuevo.id
