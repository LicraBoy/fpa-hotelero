"""Matriz de roles y permisos (deny by default: lo que no está aquí, no se puede hacer)."""

from enum import StrEnum


class Permiso(StrEnum):
    HOTEL_LEER = "hotel:leer"
    CARGA_CREAR = "carga:crear"
    CARGA_LEER = "carga:leer"
    CATALOGO_LEER = "catalogo:leer"
    CATALOGO_IMPORTAR = "catalogo:importar"
    SALDOS_LEER = "saldos:leer"
    AUDITORIA_LEER = "auditoria:leer"
    REPORTE_LEER = "reporte:leer"
    MAPEO_LEER = "mapeo:leer"
    MAPEO_EDITAR = "mapeo:editar"
    MAPEO_APROBAR = "mapeo:aprobar"
    BUDGET_LEER = "budget:leer"
    BUDGET_IMPORTAR = "budget:importar"
    BUDGET_CAPTURAR = "budget:capturar"
    BUDGET_OBJETIVO = "budget:objetivo"
    BUDGET_REVISAR = "budget:revisar"
    BUDGET_APROBAR = "budget:aprobar"
    BUDGET_BLOQUEAR = "budget:bloquear"
    VARIANCE_LEER = "variance:leer"
    DRILLDOWN_LEER = "drilldown:leer"
    USUARIOS_ADMINISTRAR = "usuarios:administrar"
    COMENTARIO_LEER = "comentario:leer"
    COMENTARIO_CREAR = "comentario:crear"
    COMENTARIO_RESOLVER = "comentario:resolver"
    CIERRE_LEER = "cierre:leer"
    CIERRE_REVISAR = "cierre:revisar"
    CIERRE_APROBAR = "cierre:aprobar"
    CIERRE_BLOQUEAR = "cierre:bloquear"


class RolCodigo(StrEnum):
    CONTRALOR = "contralor"
    ANALISTA = "analista"
    RESPONSABLE_AREA = "responsable_area"
    DIRECCION = "direccion"
    AUDITORIA = "auditoria"


NOMBRES_ROL = {
    RolCodigo.CONTRALOR: "Contralor",
    RolCodigo.ANALISTA: "Analista de Contraloría",
    RolCodigo.RESPONSABLE_AREA: "Responsable de departamento",
    RolCodigo.DIRECCION: "Dirección",
    RolCodigo.AUDITORIA: "Auditoría / consulta",
}

# [POR VALIDAR con Contraloría] Roles propuestos en el Blueprint §30.
PERMISOS_POR_ROL: dict[str, frozenset[Permiso]] = {
    RolCodigo.CONTRALOR: frozenset(Permiso),
    RolCodigo.ANALISTA: frozenset(
        {
            Permiso.HOTEL_LEER,
            Permiso.CARGA_CREAR,
            Permiso.CARGA_LEER,
            Permiso.CATALOGO_LEER,
            Permiso.CATALOGO_IMPORTAR,
            Permiso.SALDOS_LEER,
            Permiso.REPORTE_LEER,
            Permiso.MAPEO_LEER,
            Permiso.MAPEO_EDITAR,
            Permiso.BUDGET_LEER,
            Permiso.BUDGET_IMPORTAR,
            Permiso.VARIANCE_LEER,
            Permiso.DRILLDOWN_LEER,
            Permiso.COMENTARIO_LEER,
            Permiso.COMENTARIO_CREAR,
            Permiso.COMENTARIO_RESOLVER,
            Permiso.CIERRE_LEER,
            Permiso.CIERRE_REVISAR,
            Permiso.BUDGET_REVISAR,
        }
    ),
    # Ve y comenta solo las secciones del Variance que tiene asignadas (`AsignacionDepartamento`);
    # BUDGET_CAPTURAR lo restringe igual, por sección, cuando la Fase 7.2 añada esa resolución.
    RolCodigo.RESPONSABLE_AREA: frozenset(
        {
            Permiso.HOTEL_LEER,
            Permiso.CATALOGO_LEER,
            Permiso.REPORTE_LEER,
            Permiso.VARIANCE_LEER,
            Permiso.DRILLDOWN_LEER,
            Permiso.COMENTARIO_LEER,
            Permiso.COMENTARIO_CREAR,
            Permiso.BUDGET_CAPTURAR,
        }
    ),
    RolCodigo.DIRECCION: frozenset(
        {
            Permiso.HOTEL_LEER,
            Permiso.CARGA_LEER,
            Permiso.CATALOGO_LEER,
            Permiso.SALDOS_LEER,
            Permiso.REPORTE_LEER,
            Permiso.MAPEO_LEER,
            Permiso.BUDGET_LEER,
            Permiso.VARIANCE_LEER,
            Permiso.COMENTARIO_LEER,
            Permiso.CIERRE_LEER,
            Permiso.BUDGET_OBJETIVO,
        }
    ),
    RolCodigo.AUDITORIA: frozenset(
        {
            Permiso.HOTEL_LEER,
            Permiso.CARGA_LEER,
            Permiso.CATALOGO_LEER,
            Permiso.SALDOS_LEER,
            Permiso.AUDITORIA_LEER,
            Permiso.REPORTE_LEER,
            Permiso.MAPEO_LEER,
            Permiso.BUDGET_LEER,
            Permiso.VARIANCE_LEER,
            Permiso.DRILLDOWN_LEER,
            Permiso.COMENTARIO_LEER,
            Permiso.CIERRE_LEER,
        }
    ),
}

# Roles que solo ven las secciones del reporte que se les asignaron.
ROLES_POR_SECCION = frozenset({RolCodigo.RESPONSABLE_AREA})


def rol_tiene_permiso(rol: str, permiso: Permiso) -> bool:
    return permiso in PERMISOS_POR_ROL.get(rol, frozenset())
