"""Ciclo de captura del Budget (Fase 7.1/7.4, `docs/DISENO_FASE7_BUDGET.md`).

    Borrador → Enviado → Revisión → Aprobado → Bloqueado

«Devolver» regresa de Enviado o Revisión a Borrador y «Reabrir» de Aprobado a Borrador; ambas piden
nota. Al **aprobar** se genera una `VersionPlan` normal (Fase 7.4) — igual que hoy la produce un
import de Excel, reusando `fpa.servicios.budget.importar_budget_mensual` — a partir de las
`LineaPresupuestoCaptura` con `propuesta_anual` capturada; todas deben estar ya mensualizadas
(Fase 7.3) o la aprobación se rechaza (si no, su cifra anual se perdería: `importar_budget_mensual`
solo registra una línea que trae al menos un mes). Aprobar una segunda vez (tras reabrir y volver a
capturar) genera otra versión y deja la anterior como `reemplazada` — nunca se edita una ya creada.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fpa.calculo.ano_fiscal import periodos_del_ano_fiscal
from fpa.identidad.permisos import Permiso
from fpa.ingesta.variance_mzt import ValoresMes
from fpa.modelos.base import ahora_utc
from fpa.modelos.plan import VersionPlan
from fpa.modelos.presupuesto import (
    AnoFiscal,
    CicloPresupuesto,
    CicloTransicion,
    LineaPresupuestoCaptura,
    LineaPresupuestoMensual,
    PeriodoFiscal,
)
from fpa.repositorios.reporte import RepositorioReporte
from fpa.servicios.auditoria import auditar
from fpa.servicios.budget import importar_budget_mensual
from fpa.servicios.cargar_archivo import Resolucion
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.presupuesto_captura import inicializar_capturas

_PATRON_PERIODO = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


@dataclass(frozen=True)
class Transicion:
    desde: str
    hacia: str
    permiso: Permiso
    etiqueta: str
    pide_nota: bool = False


TRANSICIONES: tuple[Transicion, ...] = (
    Transicion("borrador", "enviado", Permiso.BUDGET_CAPTURAR, "Enviar a revisión"),
    Transicion("enviado", "revision", Permiso.BUDGET_REVISAR, "Marcar como revisado"),
    Transicion("enviado", "borrador", Permiso.BUDGET_REVISAR, "Devolver a borrador", True),
    Transicion("revision", "borrador", Permiso.BUDGET_REVISAR, "Devolver a borrador", True),
    Transicion("revision", "aprobado", Permiso.BUDGET_APROBAR, "Aprobar"),
    Transicion("aprobado", "bloqueado", Permiso.BUDGET_BLOQUEAR, "Bloquear"),
    Transicion("aprobado", "borrador", Permiso.BUDGET_APROBAR, "Reabrir", True),
)


class CicloInvalido(Exception):
    """Transición no permitida o datos que la impiden. Lleva el código HTTP que corresponde."""

    def __init__(self, status_code: int, detalle: str) -> None:
        super().__init__(detalle)
        self.status_code = status_code
        self.detalle = detalle


def transicion_de(desde: str, hacia: str) -> Transicion | None:
    return next((t for t in TRANSICIONES if t.desde == desde and t.hacia == hacia), None)


def _validar_periodo(periodo: str) -> None:
    if not _PATRON_PERIODO.match(periodo):
        raise CicloInvalido(422, "El periodo debe tener el formato AAAA-MM")


def crear_ano_fiscal(
    db: Session, *, hotel_id: int, etiqueta: str, mes_inicio: int, mes_fin: int
) -> AnoFiscal:
    if not (1 <= mes_inicio <= 12) or not (1 <= mes_fin <= 12):
        raise CicloInvalido(422, "El mes de inicio y de fin deben estar entre 1 y 12")
    existente = db.scalar(
        select(AnoFiscal).where(AnoFiscal.hotel_id == hotel_id, AnoFiscal.etiqueta == etiqueta)
    )
    if existente is not None:
        raise CicloInvalido(409, f"Ya existe el año fiscal «{etiqueta}» para este hotel")
    ano = AnoFiscal(
        hotel_id=hotel_id,
        etiqueta=etiqueta,
        mes_inicio=mes_inicio,
        mes_fin=mes_fin,
        estado="abierto",
    )
    db.add(ano)
    db.flush()
    return ano


def crear_periodo_fiscal(db: Session, *, ano_fiscal_id: int, periodo: str) -> PeriodoFiscal:
    _validar_periodo(periodo)
    ano = db.get(AnoFiscal, ano_fiscal_id)
    if ano is None:
        raise LookupError("Año fiscal no encontrado")
    existente = db.scalar(
        select(PeriodoFiscal).where(
            PeriodoFiscal.ano_fiscal_id == ano_fiscal_id, PeriodoFiscal.periodo == periodo
        )
    )
    if existente is not None:
        raise CicloInvalido(409, f"El periodo {periodo} ya existe en este año fiscal")
    pf = PeriodoFiscal(ano_fiscal_id=ano_fiscal_id, periodo=periodo, estado="abierto")
    db.add(pf)
    db.flush()
    return pf


def generar_periodos_fiscales(db: Session, *, ano_fiscal_id: int) -> list[PeriodoFiscal]:
    """Crea los 12 `PeriodoFiscal` del año (idempotente: los que ya existen no se duplican)."""
    ano = db.get(AnoFiscal, ano_fiscal_id)
    if ano is None:
        raise LookupError("Año fiscal no encontrado")
    anio_inicio = int(ano.etiqueta[:4])
    periodos = periodos_del_ano_fiscal(f"{anio_inicio:04d}-{ano.mes_inicio:02d}", ano.mes_inicio)
    existentes = {
        p.periodo: p
        for p in db.scalars(
            select(PeriodoFiscal).where(PeriodoFiscal.ano_fiscal_id == ano_fiscal_id)
        )
    }
    salida = []
    for periodo in periodos:
        if periodo in existentes:
            salida.append(existentes[periodo])
        else:
            pf = PeriodoFiscal(ano_fiscal_id=ano_fiscal_id, periodo=periodo, estado="abierto")
            db.add(pf)
            salida.append(pf)
    db.flush()
    return salida


def ciclo_de(db: Session, hotel_id: int, ciclo_id: int) -> CicloPresupuesto | None:
    return db.scalar(
        select(CicloPresupuesto).where(
            CicloPresupuesto.id == ciclo_id, CicloPresupuesto.hotel_id == hotel_id
        )
    )


def historial(db: Session, ciclo: CicloPresupuesto | None) -> list[CicloTransicion]:
    if ciclo is None:
        return []
    return list(
        db.scalars(
            select(CicloTransicion)
            .where(CicloTransicion.ciclo_id == ciclo.id)
            .order_by(CicloTransicion.id)
        )
    )


def crear_ciclo(
    db: Session, *, organizacion_id: int, hotel_id: int, usuario_id: int | None, ano_fiscal_id: int
) -> CicloPresupuesto:
    """Abre un ciclo de captura en `borrador` para un año fiscal.

    Rechaza si ya hay uno abierto (no `bloqueado`) para ese año fiscal — un año fiscal se
    presupuesta con un solo ciclo vivo a la vez, igual que un mapeo solo admite un borrador abierto.
    """
    ano = db.get(AnoFiscal, ano_fiscal_id)
    if ano is None or ano.hotel_id != hotel_id:
        raise LookupError("Año fiscal no encontrado")
    estructura = RepositorioReporte(db, hotel_id).vigente()
    if estructura is None:
        raise CicloInvalido(409, "No hay una estructura de reporte vigente para este hotel")
    abierto = db.scalar(
        select(CicloPresupuesto).where(
            CicloPresupuesto.hotel_id == hotel_id,
            CicloPresupuesto.ano_fiscal_id == ano_fiscal_id,
            CicloPresupuesto.estado != "bloqueado",
        )
    )
    if abierto is not None:
        raise CicloInvalido(
            409, "Ya hay un ciclo de presupuesto abierto para este año fiscal; bloquéalo antes"
        )
    numero = (
        db.scalar(
            select(CicloPresupuesto.numero)
            .where(
                CicloPresupuesto.hotel_id == hotel_id,
                CicloPresupuesto.ano_fiscal_id == ano_fiscal_id,
            )
            .order_by(CicloPresupuesto.numero.desc())
        )
        or 0
    ) + 1
    ciclo = CicloPresupuesto(
        hotel_id=hotel_id,
        ano_fiscal_id=ano_fiscal_id,
        numero=numero,
        estado="borrador",
        version_estructura_id=estructura.id,
        creado_por_id=usuario_id,
        creado_en=ahora_utc(),
    )
    db.add(ciclo)
    db.flush()
    inicializar_capturas(db, ciclo=ciclo)
    auditar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion="presupuesto.ciclo_creado",
        entidad="ciclo_presupuesto",
        entidad_id=ciclo.id,
        detalle={"ano_fiscal_id": ano_fiscal_id, "numero": numero},
    )
    return ciclo


def _lineas_capturadas_sin_mensualizar(db: Session, ciclo: CicloPresupuesto) -> list[int]:
    """`linea_id` de las capturas con `propuesta_anual` que todavía no tienen su reparto mensual.

    `importar_budget_mensual` solo guarda una línea con al menos un mes: una capturada pero sin
    mensualizar perdería su cifra anual en silencio, así que aprobar con alguna así se rechaza.
    """
    capturas = db.scalars(
        select(LineaPresupuestoCaptura).where(
            LineaPresupuestoCaptura.ciclo_id == ciclo.id,
            LineaPresupuestoCaptura.propuesta_anual.is_not(None),
        )
    )
    faltan = []
    for c in capturas:
        n = db.scalar(
            select(func.count())
            .select_from(LineaPresupuestoMensual)
            .where(LineaPresupuestoMensual.linea_captura_id == c.id)
        )
        if not n:
            faltan.append(c.linea_id)
    return faltan


def _generar_version_plan(
    db: Session, ciclo: CicloPresupuesto, *, organizacion_id: int, usuario_id: int | None
) -> VersionPlan:
    """Genera la `VersionPlan` del ciclo aprobado, igual que la produciría un import de Excel."""
    ano = db.get(AnoFiscal, ciclo.ano_fiscal_id)
    if ano is None:
        raise CicloInvalido(409, "El año fiscal del ciclo no existe")
    if ciclo.version_estructura_id is None:
        raise CicloInvalido(409, "El ciclo no tiene una estructura de reporte asociada")
    repo_reporte = RepositorioReporte(db, ciclo.hotel_id)
    estructura = repo_reporte.obtener(ciclo.version_estructura_id)
    if estructura is None:
        raise CicloInvalido(409, "La estructura de reporte del ciclo ya no existe")
    lineas_por_id = {x.id: x for x in repo_reporte.lineas(ciclo.version_estructura_id)}
    capturas = list(
        db.scalars(
            select(LineaPresupuestoCaptura).where(
                LineaPresupuestoCaptura.ciclo_id == ciclo.id,
                LineaPresupuestoCaptura.propuesta_anual.is_not(None),
            )
        )
    )
    por_periodo: dict[str, dict[int, ValoresMes]] = {}
    anual: dict[int, Decimal] = {}
    for c in capturas:
        linea = lineas_por_id.get(c.linea_id)
        if linea is None or c.propuesta_anual is None:
            continue
        anual[linea.fila_origen] = c.propuesta_anual
        mensuales = db.scalars(
            select(LineaPresupuestoMensual).where(
                LineaPresupuestoMensual.linea_captura_id == c.id
            )
        )
        for m in mensuales:
            por_periodo.setdefault(m.periodo, {})[linea.fila_origen] = ValoresMes(
                linea.fila_origen, budget=m.importe
            )
    canonico = json.dumps(
        {
            "ciclo_id": ciclo.id,
            "numero": ciclo.numero,
            "anual": {str(k): str(v) for k, v in sorted(anual.items())},
        },
        sort_keys=True,
    ).encode()
    sha = hashlib.sha256(canonico).hexdigest()
    resultado = importar_budget_mensual(
        db,
        organizacion_id=organizacion_id,
        hotel_id=ciclo.hotel_id,
        usuario_id=usuario_id,
        version_estructura=estructura,
        por_periodo=por_periodo,
        archivo=DatosArchivo(
            nombre=f"Ciclo de presupuesto {ciclo.numero}", sha256=sha, tamano_bytes=len(canonico)
        ),
        ano_fiscal=ano.etiqueta,
        mes_inicio=ano.mes_inicio,
        anual=anual,
        confirmar_reemplazo=True,
        accion_creado="presupuesto.aprobado",
    )
    if resultado.resolucion == Resolucion.RECHAZADA or resultado.version is None:
        motivo = "; ".join(resultado.motivos) or "No se pudo generar el Budget del ciclo"
        raise CicloInvalido(409, motivo)
    ciclo.version_plan_resultante_id = resultado.version.id
    ciclo.aprobado_en = ahora_utc()
    return resultado.version


def transicionar(
    db: Session,
    *,
    organizacion_id: int,
    hotel_id: int,
    usuario_id: int,
    puede: dict[Permiso, bool] | None,
    ciclo_id: int,
    hacia: str,
    nota: str | None,
) -> CicloPresupuesto:
    """Aplica una transición del ciclo. `CicloInvalido` si no existe, falta permiso o nota."""
    ciclo = ciclo_de(db, hotel_id, ciclo_id)
    if ciclo is None:
        raise CicloInvalido(404, "Ciclo de presupuesto no encontrado")
    desde = ciclo.estado
    t = transicion_de(desde, hacia)
    if t is None:
        raise CicloInvalido(409, f"No se puede pasar de «{desde}» a «{hacia}»")
    if puede is not None and not puede.get(t.permiso, False):
        raise CicloInvalido(403, "Tu rol no puede hacer este cambio de estado")
    nota = (nota or "").strip() or None
    if t.pide_nota and nota is None:
        raise CicloInvalido(422, "Escribe el motivo: es obligatorio para este cambio")
    if nota is not None and len(nota) > 1000:
        raise CicloInvalido(422, "La nota admite hasta 1000 caracteres")
    if hacia == "aprobado":
        faltan = _lineas_capturadas_sin_mensualizar(db, ciclo)
        if faltan:
            raise CicloInvalido(
                409,
                f"Faltan mensualizar {len(faltan)} línea(s) capturadas antes de aprobar "
                f"(linea_id: {faltan[:10]})",
            )
    ahora = ahora_utc()
    if hacia == "aprobado":
        _generar_version_plan(db, ciclo, organizacion_id=organizacion_id, usuario_id=usuario_id)
    ciclo.estado = hacia
    db.add(
        CicloTransicion(
            ciclo_id=ciclo.id,
            desde=desde,
            hacia=hacia,
            usuario_id=usuario_id,
            nota=nota,
            creado_en=ahora,
        )
    )
    auditar(
        db,
        organizacion_id=organizacion_id,
        hotel_id=hotel_id,
        usuario_id=usuario_id,
        accion=f"presupuesto.{hacia}",
        entidad="ciclo_presupuesto",
        entidad_id=ciclo.id,
        detalle={
            "desde": desde,
            "hacia": hacia,
            "nota": nota,
            **(
                {"version_plan_resultante_id": ciclo.version_plan_resultante_id}
                if hacia == "aprobado"
                else {}
            ),
        },
    )
    return ciclo
