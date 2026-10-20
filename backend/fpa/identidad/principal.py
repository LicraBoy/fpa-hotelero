from dataclasses import dataclass, field

from fpa.identidad.permisos import ROLES_POR_SECCION, Permiso, rol_tiene_permiso


@dataclass(frozen=True)
class Principal:
    """Quién hace la petición y qué rol tiene en cada hotel al que tiene acceso."""

    usuario_id: int
    email: str
    organizacion_id: int
    roles_por_hotel: dict[int, str]
    # hotel -> secciones del reporte asignadas (solo importan a los roles por sección)
    secciones_por_hotel: dict[int, frozenset[str]] = field(default_factory=dict)

    def tiene_acceso_a(self, hotel_id: int) -> bool:
        return hotel_id in self.roles_por_hotel

    def puede(self, hotel_id: int, permiso: Permiso) -> bool:
        rol = self.roles_por_hotel.get(hotel_id)
        return rol is not None and rol_tiene_permiso(rol, permiso)

    def secciones_permitidas(self, hotel_id: int) -> frozenset[str] | None:
        """`None` = sin restricción; si no, las únicas secciones (por nombre) que puede ver."""
        if self.roles_por_hotel.get(hotel_id) not in ROLES_POR_SECCION:
            return None
        return self.secciones_por_hotel.get(hotel_id, frozenset())
