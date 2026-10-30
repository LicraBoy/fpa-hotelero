"""Captura por área del Budget (Fase 7.2): líneas del ciclo, captura de propuesta y mensualización.

Reglas de acceso (ADR 0003): sin sesión 401; hotel ajeno 404; sin permiso 403. Un responsable de
departamento solo ve y captura las líneas de las secciones que tiene asignadas
(`AsignacionDepartamento`) — lo que queda fuera responde 404, igual que en Comentarios.
"""

import logging
import re
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path as RutaArchivo
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, Request, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.api.v1.respuestas import RESPUESTAS_HOTEL
from fpa.api.v1.tipos import ID_MAX, FechaHoraUtc, IdConsulta, IdRuta
from fpa.config import settings
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado, principal_actual
from fpa.identidad.permisos import Permiso
from fpa.identidad.principal import Principal
from fpa.ingesta.budget_other_income import leer_other_income, normalizar
from fpa.ingesta.budget_seccion import leer_seccion
from fpa.modelos.identidad import Usuario
from fpa.modelos.presupuesto import (
    AnoFiscal,
    CicloPresupuesto,
    DetalleLineaPresupuesto,
    LineaPlanDetalle,
    LineaPresupuestoCaptura,
    PerfilDistribucion,
    PeriodoFiscal,
)
from fpa.modelos.reporte import LineaReporte
from fpa.repositorios.reporte import RepositorioReporte
from fpa.seguridad.archivos import (
    ArchivoRechazado,
    LimitesArchivo,
    guardar_en_temporal,
    inspeccionar_xlsx,
    limpiar_temporales,
    nombre_seguro,
    verificar_nombre,
)
from fpa.servicios.presupuesto_captura import (
    CapturaInvalida,
    capturar_propuesta,
    fijar_objetivo,
    lineas_visibles_de,
    resumen_ciclo,
    resumen_mensual_ciclo,
)
from fpa.servicios.presupuesto_ciclo import (
    TRANSICIONES,
    CicloInvalido,
    ciclo_de,
    crear_ano_fiscal,
    crear_ciclo,
    generar_periodos_fiscales,
    historial,
    transicionar,
)
from fpa.servicios.presupuesto_consumo import (
    editar_consumo_budget,
    quitar_consumo,
)
from fpa.servicios.presupuesto_detalle import (
    SECCION_ACCOUNTING,
    SECCION_APARTMENT_INTERIOR,
    SECCION_COMMON_AREA,
    SECCION_MAID_LINEN,
    SECCION_MGMT_CHECKIN,
    SECCION_OTHER_TAXES,
    SECCION_OWNER_ACTIVITIES,
    SECCION_OWNER_SERVICES,
    SECCION_PURCHASING,
    SECCION_UTILITIES,
    SECCION_VDS,
    CeldaDetalle,
    DetalleInvalido,
    guardar_detalle,
    importar_seccion,
    leer_detalle,
    leer_detalle_de_version,
)
from fpa.servicios.presupuesto_distribucion import (
    DistribucionInvalida,
    fijar_importes_mensuales,
    prorratear_con_perfil,
    sembrar_perfiles_sistema,
)
from fpa.servicios.presupuesto_hoja import (
    HojaInvalida,
    guardar_inflacion,
    leer_hoja,
)
from fpa.servicios.presupuesto_partidas import (
    PartidaEntrada,
    activar_partidas,
    guardar_inflacion_cuenta,
    guardar_partidas,
    leer_hoja_de_cuenta,
    quitar_partidas,
)

router = APIRouter(tags=["presupuesto"], responses=RESPUESTAS_HOTEL)
log = logging.getLogger(__name__)


def _leer_o_capturar(
    hotel_id: Annotated[int, Path(ge=1, le=ID_MAX)],
    principal: Principal = Depends(principal_actual),
) -> ContextoHotel:
    """Ver el ciclo de captura no exige `budget:leer` (eso es para las versiones importadas):
    basta con poder capturar, fijar el objetivo, o leer en este hotel."""
    if not principal.tiene_acceso_a(hotel_id):
        raise HTTPException(status_code=404, detail="Hotel no encontrado")
    if not (
        principal.puede(hotel_id, Permiso.BUDGET_LEER)
        or principal.puede(hotel_id, Permiso.BUDGET_CAPTURAR)
        or principal.puede(hotel_id, Permiso.BUDGET_OBJETIVO)
    ):
        raise HTTPException(status_code=403, detail="Sin permiso para esta acción")
    return ContextoHotel(principal=principal, hotel_id=hotel_id)


Leer = Annotated[ContextoHotel, Depends(_leer_o_capturar)]
Capturar = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.BUDGET_CAPTURAR))]
LeerBudget = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.BUDGET_LEER))]
Objetivo = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.BUDGET_OBJETIVO))]
# Administra el calendario fiscal y abre ciclos: hoy solo lo tiene el Contralor (BUDGET_APROBAR).
Administrar = Annotated[ContextoHotel, Depends(hotel_autorizado(Permiso.BUDGET_APROBAR))]
PATRON_PERIODO = r"^20\d{2}-(0[1-9]|1[0-2])$"
_Monto = Annotated[Decimal, Field(allow_inf_nan=False, max_digits=20, decimal_places=6)]


class LineaCapturaSalida(BaseModel):
    id: int
    linea_id: int
    descripcion: str
    seccion: str | None
    responsable_id: int | None
    objetivo: Decimal | None
    propuesta_anual: Decimal | None
    perfil_distribucion_id: int | None
    estado: str
    nota: str | None
    usa_partidas: bool = False
    usa_consumo: bool = False


class PropuestaEntrada(BaseModel):
    propuesta_anual: _Monto | None = None
    nota: str | None = Field(default=None, max_length=1000)


class ProrrateoPerfilEntrada(BaseModel):
    perfil_distribucion_id: int = Field(ge=1, le=ID_MAX)


class ImportesMensualesEntrada(BaseModel):
    importes: dict[str, _Monto]

    @field_validator("importes")
    @classmethod
    def _periodos_validos(cls, v: dict[str, Decimal]) -> dict[str, Decimal]:
        for periodo in v:
            if not re.match(PATRON_PERIODO, periodo):
                raise ValueError(f"«{periodo}» no tiene el formato AAAA-MM")
        return v


class LineaMensualSalida(BaseModel):
    periodo: str
    importe: Decimal


class PerfilSalida(BaseModel):
    id: int
    nombre: str
    pesos: list[str]
    es_sistema: bool


class CeldaDetalleEntrada(BaseModel):
    periodo: str = Field(pattern=PATRON_PERIODO)
    metodo: str = Field(pattern=r"^(factor|fijo)$")
    base: _Monto | None = None
    factor: _Monto | None = None
    monto_fijo: _Monto | None = None


class DetalleEntrada(BaseModel):
    celdas: list[CeldaDetalleEntrada] = Field(min_length=12, max_length=12)


class CeldaDetalleSalida(BaseModel):
    periodo: str
    metodo: str
    base: Decimal | None
    factor: Decimal | None
    monto_fijo: Decimal | None
    importe: Decimal


class ObjetivoEntrada(BaseModel):
    objetivo: _Monto | None = None


class ResumenSeccionPresupuestoSalida(BaseModel):
    seccion: str | None
    total_lineas: int
    lineas_capturadas: int
    cobertura_pct: Decimal
    suma_objetivo: Decimal
    suma_propuesta: Decimal


class ResumenPresupuestoSalida(BaseModel):
    total_lineas: int
    lineas_capturadas: int
    cobertura_pct: Decimal
    suma_objetivo: Decimal
    suma_propuesta: Decimal
    por_seccion: list[ResumenSeccionPresupuestoSalida]


class PuntoMensualCicloSalida(BaseModel):
    periodo: str
    propuesta: Decimal


class SeccionMensualCicloSalida(BaseModel):
    seccion: str | None
    por_periodo: list[PuntoMensualCicloSalida]


class ResumenMensualCicloSalida(BaseModel):
    por_periodo: list[PuntoMensualCicloSalida]
    lineas_sin_mensualizar: int
    por_seccion: list[SeccionMensualCicloSalida]


class AnoFiscalEntrada(BaseModel):
    etiqueta: str = Field(min_length=1, max_length=9)
    mes_inicio: int = Field(ge=1, le=12)
    mes_fin: int = Field(ge=1, le=12)


class AnoFiscalSalida(BaseModel):
    id: int
    etiqueta: str
    mes_inicio: int
    mes_fin: int
    estado: str


class PeriodoFiscalSalida(BaseModel):
    id: int
    periodo: str
    estado: str


class CicloEntrada(BaseModel):
    ano_fiscal_id: int = Field(ge=1, le=ID_MAX)


class TransicionPosibleCicloSalida(BaseModel):
    hacia: str
    etiqueta: str
    pide_nota: bool


class TransicionCicloSalida(BaseModel):
    desde: str
    hacia: str
    usuario: str
    nota: str | None
    creado_en: FechaHoraUtc


class CicloSalida(BaseModel):
    id: int
    ano_fiscal_id: int
    numero: int
    estado: str
    version_estructura_id: int | None
    version_plan_resultante_id: int | None
    creado_en: FechaHoraUtc
    aprobado_en: FechaHoraUtc | None
    transiciones_posibles: list[TransicionPosibleCicloSalida]
    historial: list[TransicionCicloSalida]


class ResumenCicloSalida(BaseModel):
    id: int
    ano_fiscal_id: int
    numero: int
    estado: str


class CambioEstadoCiclo(BaseModel):
    hacia: str = Field(min_length=1, max_length=12)
    nota: str | None = Field(default=None, max_length=1000)


def _ciclo_o_404(db: Session, hotel_id: int, ciclo_id: int) -> CicloPresupuesto:
    ciclo = ciclo_de(db, hotel_id, ciclo_id)
    if ciclo is None:
        raise HTTPException(status_code=404, detail="Ciclo de presupuesto no encontrado")
    if ciclo.version_estructura_id is None:
        # No debería ocurrir: 7.2 la congela al crear el ciclo. Defensivo por si algún dato viejo
        # no la tiene.
        raise HTTPException(
            status_code=409, detail="El ciclo no tiene una estructura de reporte asociada"
        )
    return ciclo


def _exigir_en_captura(ciclo: CicloPresupuesto) -> None:
    if ciclo.estado != "borrador":
        raise HTTPException(status_code=409, detail="El ciclo no está en captura")


def _exigir_visible(
    db: Session, contexto: ContextoHotel, ciclo: CicloPresupuesto, linea_id: int
) -> LineaPresupuestoCaptura:
    visibles = lineas_visibles_de(db, contexto, ciclo)
    if visibles is not None and linea_id not in visibles:
        raise HTTPException(status_code=404, detail="Línea de captura no encontrada")
    captura = db.scalar(
        select(LineaPresupuestoCaptura).where(
            LineaPresupuestoCaptura.ciclo_id == ciclo.id,
            LineaPresupuestoCaptura.linea_id == linea_id,
        )
    )
    if captura is None:
        raise HTTPException(status_code=404, detail="Línea de captura no encontrada")
    return captura


def _a_salida(db: Session, captura: LineaPresupuestoCaptura) -> LineaCapturaSalida:
    linea = db.get(LineaReporte, captura.linea_id)
    seccion = db.get(LineaReporte, linea.seccion_id) if linea and linea.seccion_id else None
    return LineaCapturaSalida(
        id=captura.id,
        linea_id=captura.linea_id,
        descripcion=linea.descripcion if linea else "",
        seccion=seccion.descripcion if seccion else None,
        responsable_id=captura.responsable_id,
        objetivo=captura.objetivo,
        propuesta_anual=captura.propuesta_anual,
        perfil_distribucion_id=captura.perfil_distribucion_id,
        estado=captura.estado,
        nota=captura.nota,
        usa_partidas=captura.usa_partidas,
        usa_consumo=captura.usa_consumo,
    )


def _ciclo_salida(db: Session, contexto: ContextoHotel, ciclo: CicloPresupuesto) -> CicloSalida:
    puede = contexto.principal.puede
    pasos = [
        TransicionPosibleCicloSalida(hacia=t.hacia, etiqueta=t.etiqueta, pide_nota=t.pide_nota)
        for t in TRANSICIONES
        if t.desde == ciclo.estado and puede(contexto.hotel_id, t.permiso)
    ]
    movimientos = historial(db, ciclo)
    nombres = {
        u.id: u.nombre
        for u in db.scalars(
            select(Usuario).where(Usuario.id.in_({m.usuario_id for m in movimientos}))
        )
    }
    return CicloSalida(
        id=ciclo.id,
        ano_fiscal_id=ciclo.ano_fiscal_id,
        numero=ciclo.numero,
        estado=ciclo.estado,
        version_estructura_id=ciclo.version_estructura_id,
        version_plan_resultante_id=ciclo.version_plan_resultante_id,
        creado_en=ciclo.creado_en,
        aprobado_en=ciclo.aprobado_en,
        transiciones_posibles=pasos,
        historial=[
            TransicionCicloSalida(
                desde=m.desde,
                hacia=m.hacia,
                usuario=nombres.get(m.usuario_id, "—"),
                nota=m.nota,
                creado_en=m.creado_en,
            )
            for m in movimientos
        ],
    )


@router.post(
    "/hoteles/{hotel_id}/presupuesto/anos-fiscales",
    response_model=AnoFiscalSalida,
    status_code=201,
)
def crear_ano(
    contexto: Administrar, entrada: AnoFiscalEntrada, db: Session = Depends(get_db)
) -> AnoFiscalSalida:
    try:
        ano = crear_ano_fiscal(
            db,
            hotel_id=contexto.hotel_id,
            etiqueta=entrada.etiqueta,
            mes_inicio=entrada.mes_inicio,
            mes_fin=entrada.mes_fin,
        )
    except CicloInvalido as e:
        raise HTTPException(status_code=e.status_code, detail=e.detalle) from None
    db.commit()
    return AnoFiscalSalida(
        id=ano.id,
        etiqueta=ano.etiqueta,
        mes_inicio=ano.mes_inicio,
        mes_fin=ano.mes_fin,
        estado=ano.estado,
    )


@router.get("/hoteles/{hotel_id}/presupuesto/anos-fiscales", response_model=list[AnoFiscalSalida])
def listar_anos(contexto: Leer, db: Session = Depends(get_db)) -> list[AnoFiscalSalida]:
    anos = db.scalars(
        select(AnoFiscal)
        .where(AnoFiscal.hotel_id == contexto.hotel_id)
        .order_by(AnoFiscal.etiqueta)
    )
    return [
        AnoFiscalSalida(
            id=a.id,
            etiqueta=a.etiqueta,
            mes_inicio=a.mes_inicio,
            mes_fin=a.mes_fin,
            estado=a.estado,
        )
        for a in anos
    ]


@router.post(
    "/hoteles/{hotel_id}/presupuesto/anos-fiscales/{ano_fiscal_id}/periodos/generar",
    response_model=list[PeriodoFiscalSalida],
)
def generar_periodos(
    contexto: Administrar, ano_fiscal_id: IdRuta, db: Session = Depends(get_db)
) -> list[PeriodoFiscalSalida]:
    ano = db.get(AnoFiscal, ano_fiscal_id)
    if ano is None or ano.hotel_id != contexto.hotel_id:
        raise HTTPException(status_code=404, detail="Año fiscal no encontrado")
    periodos = generar_periodos_fiscales(db, ano_fiscal_id=ano_fiscal_id)
    db.commit()
    return [PeriodoFiscalSalida(id=p.id, periodo=p.periodo, estado=p.estado) for p in periodos]


@router.get(
    "/hoteles/{hotel_id}/presupuesto/anos-fiscales/{ano_fiscal_id}/periodos",
    response_model=list[PeriodoFiscalSalida],
)
def listar_periodos(
    contexto: Leer, ano_fiscal_id: IdRuta, db: Session = Depends(get_db)
) -> list[PeriodoFiscalSalida]:
    ano = db.get(AnoFiscal, ano_fiscal_id)
    if ano is None or ano.hotel_id != contexto.hotel_id:
        raise HTTPException(status_code=404, detail="Año fiscal no encontrado")
    periodos = db.scalars(
        select(PeriodoFiscal)
        .where(PeriodoFiscal.ano_fiscal_id == ano_fiscal_id)
        .order_by(PeriodoFiscal.periodo)
    )
    return [PeriodoFiscalSalida(id=p.id, periodo=p.periodo, estado=p.estado) for p in periodos]


@router.post("/hoteles/{hotel_id}/presupuesto/ciclos", response_model=CicloSalida, status_code=201)
def crear_ciclo_presupuesto(
    contexto: Administrar, entrada: CicloEntrada, db: Session = Depends(get_db)
) -> CicloSalida:
    try:
        ciclo = crear_ciclo(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            ano_fiscal_id=entrada.ano_fiscal_id,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=404, detail=str(e.args[0]) if e.args else "No encontrado"
        ) from None
    except CicloInvalido as e:
        raise HTTPException(status_code=e.status_code, detail=e.detalle) from None
    db.commit()
    return _ciclo_salida(db, contexto, ciclo)


@router.get("/hoteles/{hotel_id}/presupuesto/ciclos", response_model=list[ResumenCicloSalida])
def listar_ciclos(
    contexto: Leer, ano_fiscal_id: IdConsulta | None = None, db: Session = Depends(get_db)
) -> list[ResumenCicloSalida]:
    consulta = select(CicloPresupuesto).where(CicloPresupuesto.hotel_id == contexto.hotel_id)
    if ano_fiscal_id is not None:
        consulta = consulta.where(CicloPresupuesto.ano_fiscal_id == ano_fiscal_id)
    ciclos = db.scalars(consulta.order_by(CicloPresupuesto.ano_fiscal_id, CicloPresupuesto.numero))
    return [
        ResumenCicloSalida(id=c.id, ano_fiscal_id=c.ano_fiscal_id, numero=c.numero, estado=c.estado)
        for c in ciclos
    ]


@router.get("/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}", response_model=CicloSalida)
def detalle_ciclo(contexto: Leer, ciclo_id: IdRuta, db: Session = Depends(get_db)) -> CicloSalida:
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    return _ciclo_salida(db, contexto, ciclo)


@router.post(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/transiciones",
    response_model=CicloSalida,
    responses={
        409: {"description": "La transición no existe desde el estado actual, o faltan líneas"},
        422: {"description": "Falta la nota que ese cambio exige"},
    },
)
def cambiar_estado_ciclo(
    contexto: Leer,
    ciclo_id: IdRuta,
    entrada: CambioEstadoCiclo,
    db: Session = Depends(get_db),
) -> CicloSalida:
    permisos = {p: contexto.principal.puede(contexto.hotel_id, p) for p in Permiso}
    try:
        ciclo = transicionar(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            puede=permisos,
            ciclo_id=ciclo_id,
            hacia=entrada.hacia,
            nota=entrada.nota,
        )
    except CicloInvalido as e:
        db.rollback()
        raise HTTPException(status_code=e.status_code, detail=e.detalle) from None
    db.commit()
    return _ciclo_salida(db, contexto, ciclo)


@router.get(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas",
    response_model=list[LineaCapturaSalida],
)
def listar_lineas(
    contexto: Leer, ciclo_id: IdRuta, db: Session = Depends(get_db)
) -> list[LineaCapturaSalida]:
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    version_estructura_id = ciclo.version_estructura_id
    if version_estructura_id is None:  # pragma: no cover - _ciclo_o_404 ya lo garantiza
        raise HTTPException(
            status_code=409, detail="El ciclo no tiene una estructura de reporte asociada"
        )
    visibles = lineas_visibles_de(db, contexto, ciclo)
    todas = RepositorioReporte(db, contexto.hotel_id).lineas(version_estructura_id)
    lineas = {x.id: x for x in todas}
    secciones = {x.id: x.descripcion for x in lineas.values() if x.tipo == "seccion"}
    capturas = db.scalars(
        select(LineaPresupuestoCaptura)
        .where(LineaPresupuestoCaptura.ciclo_id == ciclo.id)
        .order_by(LineaPresupuestoCaptura.linea_id)
    )
    salida = []
    for c in capturas:
        if visibles is not None and c.linea_id not in visibles:
            continue
        linea = lineas.get(c.linea_id)
        salida.append(
            LineaCapturaSalida(
                id=c.id,
                linea_id=c.linea_id,
                descripcion=linea.descripcion if linea else "",
                seccion=secciones.get(linea.seccion_id) if linea and linea.seccion_id else None,
                responsable_id=c.responsable_id,
                objetivo=c.objetivo,
                propuesta_anual=c.propuesta_anual,
                perfil_distribucion_id=c.perfil_distribucion_id,
                estado=c.estado,
                nota=c.nota,
                usa_partidas=c.usa_partidas,
                usa_consumo=c.usa_consumo,
            )
        )
    return salida


@router.put(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas/{linea_id}",
    response_model=LineaCapturaSalida,
)
def capturar(
    contexto: Capturar,
    ciclo_id: IdRuta,
    linea_id: IdRuta,
    entrada: PropuestaEntrada,
    db: Session = Depends(get_db),
) -> LineaCapturaSalida:
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    visibles = lineas_visibles_de(db, contexto, ciclo)
    try:
        captura = capturar_propuesta(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            ciclo_id=ciclo_id,
            linea_id=linea_id,
            propuesta_anual=entrada.propuesta_anual,
            nota=entrada.nota,
            visibles=visibles,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=404, detail=str(e.args[0]) if e.args else "No encontrado"
        ) from None
    except CapturaInvalida as e:
        raise HTTPException(status_code=e.status_code, detail=e.detalle) from None
    db.commit()
    return _a_salida(db, captura)


@router.get("/hoteles/{hotel_id}/presupuesto/perfiles", response_model=list[PerfilSalida])
def listar_perfiles(contexto: Leer, db: Session = Depends(get_db)) -> list[PerfilSalida]:
    sembrar_perfiles_sistema(db)
    db.commit()
    perfiles = db.scalars(
        select(PerfilDistribucion)
        .where(
            (PerfilDistribucion.hotel_id == contexto.hotel_id)
            | (PerfilDistribucion.hotel_id.is_(None))
        )
        .order_by(PerfilDistribucion.nombre)
    )
    return [
        PerfilSalida(id=p.id, nombre=p.nombre, pesos=p.pesos, es_sistema=p.es_sistema)
        for p in perfiles
    ]


@router.post(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas/{linea_id}/prorrateo",
    response_model=list[LineaMensualSalida],
)
def prorratear(
    contexto: Capturar,
    ciclo_id: IdRuta,
    linea_id: IdRuta,
    entrada: ProrrateoPerfilEntrada,
    db: Session = Depends(get_db),
) -> list[LineaMensualSalida]:
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    _exigir_en_captura(ciclo)
    captura = _exigir_visible(db, contexto, ciclo, linea_id)
    try:
        filas = prorratear_con_perfil(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            linea_captura_id=captura.id,
            perfil_distribucion_id=entrada.perfil_distribucion_id,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=404, detail=str(e.args[0]) if e.args else "No encontrado"
        ) from None
    except DistribucionInvalida as e:
        raise HTTPException(status_code=e.status_code, detail=e.detalle) from None
    db.commit()
    return [LineaMensualSalida(periodo=f.periodo, importe=f.importe) for f in filas]


@router.put(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas/{linea_id}/objetivo",
    response_model=LineaCapturaSalida,
)
def fijar_objetivo_linea(
    contexto: Objetivo,
    ciclo_id: IdRuta,
    linea_id: IdRuta,
    entrada: ObjetivoEntrada,
    db: Session = Depends(get_db),
) -> LineaCapturaSalida:
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    visibles = lineas_visibles_de(db, contexto, ciclo)
    try:
        captura = fijar_objetivo(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            ciclo_id=ciclo_id,
            linea_id=linea_id,
            objetivo=entrada.objetivo,
            visibles=visibles,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=404, detail=str(e.args[0]) if e.args else "No encontrado"
        ) from None
    except CapturaInvalida as e:
        raise HTTPException(status_code=e.status_code, detail=e.detalle) from None
    db.commit()
    return _a_salida(db, captura)


@router.get(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/resumen",
    response_model=ResumenPresupuestoSalida,
)
def resumen(
    contexto: Leer, ciclo_id: IdRuta, db: Session = Depends(get_db)
) -> ResumenPresupuestoSalida:
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    try:
        r = resumen_ciclo(db, ciclo=ciclo)
    except CapturaInvalida as e:
        raise HTTPException(status_code=e.status_code, detail=e.detalle) from None
    return ResumenPresupuestoSalida(
        total_lineas=r.total_lineas,
        lineas_capturadas=r.lineas_capturadas,
        cobertura_pct=r.cobertura_pct,
        suma_objetivo=r.suma_objetivo,
        suma_propuesta=r.suma_propuesta,
        por_seccion=[
            ResumenSeccionPresupuestoSalida(
                seccion=s.seccion,
                total_lineas=s.total_lineas,
                lineas_capturadas=s.lineas_capturadas,
                cobertura_pct=s.cobertura_pct,
                suma_objetivo=s.suma_objetivo,
                suma_propuesta=s.suma_propuesta,
            )
            for s in r.por_seccion
        ],
    )


@router.get(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/resumen-mensual",
    response_model=ResumenMensualCicloSalida,
)
def resumen_mensual(
    contexto: Leer, ciclo_id: IdRuta, db: Session = Depends(get_db)
) -> ResumenMensualCicloSalida:
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    r = resumen_mensual_ciclo(db, ciclo=ciclo)
    return ResumenMensualCicloSalida(
        por_periodo=[
            PuntoMensualCicloSalida(periodo=p.periodo, propuesta=p.propuesta) for p in r.por_periodo
        ],
        lineas_sin_mensualizar=r.lineas_sin_mensualizar,
        por_seccion=[
            SeccionMensualCicloSalida(
                seccion=s.seccion,
                por_periodo=[
                    PuntoMensualCicloSalida(periodo=p.periodo, propuesta=p.propuesta)
                    for p in s.por_periodo
                ],
            )
            for s in r.por_seccion
        ],
    )


@router.post(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas/{linea_id}/importes-mensuales",
    response_model=list[LineaMensualSalida],
)
def fijar_importes(
    contexto: Capturar,
    ciclo_id: IdRuta,
    linea_id: IdRuta,
    entrada: ImportesMensualesEntrada,
    db: Session = Depends(get_db),
) -> list[LineaMensualSalida]:
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    _exigir_en_captura(ciclo)
    captura = _exigir_visible(db, contexto, ciclo, linea_id)
    try:
        filas = fijar_importes_mensuales(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            linea_captura_id=captura.id,
            importes=entrada.importes,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=404, detail=str(e.args[0]) if e.args else "No encontrado"
        ) from None
    except DistribucionInvalida as e:
        raise HTTPException(status_code=e.status_code, detail=e.detalle) from None
    db.commit()
    return [LineaMensualSalida(periodo=f.periodo, importe=f.importe) for f in filas]


def _detalle_salida(
    filas: Sequence[DetalleLineaPresupuesto | LineaPlanDetalle],
) -> list[CeldaDetalleSalida]:
    return [
        CeldaDetalleSalida(
            periodo=f.periodo,
            metodo=f.metodo,
            base=f.base,
            factor=f.factor,
            monto_fijo=f.monto_fijo,
            importe=f.importe,
        )
        for f in filas
    ]


@router.get(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas/{linea_id}/detalle",
    response_model=list[CeldaDetalleSalida],
)
def ver_detalle(
    contexto: Leer, ciclo_id: IdRuta, linea_id: IdRuta, db: Session = Depends(get_db)
) -> list[CeldaDetalleSalida]:
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    visibles = lineas_visibles_de(db, contexto, ciclo)
    try:
        filas = leer_detalle(
            db,
            hotel_id=contexto.hotel_id,
            ciclo_id=ciclo_id,
            linea_id=linea_id,
            visibles=visibles,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=404, detail=str(e.args[0]) if e.args else "No encontrado"
        ) from None
    return _detalle_salida(filas)


@router.put(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas/{linea_id}/detalle",
    response_model=list[CeldaDetalleSalida],
)
def guardar_detalle_linea(
    contexto: Capturar,
    ciclo_id: IdRuta,
    linea_id: IdRuta,
    entrada: DetalleEntrada,
    db: Session = Depends(get_db),
) -> list[CeldaDetalleSalida]:
    """Reemplaza **completo** el detalle de la línea (no es parcial): 12 celdas, una por periodo."""
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    _exigir_en_captura(ciclo)
    visibles = lineas_visibles_de(db, contexto, ciclo)
    try:
        filas = guardar_detalle(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            ciclo_id=ciclo_id,
            linea_id=linea_id,
            celdas=[
                CeldaDetalle(
                    periodo=c.periodo,
                    metodo=c.metodo,
                    base=c.base,
                    factor=c.factor,
                    monto_fijo=c.monto_fijo,
                )
                for c in entrada.celdas
            ],
            visibles=visibles,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=404, detail=str(e.args[0]) if e.args else "No encontrado"
        ) from None
    except (DetalleInvalido, DistribucionInvalida) as e:
        raise HTTPException(status_code=e.status_code, detail=e.detalle) from None
    db.commit()
    return _detalle_salida(filas)


@router.get(
    "/hoteles/{hotel_id}/presupuesto/versiones/{version_plan_id}/lineas/{linea_id}/detalle",
    response_model=list[CeldaDetalleSalida],
)
def ver_detalle_de_version(
    contexto: LeerBudget,
    version_plan_id: IdRuta,
    linea_id: IdRuta,
    db: Session = Depends(get_db),
) -> list[CeldaDetalleSalida]:
    """El detalle congelado de una línea en una versión de Budget ya emitida (solo lectura)."""
    try:
        filas = leer_detalle_de_version(
            db, hotel_id=contexto.hotel_id, version_plan_id=version_plan_id, linea_id=linea_id
        )
    except LookupError as e:
        raise HTTPException(
            status_code=404, detail=str(e.args[0]) if e.args else "No encontrado"
        ) from None
    return _detalle_salida(filas)


class ImportacionDetalleSalida(BaseModel):
    importadas: int
    avisos: list[str]


_SECCIONES_IMPORTABLES = {
    "otherincome",
    SECCION_MGMT_CHECKIN,
    SECCION_ACCOUNTING,
    SECCION_MAID_LINEN,
    SECCION_APARTMENT_INTERIOR,
    SECCION_COMMON_AREA,
    SECCION_UTILITIES,
    SECCION_OWNER_ACTIVITIES,
    SECCION_OTHER_TAXES,
    SECCION_OWNER_SERVICES,
    SECCION_VDS,
    SECCION_PURCHASING,
    "telephones",
    "travelagency",
    "store",
    "cafeteria",
    "bar",
    "moneyexchange",
    "restaurant",
    "legal",
    "itsystems",
}
_NOMBRE_SECCION = {
    "legal": "Legal",
    "itsystems": "IT Systems",
    "telephones": "Telephones",
    "travelagency": "Travel Agency",
    "store": "Store",
    "cafeteria": "Cafeteria",
    "bar": "Bar",
    "moneyexchange": "Money Exchange",
    "restaurant": "Restaurant",
    SECCION_PURCHASING: "Purchasing",
    SECCION_VDS: "VDS Allocation Collections",
    SECCION_OWNER_SERVICES: "Owner Services",
    SECCION_OTHER_TAXES: "Other Taxes,Fees and Insurance",
    SECCION_OWNER_ACTIVITIES: "Owner Activities",
    SECCION_UTILITIES: "Utilities",
    SECCION_COMMON_AREA: "Common Area",
    SECCION_APARTMENT_INTERIOR: "Apartment Interior",
    SECCION_MGMT_CHECKIN: "Mgmt & Check In",
    SECCION_ACCOUNTING: "Accounting",
    SECCION_MAID_LINEN: "Maid & Linen",
}


def _seccion_importable(db: Session, ciclo: CicloPresupuesto, seccion_id: int | None) -> str:
    """Nombre normalizado de la sección que se va a importar (Other Income si no se indica)."""
    if seccion_id is None:
        return "otherincome"
    if ciclo.version_estructura_id is None:
        raise HTTPException(status_code=409, detail="El ciclo no tiene estructura de reporte")
    lineas = RepositorioReporte(db, ciclo.hotel_id).lineas(ciclo.version_estructura_id)
    linea = next((x for x in lineas if x.id == seccion_id and x.tipo == "seccion"), None)
    if linea is None:
        raise HTTPException(status_code=404, detail="Sección no encontrada")
    nombre = normalizar(linea.descripcion)
    if nombre not in _SECCIONES_IMPORTABLES:
        raise HTTPException(status_code=422, detail="Esa sección no se importa desde el Excel")
    # secciones repetidas (Store ventas / Store gastos): la clave lleva su ordinal en el reporte
    anteriores = [
        x for x in lineas
        if x.tipo == "seccion" and normalizar(x.descripcion) == nombre and x.orden < linea.orden
    ]  # fmt: skip
    return f"{nombre}#{len(anteriores) + 1}" if anteriores else nombre


@router.post(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/detalle/importar-other-income",
    response_model=ImportacionDetalleSalida,
)
def importar_detalle_other_income(
    request: Request,
    contexto: Capturar,
    ciclo_id: IdRuta,
    archivo: Annotated[
        UploadFile, File(description="Excel del Budget (.xlsx): hoja `Other Income` o la sección")
    ],
    seccion_id: Annotated[
        int | None,
        Query(description="Sección que se importa; sin ella, *Other Income* (compatibilidad)"),
    ] = None,
    linea_id: Annotated[
        int | None,
        Query(description="Solo trae las partidas de esta cuenta (su hoja de detalle del Excel)"),
    ] = None,
    db: Session = Depends(get_db),
) -> ImportacionDetalleSalida:
    """Llena la tabla interna de una sección del ciclo (*Other Income* o *Mgmt & Check In*)."""
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    _exigir_en_captura(ciclo)
    seccion = _seccion_importable(db, ciclo, seccion_id)
    visibles = lineas_visibles_de(db, contexto, ciclo)
    limites = LimitesArchivo.desde_settings()
    declarado = request.headers.get("content-length")
    if declarado and declarado.isdigit() and int(declarado) > limites.max_bytes + 64 * 1024:
        raise HTTPException(status_code=413, detail="El archivo supera el tamaño máximo")
    carpeta = RutaArchivo(settings.storage_dir) / "tmp"
    limpiar_temporales(carpeta)
    temporal: RutaArchivo | None = None
    try:
        try:
            verificar_nombre(nombre_seguro(archivo.filename))
            temporal, _sha, _tamano = guardar_en_temporal(archivo.file, carpeta, limites)
            inspeccionar_xlsx(temporal, limites)
        except ArchivoRechazado as e:
            raise HTTPException(status_code=e.status_code, detail=e.detalle) from None
        try:
            leido = (
                leer_other_income(temporal)
                if seccion == "otherincome"
                else leer_seccion(temporal, seccion, _NOMBRE_SECCION[seccion.partition("#")[0]])
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from None
        except Exception:
            log.exception("No se pudo leer Other Income del libro")
            raise HTTPException(status_code=422, detail="No se pudo leer el libro") from None
        try:
            resultado = importar_seccion(
                db,
                organizacion_id=contexto.organizacion_id,
                hotel_id=contexto.hotel_id,
                usuario_id=contexto.principal.usuario_id,
                ciclo_id=ciclo_id,
                leido=leido,
                visibles=visibles,
                seccion=seccion,
                linea_id=linea_id,
            )
        except LookupError as e:
            raise HTTPException(
                status_code=404, detail=str(e.args[0]) if e.args else "No encontrado"
            ) from None
        except (DetalleInvalido, DistribucionInvalida) as e:
            raise HTTPException(status_code=e.status_code, detail=e.detalle) from None
        db.commit()
        return ImportacionDetalleSalida(importadas=resultado.importadas, avisos=resultado.avisos)
    finally:
        if temporal is not None:
            try:
                temporal.unlink(missing_ok=True)
            except OSError:
                log.warning("No se pudo borrar el temporal %s; se limpiará después", temporal.name)


class CuentaHojaSalida(BaseModel):
    linea_id: int
    descripcion: str
    codigo: str | None
    estado: str
    meses: list[Decimal | None]


class HojaSalida(BaseModel):
    seccion_id: int
    seccion: str
    periodos: list[str]
    cuentas: list[CuentaHojaSalida]
    totales: list[Decimal]
    inflacion: list[Decimal | None]
    acumulada: list[Decimal]
    total_con_inflacion: list[Decimal]
    est_act: list[Decimal | None]
    budget_previo: list[Decimal | None]
    variacion: list[Decimal | None]
    variacion_pct: list[Decimal | None]
    origen: str | None


class InflacionEntrada(BaseModel):
    inflacion: dict[
        str, Annotated[Decimal, Field(allow_inf_nan=False, max_digits=10, decimal_places=6)]
    ]

    @field_validator("inflacion")
    @classmethod
    def _periodos_validos(cls, v: dict[str, Decimal]) -> dict[str, Decimal]:
        for periodo in v:
            if not re.match(PATRON_PERIODO, periodo):
                raise ValueError(f"«{periodo}» no tiene el formato AAAA-MM")
        return v


def _hoja_a_salida(h) -> HojaSalida:  # type: ignore[no-untyped-def]
    return HojaSalida(
        seccion_id=h.seccion_id,
        seccion=h.seccion,
        periodos=h.periodos,
        cuentas=[
            CuentaHojaSalida(
                linea_id=c.linea_id,
                descripcion=c.descripcion,
                codigo=c.codigo,
                estado=c.estado,
                meses=c.meses,
            )
            for c in h.cuentas
        ],
        totales=h.totales,
        inflacion=h.inflacion,
        acumulada=h.bloque.acumulada,
        total_con_inflacion=h.bloque.total_con_inflacion,
        est_act=h.est_act,
        budget_previo=h.budget_previo,
        variacion=h.bloque.variacion,
        variacion_pct=h.bloque.variacion_pct,
        origen=h.origen,
    )


@router.get(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/hojas/{seccion_id}",
    response_model=HojaSalida,
)
def ver_hoja(
    contexto: Leer, ciclo_id: IdRuta, seccion_id: IdRuta, db: Session = Depends(get_db)
) -> HojaSalida:
    """La hoja completa de una sección: sus cuentas por mes y el bloque inferior (inflación,
    total con inflación, Est Act y Budget del año previo, variación)."""
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    visibles = lineas_visibles_de(db, contexto, ciclo)
    try:
        hoja = leer_hoja(
            db,
            hotel_id=contexto.hotel_id,
            ciclo_id=ciclo_id,
            seccion_id=seccion_id,
            visibles=visibles,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=404, detail=str(e.args[0]) if e.args else "No encontrado"
        ) from None
    except (HojaInvalida, DistribucionInvalida) as e:
        raise HTTPException(status_code=e.status_code, detail=e.detalle) from None
    return _hoja_a_salida(hoja)


@router.put(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/hojas/{seccion_id}/inflacion",
    response_model=HojaSalida,
)
def guardar_inflacion_hoja(
    contexto: Capturar,
    ciclo_id: IdRuta,
    seccion_id: IdRuta,
    entrada: InflacionEntrada,
    db: Session = Depends(get_db),
) -> HojaSalida:
    """Reemplaza **completa** la inflación mensual (12 periodos; no es parcial). Informativa: no
    cambia el Budget de las cuentas."""
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    _exigir_en_captura(ciclo)
    visibles = lineas_visibles_de(db, contexto, ciclo)
    try:
        guardar_inflacion(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            ciclo_id=ciclo_id,
            seccion_id=seccion_id,
            inflacion=entrada.inflacion,
            visibles=visibles,
        )
        hoja = leer_hoja(
            db,
            hotel_id=contexto.hotel_id,
            ciclo_id=ciclo_id,
            seccion_id=seccion_id,
            visibles=visibles,
        )
    except LookupError as e:
        raise HTTPException(
            status_code=404, detail=str(e.args[0]) if e.args else "No encontrado"
        ) from None
    except (HojaInvalida, DistribucionInvalida) as e:
        raise HTTPException(status_code=e.status_code, detail=e.detalle) from None
    db.commit()
    return _hoja_a_salida(hoja)


# --- Hoja de cuenta: cuentas que se capturan por PARTIDAS (Cant. × Costo + reparto + inflación) ---


class PartidaEntradaApi(BaseModel):
    concepto: str = Field(min_length=1, max_length=120)
    cantidad: Annotated[Decimal, Field(allow_inf_nan=False, ge=0, max_digits=18, decimal_places=6)]
    unidad: str | None = Field(default=None, max_length=20)
    costo: Annotated[Decimal, Field(allow_inf_nan=False, ge=0, max_digits=18, decimal_places=6)]
    metodo: Literal["mensual", "estacional", "importada"]
    meses: (
        list[Annotated[Decimal, Field(allow_inf_nan=False, max_digits=18, decimal_places=6)]] | None
    ) = None


class PartidasEntrada(BaseModel):
    partidas: list[PartidaEntradaApi] = Field(min_length=1, max_length=200)
    inflacion: dict[
        str, Annotated[Decimal, Field(allow_inf_nan=False, max_digits=10, decimal_places=6)]
    ]

    @field_validator("inflacion")
    @classmethod
    def _periodos_validos(cls, v: dict[str, Decimal]) -> dict[str, Decimal]:
        for periodo in v:
            if not re.match(PATRON_PERIODO, periodo):
                raise ValueError(f"«{periodo}» no tiene el formato AAAA-MM")
        return v


class PartidaSalida(BaseModel):
    id: int | None
    orden: int
    concepto: str
    cantidad: Decimal
    unidad: str | None
    costo: Decimal
    metodo: str
    extendido: Decimal
    meses: list[Decimal]
    suma: Decimal
    diferencia: Decimal


class ConsumoMesSalida(BaseModel):
    unidades: Decimal | None
    costo_unitario: Decimal | None
    total: Decimal | None


class ConsumoSalida(BaseModel):
    """Consumo mensual de una cuenta de consumo.

    4 bloques × 12 meses de (unidades, costo, total).
    """

    unidad: str
    real_prev: list[ConsumoMesSalida]
    budget_prev: list[ConsumoMesSalida]
    est_act: list[ConsumoMesSalida]
    budget: list[ConsumoMesSalida]


class HojaCuentaSalida(HojaSalida):
    """La hoja de una cuenta por partidas. Misma forma que la hoja de sección (`cuentas` = las
    partidas con sus 12 meses, `totales` = la distribución) más los datos de cada partida.
    `seccion_id`/`seccion` son los de la CUENTA; `padre_id`/`padre` los de su sección."""

    linea_id: int
    padre_id: int | None
    padre: str
    codigo_cuenta: str | None
    partidas: list[PartidaSalida]
    consumo: ConsumoSalida | None = None


def _hoja_cuenta_a_salida(h) -> HojaCuentaSalida:  # type: ignore[no-untyped-def]
    return HojaCuentaSalida(
        seccion_id=h.linea_id,
        seccion=h.cuenta,
        periodos=h.periodos,
        cuentas=[
            CuentaHojaSalida(
                linea_id=p.id or 0,
                descripcion=p.concepto,
                codigo=" ".join(
                    f"{p.cantidad.normalize():f} {p.unidad or ''} × {p.costo.normalize():f}".split()
                ),
                estado=p.metodo,
                meses=list(p.meses),
            )
            for p in h.partidas
        ],
        totales=h.totales,
        inflacion=h.inflacion,
        acumulada=h.bloque.acumulada,
        total_con_inflacion=h.bloque.total_con_inflacion,
        est_act=h.est_act,
        budget_previo=h.budget_previo,
        variacion=h.bloque.variacion,
        variacion_pct=h.bloque.variacion_pct,
        origen=h.origen,
        linea_id=h.linea_id,
        padre_id=h.seccion_id,
        padre=h.seccion,
        codigo_cuenta=h.codigo,
        partidas=[
            PartidaSalida(
                id=p.id,
                orden=p.orden,
                concepto=p.concepto,
                cantidad=p.cantidad,
                unidad=p.unidad,
                costo=p.costo,
                metodo=p.metodo,
                extendido=p.extendido,
                meses=list(p.meses),
                suma=p.suma,
                diferencia=p.diferencia,
            )
            for p in h.partidas
        ],
        consumo=(
            ConsumoSalida(
                unidad=h.consumo.unidad,
                **{
                    b: [
                        ConsumoMesSalida(unidades=m[0], costo_unitario=m[1], total=m[2])
                        for m in meses
                    ]
                    for b, meses in h.consumo.bloques.items()
                },
            )
            if h.consumo is not None
            else None
        ),
    )


def _hoja_de_cuenta(db: Session, contexto: ContextoHotel, ciclo_id: int, linea_id: int, ciclo):  # type: ignore[no-untyped-def]
    visibles = lineas_visibles_de(db, contexto, ciclo)
    return leer_hoja_de_cuenta(
        db, hotel_id=contexto.hotel_id, ciclo_id=ciclo_id, linea_id=linea_id, visibles=visibles
    )


def _errores_partidas(e: Exception) -> HTTPException:
    if isinstance(e, LookupError):
        return HTTPException(status_code=404, detail=str(e.args[0]) if e.args else "No encontrado")
    return HTTPException(status_code=e.status_code, detail=e.detalle)  # type: ignore[attr-defined]


@router.get(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas/{linea_id}/hoja",
    response_model=HojaCuentaSalida,
)
def ver_hoja_de_cuenta(
    contexto: Leer, ciclo_id: IdRuta, linea_id: IdRuta, db: Session = Depends(get_db)
) -> HojaCuentaSalida:
    """La hoja de una cuenta por partidas: partidas × 12 meses y el bloque inferior (inflación,
    total
    con inflación —que ES el Budget—, Est Act y Budget del año previo, variación)."""
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    try:
        return _hoja_cuenta_a_salida(_hoja_de_cuenta(db, contexto, ciclo_id, linea_id, ciclo))
    except (LookupError, DetalleInvalido, DistribucionInvalida) as e:
        raise _errores_partidas(e) from None


@router.put(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas/{linea_id}/partidas",
    response_model=HojaCuentaSalida,
)
def guardar_partidas_de_cuenta(
    contexto: Capturar,
    ciclo_id: IdRuta,
    linea_id: IdRuta,
    entrada: PartidasEntrada,
    db: Session = Depends(get_db),
) -> HojaCuentaSalida:
    """Reemplaza **completas** las partidas y la inflación de la cuenta (no es parcial) y deja la
    cuenta mensualizada: Budget del mes = distribución × (1 + inflación)."""
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    _exigir_en_captura(ciclo)
    visibles = lineas_visibles_de(db, contexto, ciclo)
    try:
        guardar_partidas(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            ciclo_id=ciclo_id,
            linea_id=linea_id,
            partidas=[
                PartidaEntrada(
                    concepto=p.concepto,
                    cantidad=p.cantidad,
                    unidad=p.unidad,
                    costo=p.costo,
                    metodo=p.metodo,
                    meses=p.meses,
                )
                for p in entrada.partidas
            ],
            inflacion=entrada.inflacion,
            visibles=visibles,
        )
        hoja = _hoja_de_cuenta(db, contexto, ciclo_id, linea_id, ciclo)
    except (LookupError, DetalleInvalido, DistribucionInvalida) as e:
        raise _errores_partidas(e) from None
    db.commit()
    return _hoja_cuenta_a_salida(hoja)


@router.put(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas/{linea_id}/hoja/inflacion",
    response_model=HojaCuentaSalida,
)
def guardar_inflacion_de_cuenta(
    contexto: Capturar,
    ciclo_id: IdRuta,
    linea_id: IdRuta,
    entrada: InflacionEntrada,
    db: Session = Depends(get_db),
) -> HojaCuentaSalida:
    """Cambia la inflación mensual (12 periodos) conservando las partidas.

    El Budget se recalcula.
    """
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    _exigir_en_captura(ciclo)
    visibles = lineas_visibles_de(db, contexto, ciclo)
    try:
        guardar_inflacion_cuenta(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            ciclo_id=ciclo_id,
            linea_id=linea_id,
            inflacion=entrada.inflacion,
            visibles=visibles,
        )
        hoja = _hoja_de_cuenta(db, contexto, ciclo_id, linea_id, ciclo)
    except (LookupError, DetalleInvalido, DistribucionInvalida) as e:
        raise _errores_partidas(e) from None
    db.commit()
    return _hoja_cuenta_a_salida(hoja)


class ConsumoCambio(BaseModel):
    periodo: Annotated[str, Field(pattern=PATRON_PERIODO)]
    unidades: Annotated[Decimal, Field(allow_inf_nan=False, ge=0, max_digits=18, decimal_places=6)]
    costo_unitario: Annotated[
        Decimal, Field(allow_inf_nan=False, ge=0, max_digits=18, decimal_places=6)
    ]


class ConsumoEntrada(BaseModel):
    meses: list[ConsumoCambio] = Field(min_length=1, max_length=12)


@router.put(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas/{linea_id}/consumo",
    response_model=HojaCuentaSalida,
)
def guardar_consumo_de_cuenta(
    contexto: Capturar,
    ciclo_id: IdRuta,
    linea_id: IdRuta,
    entrada: ConsumoEntrada,
    db: Session = Depends(get_db),
) -> HojaCuentaSalida:
    """Cambia unidades y costo unitario de los meses indicados del Budget de una cuenta de consumo
    (Diesel, Gas, Electricity, Water); el total del mes es unidades × costo y el Budget se
    recalcula."""
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    _exigir_en_captura(ciclo)
    visibles = lineas_visibles_de(db, contexto, ciclo)
    try:
        editar_consumo_budget(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            ciclo_id=ciclo_id,
            linea_id=linea_id,
            cambios={m.periodo: (m.unidades, m.costo_unitario) for m in entrada.meses},
            visibles=visibles,
        )
        hoja = _hoja_de_cuenta(db, contexto, ciclo_id, linea_id, ciclo)
    except (LookupError, DetalleInvalido, DistribucionInvalida) as e:
        raise _errores_partidas(e) from None
    db.commit()
    return _hoja_cuenta_a_salida(hoja)


@router.delete(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas/{linea_id}/consumo",
    status_code=204,
)
def quitar_consumo_de_cuenta(
    contexto: Capturar, ciclo_id: IdRuta, linea_id: IdRuta, db: Session = Depends(get_db)
) -> None:
    """Vuelve la cuenta de consumo al Editor mensual.

    El Budget que tenía queda como detalle fijo.
    """
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    _exigir_en_captura(ciclo)
    visibles = lineas_visibles_de(db, contexto, ciclo)
    try:
        quitar_consumo(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            ciclo_id=ciclo_id,
            linea_id=linea_id,
            visibles=visibles,
        )
    except (LookupError, DetalleInvalido, DistribucionInvalida) as e:
        raise _errores_partidas(e) from None
    db.commit()


@router.post(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas/{linea_id}/partidas/activar",
    response_model=HojaCuentaSalida,
)
def activar_partidas_de_cuenta(
    contexto: Capturar, ciclo_id: IdRuta, linea_id: IdRuta, db: Session = Depends(get_db)
) -> HojaCuentaSalida:
    """Pasa la cuenta a partidas.

    Conserva sus importes actuales como la partida «Importe actual».
    """
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    _exigir_en_captura(ciclo)
    visibles = lineas_visibles_de(db, contexto, ciclo)
    try:
        activar_partidas(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            ciclo_id=ciclo_id,
            linea_id=linea_id,
            visibles=visibles,
        )
        hoja = _hoja_de_cuenta(db, contexto, ciclo_id, linea_id, ciclo)
    except (LookupError, DetalleInvalido, DistribucionInvalida) as e:
        raise _errores_partidas(e) from None
    db.commit()
    return _hoja_cuenta_a_salida(hoja)


@router.delete(
    "/hoteles/{hotel_id}/presupuesto/ciclos/{ciclo_id}/lineas/{linea_id}/partidas",
    status_code=204,
)
def quitar_partidas_de_cuenta(
    contexto: Capturar, ciclo_id: IdRuta, linea_id: IdRuta, db: Session = Depends(get_db)
) -> None:
    """Vuelve la cuenta al Editor mensual; el Budget que ya tenía queda como detalle fijo."""
    ciclo = _ciclo_o_404(db, contexto.hotel_id, ciclo_id)
    _exigir_en_captura(ciclo)
    visibles = lineas_visibles_de(db, contexto, ciclo)
    try:
        quitar_partidas(
            db,
            organizacion_id=contexto.organizacion_id,
            hotel_id=contexto.hotel_id,
            usuario_id=contexto.principal.usuario_id,
            ciclo_id=ciclo_id,
            linea_id=linea_id,
            visibles=visibles,
        )
    except (LookupError, DetalleInvalido, DistribucionInvalida) as e:
        raise _errores_partidas(e) from None
    db.commit()
