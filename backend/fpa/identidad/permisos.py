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
        }
    ),
    RolCodigo.RESPONSABLE_AREA: frozenset({Permiso.HOTEL_LEER, Permiso.CATALOGO_LEER}),
    RolCodigo.DIRECCION: frozenset(
        {Permiso.HOTEL_LEER, Permiso.CARGA_LEER, Permiso.CATALOGO_LEER, Permiso.SALDOS_LEER}
    ),
    RolCodigo.AUDITORIA: frozenset(
        {
            Permiso.HOTEL_LEER,
            Permiso.CARGA_LEER,
            Permiso.CATALOGO_LEER,
            Permiso.SALDOS_LEER,
            Permiso.AUDITORIA_LEER,
        }
    ),
}


def rol_tiene_permiso(rol: str, permiso: Permiso) -> bool:
    return permiso in PERMISOS_POR_ROL.get(rol, frozenset())
