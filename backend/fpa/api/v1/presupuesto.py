"""Captura por área del Budget (Fase 7.2): líneas del ciclo, captura de propuesta y mensualización.

Reglas de acceso (ADR 0003): sin sesión 401; hotel ajeno 404; sin permiso 403. Un responsable de
departamento solo ve y captura las líneas de las secciones que tiene asignadas
(`AsignacionDepartamento`) — lo que queda fuera responde 404, igual que en Comentarios.
"""

import re
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.api.v1.respuestas import RESPUESTAS_HOTEL
from fpa.api.v1.tipos import ID_MAX, FechaHoraUtc, IdConsulta, IdRuta
from fpa.db import get_db
from fpa.identidad.dependencias import ContextoHotel, hotel_autorizado, principal_actual
from fpa.identidad.permisos import Permiso
from fpa.identidad.principal import Principal
from fpa.modelos.identidad import Usuario
from fpa.modelos.presupuesto import (
    AnoFiscal,
    CicloPresupuesto,
    LineaPresupuestoCaptura,
    PerfilDistribucion,
    PeriodoFiscal,
)
from fpa.modelos.reporte import LineaReporte
from fpa.repositorios.reporte import RepositorioReporte
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
from fpa.servicios.presupuesto_distribucion import (
    DistribucionInvalida,
    fijar_importes_mensuales,
    prorratear_con_perfil,
    sembrar_perfiles_sistema,
)

router = APIRouter(tags=["presupuesto"], responses=RESPUESTAS_HOTEL)


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


@router.post(
    "/hoteles/{hotel_id}/presupuesto/ciclos", response_model=CicloSalida, status_code=201
)
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
def detalle_ciclo(
    contexto: Leer, ciclo_id: IdRuta, db: Session = Depends(get_db)
) -> CicloSalida:
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
