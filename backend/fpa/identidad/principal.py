from dataclasses import dataclass

from fpa.identidad.permisos import Permiso, rol_tiene_permiso


@dataclass(frozen=True)
class Principal:
    """Quién hace la petición y qué rol tiene en cada hotel al que tiene acceso."""

    usuario_id: int
    email: str
    organizacion_id: int
    roles_por_hotel: dict[int, str]

    def tiene_acceso_a(self, hotel_id: int) -> bool:
        return hotel_id in self.roles_por_hotel

    def puede(self, hotel_id: int, permiso: Permiso) -> bool:
        rol = self.roles_por_hotel.get(hotel_id)
        return rol is not None and rol_tiene_permiso(rol, permiso)
