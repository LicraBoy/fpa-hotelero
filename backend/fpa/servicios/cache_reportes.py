"""Caché en memoria de reportes (Fase 4.7).

Qué se guarda: el Variance de un periodo, ya calculado y serializado. Se pide muchas veces (cada
pantalla, cada filtro, cada exportación) y solo cambia cuando cambian sus insumos.

**Clave:** `(organización, hotel, versión de mapeo pedida, versión de Budget pedida, periodo, mes de
inicio del año fiscal, generación del hotel)`. Dos organizaciones u hoteles nunca comparten entrada.

**Invalidación por generación:** cada hotel tiene un contador. Cualquier escritura exitosa en la API
del hotel (cargar un archivo, aprobar o editar el mapeo, importar estructura o Budget…) lo sube, y
las entradas viejas dejan de ser alcanzables (se barren por LRU y por tiempo). Es más robusto que
invalidar a mano en cada servicio: una ruta nueva que escriba invalida sola. Un contador por proceso
con una **época aleatoria**: tras reiniciar el servidor no se puede confundir con uno anterior.

**Límites (decisión pendiente de TI):** vive en la memoria de UN proceso. Con varios procesos o
servidores cada uno tendría su caché y una escritura solo invalidaría la suya; ahí hace falta Redis
(`docs/CAMBIOS_FUTUROS_DE_TECNOLOGIA.md`) o poner `FPA_CACHE_REPORTES_TTL_S=0` para apagarla. El
vencimiento por tiempo (5 min) acota cualquier desfase, incluida una carga hecha por otro proceso
(p. ej. el script de demostración).
"""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

# (organización, hotel, mapeo, Budget, periodo, mes de inicio del año fiscal, época:generación)
ClaveReporte = tuple[int, int, int | None, int | None, str, int, str]


@dataclass
class _Entrada[T]:
    valor: T
    vence: float


class CacheReportes[T]:
    def __init__(
        self,
        ttl_segundos: float = 300.0,
        max_entradas: int = 128,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_segundos
        self._max = max_entradas
        self._reloj = reloj
        self._entradas: OrderedDict[Hashable, _Entrada[T]] = OrderedDict()
        self._generaciones: dict[int, int] = {}
        self._epoca = secrets.token_hex(4)
        self._candado = threading.Lock()
        self.aciertos = 0
        self.fallos = 0

    @property
    def activa(self) -> bool:
        return self._ttl > 0

    def clave(
        self,
        *,
        organizacion_id: int,
        hotel_id: int,
        version_mapeo_id: int | None,
        version_plan_id: int | None,
        periodo: str,
        mes_inicio: int = 7,
    ) -> ClaveReporte:
        with self._candado:
            generacion = self._generaciones.get(hotel_id, 0)
        return (
            organizacion_id,
            hotel_id,
            version_mapeo_id,
            version_plan_id,
            periodo,
            mes_inicio,
            f"{self._epoca}:{generacion}",
        )

    def obtener(self, clave: Hashable) -> T | None:
        if not self.activa:
            return None
        with self._candado:
            entrada = self._entradas.get(clave)
            if entrada is None or entrada.vence <= self._reloj():
                if entrada is not None:
                    del self._entradas[clave]
                self.fallos += 1
                return None
            self._entradas.move_to_end(clave)
            self.aciertos += 1
            return entrada.valor

    def guardar(self, clave: Hashable, valor: T) -> None:
        if not self.activa:
            return
        with self._candado:
            self._entradas[clave] = _Entrada(valor, self._reloj() + self._ttl)
            self._entradas.move_to_end(clave)
            while len(self._entradas) > self._max:
                self._entradas.popitem(last=False)

    def invalidar_hotel(self, hotel_id: int) -> None:
        """Sube la generación del hotel: sus entradas anteriores ya no se encuentran."""
        with self._candado:
            self._generaciones[hotel_id] = self._generaciones.get(hotel_id, 0) + 1

    def limpiar(self) -> None:
        with self._candado:
            self._entradas.clear()
            self.aciertos = 0
            self.fallos = 0

    def __len__(self) -> int:
        with self._candado:
            return len(self._entradas)
