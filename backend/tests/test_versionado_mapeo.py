from datetime import date
from decimal import Decimal

import pytest
from conftest import Mundo
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.ingesta.contrato import Fuente, ResultadoLectura
from fpa.ingesta.contrato import Movimiento as MovimientoLeido
from fpa.ingesta.variance_estructura import leer_variance_estructura_filas
from fpa.ingesta.variance_mapeo import leer_variance_mapeo_filas
from fpa.modelos.auditoria import EventoAuditoria
from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.cargar_archivo import Resolucion, cargar_archivo
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.estructura_reporte import importar_estructura_reporte
from fpa.servicios.mapeo import importar_mapeo
from fpa.servicios.validacion_mapeo import validar_mapeo
from fpa.servicios.versionado_mapeo import (
    AprobacionBloqueada,
    MapeoInvalido,
    VersionInmutable,
    agregar_vinculo,
    aprobar,
    crear_borrador_desde,
    descartar_borrador,
    excluir_cuenta,
    quitar_vinculo,
)

D = Decimal


def fila(b=None, c=None, d=None, s=None, t=None):  # type: ignore[no-untyped-def]
    return (None, b, c, d, *([None] * 14), s, t)


EJEMPLO = [
    fila(),
    fila("Account #", "Account Description", "AUGUST"),
    fila(None, None, "Actual"),
    fila("029-0000-1-000", "Ingreso", 100, "=-'4001002.001'!L5", None),
    fila("029-0000-2-000", "Gasto", 30, "='6009001.001'!L9", None),
    fila(None, "T o t a l", 70, "=S4-S5", None),
]


def _mov(cuenta: str, debito: str, credito: str) -> MovimientoLeido:
    return MovimientoLeido(
        cuenta_codigo=cuenta,
        cuenta_descripcion=cuenta,
        asiento="8.1.1",
        fecha=date(2026, 8, 5),
        concepto="x",
        debito=D(debito),
        credito=D(credito),
        fila=1,
    )


class Escenario:
    def __init__(self, db: Session, mundo: Mundo, movimientos: list[MovimientoLeido]) -> None:
        self.db, self.mundo = db, mundo
        r = ResultadoLectura(fuente=Fuente.VARIANCE_BASE_DATOS, controla_balance=False)
        r.movimientos = movimientos
        res = cargar_archivo(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=None,
            resultado=r,
            archivo=DatosArchivo(nombre="m.xlsx", sha256="m" * 64),
        )
        assert res.resolucion is Resolucion.CREADA
        est = leer_variance_estructura_filas(EJEMPLO)
        ver = importar_estructura_reporte(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=None,
            resultado=est,
            archivo=DatosArchivo(nombre="v.xlsx", sha256="a" * 64),
        ).version
        assert ver is not None
        self.estructura = ver
        self.borrador = importar_mapeo(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=None,
            version_estructura=ver,
            leido=leer_variance_mapeo_filas(EJEMPLO, est),
            archivo=DatosArchivo(nombre="v.xlsx", sha256="a" * 64),
        ).version
        assert self.borrador is not None
        db.commit()

    @property
    def kw(self) -> dict[str, int | None]:
        return {
            "organizacion_id": self.mundo.org1,
            "hotel_id": self.mundo.hotel_a,
            "usuario_id": None,
        }

    def linea(self, descripcion: str) -> int:
        lineas = RepositorioReporte(self.db, self.mundo.hotel_a).lineas(self.estructura.id)
        return next(x.id for x in lineas if x.descripcion == descripcion)


@pytest.fixture
def esc(db: Session, mundo: Mundo) -> Escenario:
    return Escenario(db, mundo, [_mov("4001002.001", "0", "100"), _mov("6009001.001", "30", "0")])


def test_aprobar_marca_aprobada_y_es_inmutable(esc: Escenario) -> None:
    version = aprobar(esc.db, version_id=esc.borrador.id, **esc.kw)  # type: ignore[union-attr, arg-type]
    esc.db.commit()
    assert version.estado == "aprobada" and version.aprobada_en is not None
    repo = RepositorioMapeo(esc.db, esc.mundo.hotel_a)
    assert repo.aprobada() is not None and repo.borrador() is None
    linea = esc.linea("Ingreso")
    with pytest.raises(VersionInmutable):
        agregar_vinculo(
            esc.db,
            version_id=version.id,
            linea_id=linea,
            cuenta_codigo="9",
            signo=1,
            **esc.kw,  # type: ignore[arg-type]
        )
    with pytest.raises(VersionInmutable):
        quitar_vinculo(
            esc.db,
            version_id=version.id,
            linea_id=linea,
            cuenta_codigo="4001002.001",
            **esc.kw,  # type: ignore[arg-type]
        )
    with pytest.raises(VersionInmutable):
        excluir_cuenta(esc.db, version_id=version.id, cuenta_codigo="9", motivo="x", **esc.kw)  # type: ignore[arg-type]
    with pytest.raises(VersionInmutable):
        aprobar(esc.db, version_id=version.id, **esc.kw)  # type: ignore[arg-type]
    with pytest.raises(VersionInmutable):
        descartar_borrador(esc.db, version_id=version.id, **esc.kw)  # type: ignore[arg-type]


def test_no_se_aprueba_con_cuentas_sin_mapear(db: Session, mundo: Mundo) -> None:
    esc = Escenario(db, mundo, [_mov("4001002.001", "0", "100"), _mov("4999999", "0", "50")])
    with pytest.raises(AprobacionBloqueada) as e:
        aprobar(esc.db, version_id=esc.borrador.id, **esc.kw)  # type: ignore[union-attr, arg-type]
    assert "no están mapeadas" in e.value.motivos[0]
    assert RepositorioMapeo(db, mundo.hotel_a).aprobada() is None


def test_excluir_a_proposito_permite_aprobar_y_queda_auditado(db: Session, mundo: Mundo) -> None:
    esc = Escenario(db, mundo, [_mov("4001002.001", "0", "100"), _mov("4999999", "0", "50")])
    id_ = esc.borrador.id  # type: ignore[union-attr]
    with pytest.raises(MapeoInvalido):
        excluir_cuenta(db, version_id=id_, cuenta_codigo="4999999", motivo="  ", **esc.kw)  # type: ignore[arg-type]
    excluir_cuenta(
        db,
        version_id=id_,
        cuenta_codigo="4999999",
        motivo="Ingreso no operativo",
        **esc.kw,  # type: ignore[arg-type]
    )
    r = validar_mapeo(db, hotel_id=mundo.hotel_a, version_mapeo_id=id_, periodo="2026-08")
    assert r.aprobable and r.excluidas_con_movimiento == ["4999999"]
    aprobar(db, version_id=id_, **esc.kw)  # type: ignore[arg-type]
    db.commit()
    evento = db.scalar(select(EventoAuditoria).where(EventoAuditoria.accion == "mapeo.aprobado"))
    assert evento is not None and evento.detalle is not None
    assert evento.detalle["excluidas"] == ["4999999"]


def test_borrador_se_edita_y_el_vinculo_manual_quita_la_exclusion(esc: Escenario) -> None:
    db, id_ = esc.db, esc.borrador.id  # type: ignore[union-attr]
    linea = esc.linea("Gasto")
    excluir_cuenta(db, version_id=id_, cuenta_codigo="6009999", motivo="m", **esc.kw)  # type: ignore[arg-type]
    v = agregar_vinculo(
        db, version_id=id_, linea_id=linea, cuenta_codigo="6009999", signo=1, **esc.kw
    )  # type: ignore[arg-type]
    assert v.origen == "manual"
    repo = RepositorioMapeo(db, esc.mundo.hotel_a)
    assert repo.excluidas(id_) == []
    # repetir con otro signo cambia el signo, no duplica
    agregar_vinculo(db, version_id=id_, linea_id=linea, cuenta_codigo="6009999", signo=-1, **esc.kw)  # type: ignore[arg-type]
    assert [x.signo for x in repo.vinculos(id_) if x.cuenta_codigo == "6009999"] == [-1]
    quitar_vinculo(db, version_id=id_, linea_id=linea, cuenta_codigo="6009999", **esc.kw)  # type: ignore[arg-type]
    assert all(x.cuenta_codigo != "6009999" for x in repo.vinculos(id_))
    with pytest.raises(LookupError):
        quitar_vinculo(db, version_id=id_, linea_id=linea, cuenta_codigo="6009999", **esc.kw)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("linea", "signo", "cuenta"),
    [("Total", 1, "1"), ("Gasto", 2, "1"), ("Gasto", 1, "  "), ("no existe", 1, "1")],
)
def test_ediciones_invalidas(esc: Escenario, linea: str, signo: int, cuenta: str) -> None:
    try:
        linea_id = esc.linea(linea)
    except StopIteration:
        linea_id = 10**9
    with pytest.raises(MapeoInvalido):
        agregar_vinculo(
            esc.db,
            version_id=esc.borrador.id,
            linea_id=linea_id,
            cuenta_codigo=cuenta,
            signo=signo,
            **esc.kw,  # type: ignore[union-attr, arg-type]
        )


def test_nuevo_borrador_copia_la_aprobada_y_aprobarlo_la_reemplaza(esc: Escenario) -> None:
    db = esc.db
    primera = aprobar(db, version_id=esc.borrador.id, **esc.kw)  # type: ignore[union-attr, arg-type]
    db.commit()
    copia = crear_borrador_desde(db, **esc.kw)  # type: ignore[arg-type]
    db.commit()
    repo = RepositorioMapeo(db, esc.mundo.hotel_a)
    assert copia.numero == 2 and copia.origen == "copia de la versión 1"
    ver = lambda v: [(x.linea_id, x.cuenta_codigo, x.signo) for x in repo.vinculos(v.id)]  # noqa: E731
    assert ver(copia) == ver(primera) and len(ver(copia)) == 2
    with pytest.raises(MapeoInvalido):  # solo un borrador a la vez
        crear_borrador_desde(db, **esc.kw)  # type: ignore[arg-type]
    agregar_vinculo(
        db,
        version_id=copia.id,
        linea_id=esc.linea("Gasto"),
        cuenta_codigo="6009002",
        signo=1,
        **esc.kw,  # type: ignore[arg-type]
    )
    assert len(ver(copia)) == 3 and len(ver(primera)) == 2  # la aprobada no cambió
    segunda = aprobar(db, version_id=copia.id, **esc.kw)  # type: ignore[arg-type]
    db.commit()
    assert [v.estado for v in repo.versiones()] == ["reemplazada", "aprobada"]
    assert repo.aprobada() is not None and repo.aprobada().id == segunda.id  # type: ignore[union-attr]


def test_descartar_borrador_y_aislamiento(esc: Escenario) -> None:
    db = esc.db
    id_ = esc.borrador.id  # type: ignore[union-attr]
    with pytest.raises(LookupError):  # otro hotel no ve la versión
        agregar_vinculo(
            db,
            organizacion_id=esc.mundo.org1,
            hotel_id=esc.mundo.hotel_b,
            usuario_id=None,
            version_id=id_,
            linea_id=1,
            cuenta_codigo="1",
            signo=1,
        )
    with pytest.raises(LookupError):
        aprobar(
            db,
            organizacion_id=esc.mundo.org1,
            hotel_id=esc.mundo.hotel_b,
            usuario_id=None,
            version_id=id_,
        )
    descartar_borrador(db, version_id=id_, **esc.kw)  # type: ignore[arg-type]
    assert RepositorioMapeo(db, esc.mundo.hotel_a).borrador() is None
    acciones = [e.accion for e in db.scalars(select(EventoAuditoria))]
    assert "mapeo.borrador_descartado" in acciones


def test_sin_movimientos_no_hay_contra_que_validar(db: Session, mundo: Mundo) -> None:
    est = leer_variance_estructura_filas(EJEMPLO)
    ver = importar_estructura_reporte(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        resultado=est,
        archivo=DatosArchivo(nombre="v.xlsx", sha256="a" * 64),
    ).version
    assert ver is not None
    borrador = importar_mapeo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=mundo.hotel_a,
        usuario_id=None,
        version_estructura=ver,
        leido=leer_variance_mapeo_filas(EJEMPLO, est),
        archivo=DatosArchivo(nombre="v.xlsx", sha256="a" * 64),
    ).version
    assert borrador is not None
    with pytest.raises(AprobacionBloqueada):
        aprobar(
            db,
            organizacion_id=mundo.org1,
            hotel_id=mundo.hotel_a,
            usuario_id=None,
            version_id=borrador.id,
        )
