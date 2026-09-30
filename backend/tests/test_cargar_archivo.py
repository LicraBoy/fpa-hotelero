import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import Mundo
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fpa.ingesta.contrato import Fuente, ResultadoLectura
from fpa.ingesta.contrato import Movimiento as MovimientoLeido
from fpa.ingesta.novohit_con130 import leer_con130
from fpa.ingesta.variance_base_datos import leer_variance_base_datos
from fpa.modelos import CargaArchivo, EstadoCarga, EventoAuditoria, Movimiento, Usuario
from fpa.modelos.auditoria import AuditoriaInmutable
from fpa.repositorios.auditoria import RepositorioAuditoria
from fpa.repositorios.cargas import RepositorioCargas
from fpa.servicios.cargar_archivo import Resolucion, cargar_archivo
from fpa.servicios.cargas import DatosArchivo

D = Decimal
_CARPETA_DOCUMENTOS = Path(
    os.environ.get(
        "FPA_DATOS_REALES", Path.home() / "Desktop" / "PLATAFORMA FP&A E INTELIGENCIA HOTELERA"
    )
)
CON130 = _CARPETA_DOCUMENTOS / "BASE DATOS.xlsx"
VARIANCE = _CARPETA_DOCUMENTOS / "02. VT August 2026 Variance (Envio) (1).xlsx"
A, B, C = "a" * 64, "b" * 64, "c" * 64


def mov(fecha: date, debito: str, fila: int = 1) -> MovimientoLeido:
    return MovimientoLeido(
        cuenta_codigo="4001002.001",
        cuenta_descripcion="INGRESOS",
        asiento="8.3.1",
        fecha=fecha,
        concepto="X",
        debito=D(debito),
        credito=D("0"),
        fila=fila,
    )


def lectura(*movs: MovimientoLeido) -> ResultadoLectura:
    return ResultadoLectura(
        fuente=Fuente.VARIANCE_BASE_DATOS, controla_balance=False, movimientos=list(movs)
    )


def cargar(
    db: Session,
    mundo: Mundo,
    res: ResultadoLectura,
    sha: str = A,
    nombre: str = "archivo.xlsx",
    confirmar: bool = False,
    hotel: int | None = None,
):  # type: ignore[no-untyped-def]
    usuario = db.scalar(select(Usuario.id).where(Usuario.email == "analista_a@test.local"))
    resultado = cargar_archivo(
        db,
        organizacion_id=mundo.org1,
        hotel_id=hotel or mundo.hotel_a,
        usuario_id=usuario,
        resultado=res,
        archivo=DatosArchivo(nombre, sha),
        confirmar_reemplazo=confirmar,
    )
    db.commit()
    return resultado


def n(db: Session, modelo: type) -> int:
    return db.scalar(select(func.count()).select_from(modelo)) or 0


def acciones(db: Session, hotel: int) -> list[str]:
    return [e.accion for e in RepositorioAuditoria(db, hotel).listar()]


JULIO = mov(date(2026, 7, 10), "100.00")
AGOSTO = mov(date(2026, 8, 10), "200.00", fila=2)
AGOSTO_CORREGIDO = mov(date(2026, 8, 10), "250.00", fila=2)
SEPTIEMBRE = mov(date(2026, 9, 10), "300.00", fila=3)


def test_primera_carga_se_crea_y_se_audita(db: Session, mundo: Mundo) -> None:
    r = cargar(db, mundo, lectura(JULIO, AGOSTO))
    assert r.resolucion == Resolucion.CREADA
    assert [c.periodo for c in r.cargas] == ["2026-07", "2026-08"]
    eventos = RepositorioAuditoria(db, mundo.hotel_a).listar("carga.creada")
    assert len(eventos) == 2
    e = eventos[0]
    assert e.usuario_id is not None and e.organizacion_id == mundo.org1
    assert e.entidad == "carga_archivo" and e.entidad_id == r.cargas[0].id
    assert e.detalle and e.detalle["sha256"] == A and e.detalle["total_debito"] == "100.00"


def test_cargar_dos_veces_el_mismo_archivo_no_cambia_nada(db: Session, mundo: Mundo) -> None:
    primera = cargar(db, mundo, lectura(JULIO, AGOSTO))
    cargas_antes, movs_antes = n(db, CargaArchivo), n(db, Movimiento)
    segunda = cargar(db, mundo, lectura(JULIO, AGOSTO))
    assert segunda.resolucion == Resolucion.DUPLICADA
    assert segunda.sin_cambio == ["2026-07", "2026-08"]
    assert [c.id for c in segunda.cargas] == [c.id for c in primera.cargas]
    assert (n(db, CargaArchivo), n(db, Movimiento)) == (cargas_antes, movs_antes)
    assert acciones(db, mundo.hotel_a)[-1] == "carga.duplicada"


def test_otro_archivo_para_el_mismo_periodo_pide_confirmacion_y_no_escribe(
    db: Session, mundo: Mundo
) -> None:
    cargar(db, mundo, lectura(AGOSTO), sha=A, nombre="original.xlsx")
    antes = (n(db, CargaArchivo), n(db, Movimiento), n(db, EventoAuditoria))
    r = cargar(db, mundo, lectura(AGOSTO_CORREGIDO), sha=B, nombre="corregido.xlsx")
    assert r.resolucion == Resolucion.REQUIERE_CONFIRMACION
    (conflicto,) = r.conflictos
    assert conflicto.periodo == "2026-08"
    assert conflicto.archivo_vigente == "original.xlsx"
    assert (conflicto.debito_vigente, conflicto.debito_nuevo) == (D("200.00"), D("250.00"))
    assert (n(db, CargaArchivo), n(db, Movimiento), n(db, EventoAuditoria)) == antes
    vigente = RepositorioCargas(db, mundo.hotel_a).vigente_de_periodo("2026-08")
    assert vigente is not None and vigente.sha256 == A


def test_confirmar_reemplaza_conserva_historial_y_audita(db: Session, mundo: Mundo) -> None:
    primera = cargar(db, mundo, lectura(AGOSTO), sha=A, nombre="original.xlsx")
    r = cargar(db, mundo, lectura(AGOSTO_CORREGIDO), sha=B, nombre="corregido.xlsx", confirmar=True)
    assert r.resolucion == Resolucion.REEMPLAZADA
    vieja, nueva = primera.cargas[0], r.cargas[0]
    db.refresh(vieja)
    assert vieja.estado == EstadoCarga.REEMPLAZADA.value
    assert vieja.reemplazada_por_id == nueva.id and vieja.reemplazada_en is not None
    assert nueva.estado == EstadoCarga.VIGENTE.value
    repo = RepositorioCargas(db, mundo.hotel_a)
    assert [m.debito for m in repo.movimientos_vigentes("2026-08")] == [D("250.00")]
    assert [m.debito for m in repo.movimientos_de_carga(vieja.id)] == [D("200.00")]  # historial
    (evento,) = RepositorioAuditoria(db, mundo.hotel_a).listar("carga.reemplazada")
    assert evento.entidad_id == vieja.id and evento.usuario_id is not None
    assert evento.detalle and evento.detalle["reemplazada_por_id"] == nueva.id
    assert evento.detalle["total_debito_anterior"] == "200.00"
    assert evento.detalle["total_debito_nuevo"] == "250.00"


def test_archivo_con_varios_meses_reemplaza_solo_lo_que_choca(db: Session, mundo: Mundo) -> None:
    cargar(db, mundo, lectura(JULIO, AGOSTO), sha=A)
    # Nuevo archivo: agosto corregido (choca) y septiembre (nuevo)
    sin_confirmar = cargar(db, mundo, lectura(AGOSTO_CORREGIDO, SEPTIEMBRE), sha=B)
    assert sin_confirmar.resolucion == Resolucion.REQUIERE_CONFIRMACION
    assert [c.periodo for c in sin_confirmar.conflictos] == ["2026-08"]
    assert n(db, CargaArchivo) == 2  # nada se escribió, ni siquiera septiembre

    r = cargar(db, mundo, lectura(AGOSTO_CORREGIDO, SEPTIEMBRE), sha=B, confirmar=True)
    assert r.resolucion == Resolucion.REEMPLAZADA
    assert [c.periodo for c in r.cargas] == ["2026-08", "2026-09"]
    repo = RepositorioCargas(db, mundo.hotel_a)
    assert repo.vigente_de_periodo("2026-07").sha256 == A  # type: ignore[union-attr]
    assert repo.vigente_de_periodo("2026-08").sha256 == B  # type: ignore[union-attr]
    assert repo.vigente_de_periodo("2026-09").sha256 == B  # type: ignore[union-attr]


def test_recargar_el_archivo_original_omite_los_periodos_sin_cambio(
    db: Session, mundo: Mundo
) -> None:
    cargar(db, mundo, lectura(JULIO, AGOSTO), sha=A)
    cargar(db, mundo, lectura(AGOSTO_CORREGIDO), sha=B, confirmar=True)  # agosto pasó a B
    r = cargar(db, mundo, lectura(JULIO, AGOSTO), sha=A)
    assert r.resolucion == Resolucion.REQUIERE_CONFIRMACION
    assert [c.periodo for c in r.conflictos] == ["2026-08"]  # julio ya es el mismo archivo
    r = cargar(db, mundo, lectura(JULIO, AGOSTO), sha=A, confirmar=True)
    assert r.resolucion == Resolucion.REEMPLAZADA
    assert r.sin_cambio == ["2026-07"]
    assert [c.periodo for c in r.cargas] == ["2026-08"]  # julio no se duplicó
    assert n(db, Movimiento) == 4  # julio, agosto(A), agosto(B), agosto(A otra vez)


def test_lectura_invalida_se_rechaza_y_queda_en_la_auditoria(db: Session, mundo: Mundo) -> None:
    mala = lectura(JULIO)
    mala.errores.append("Fila 9: monto inválido")
    r = cargar(db, mundo, mala)
    assert r.resolucion == Resolucion.RECHAZADA and r.motivos == ["Fila 9: monto inválido"]
    assert n(db, CargaArchivo) == 0 and n(db, Movimiento) == 0
    (evento,) = RepositorioAuditoria(db, mundo.hotel_a).listar("carga.rechazada")
    assert evento.detalle and evento.detalle["motivos"] == ["Fila 9: monto inválido"]


def test_archivo_vacio_o_sin_fuente_se_rechaza(db: Session, mundo: Mundo) -> None:
    assert cargar(db, mundo, ResultadoLectura(fuente=Fuente.CON130)).resolucion == (
        Resolucion.RECHAZADA
    )
    assert cargar(db, mundo, ResultadoLectura(movimientos=[JULIO])).resolucion == (
        Resolucion.RECHAZADA
    )


def test_si_el_reemplazo_falla_la_carga_anterior_sigue_vigente(db: Session, mundo: Mundo) -> None:
    cargar(db, mundo, lectura(AGOSTO), sha=A)
    mala = lectura(mov(date(2026, 8, 10), "1.234"))  # tres decimales: la base lo rechaza
    with pytest.raises(Exception, match="más de 2 decimales"):
        cargar(db, mundo, mala, sha=B, confirmar=True)
    db.rollback()
    vigente = RepositorioCargas(db, mundo.hotel_a).vigente_de_periodo("2026-08")
    assert vigente is not None and vigente.sha256 == A
    assert n(db, CargaArchivo) == 1
    assert "carga.reemplazada" not in acciones(db, mundo.hotel_a)


def test_la_auditoria_no_se_puede_modificar_ni_borrar(db: Session, mundo: Mundo) -> None:
    cargar(db, mundo, lectura(JULIO))
    evento = db.scalars(select(EventoAuditoria)).first()
    assert evento is not None
    evento.accion = "otra.cosa"
    with pytest.raises(AuditoriaInmutable):
        db.flush()
    db.rollback()
    evento = db.scalars(select(EventoAuditoria)).first()
    assert evento is not None
    db.delete(evento)
    with pytest.raises(AuditoriaInmutable):
        db.flush()
    db.rollback()
    assert n(db, EventoAuditoria) == 1


def test_mismo_periodo_en_otro_hotel_no_es_conflicto_y_la_auditoria_se_separa(
    db: Session, mundo: Mundo
) -> None:
    cargar(db, mundo, lectura(AGOSTO), sha=A, hotel=mundo.hotel_a)
    r = cargar(db, mundo, lectura(AGOSTO_CORREGIDO), sha=B, hotel=mundo.hotel_b)
    assert r.resolucion == Resolucion.CREADA
    assert acciones(db, mundo.hotel_a) == ["carga.creada"]
    assert acciones(db, mundo.hotel_b) == ["carga.creada"]


# --- Con los archivos reales de Torres ---------------------------------------------------------


@pytest.mark.skipif(
    not (CON130.exists() and VARIANCE.exists()), reason="Faltan los Excel reales de Torres"
)
def test_flujo_real_variance_y_con130(db: Session, mundo: Mundo) -> None:
    variance = leer_variance_base_datos(VARIANCE)
    con130 = leer_con130(CON130)
    r1 = cargar(db, mundo, variance, sha=A, nombre="variance.xlsx")
    r2 = cargar(db, mundo, con130, sha=B, nombre="con130.xlsx")
    assert r1.resolucion == r2.resolucion == Resolucion.CREADA
    assert n(db, Movimiento) == 6860 + 7242
    assert cargar(db, mundo, variance, sha=A).resolucion == Resolucion.DUPLICADA
    assert cargar(db, mundo, con130, sha=B).resolucion == Resolucion.DUPLICADA
    assert n(db, Movimiento) == 6860 + 7242
    periodos = [c.periodo for c in RepositorioCargas(db, mundo.hotel_a).listar()]
    assert periodos == ["2026-07", "2026-08", "2026-09"]
