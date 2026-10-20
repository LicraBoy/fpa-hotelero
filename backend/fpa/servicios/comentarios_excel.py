"""Texto de los comentarios para las columnas COMMENTS y YTD COMMENTS del Excel exportado."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from fpa.modelos.comentarios import ComentarioLinea
from fpa.modelos.identidad import Usuario

ETIQUETA = {"pendiente": "Pendiente", "explicado": "Explicado", "aprobado": "Aprobado"}
MAX_CELDA = 32_000  # Excel admite 32 767 caracteres por celda


def comentarios_por_linea(db: Session, hotel_id: int, periodo: str) -> dict[tuple[int, str], str]:
    """`(linea_id, bloque)` -> un texto con los hilos de esa línea (una línea por hilo)."""
    raices = list(
        db.scalars(
            select(ComentarioLinea)
            .where(
                ComentarioLinea.hotel_id == hotel_id,
                ComentarioLinea.periodo == periodo,
                ComentarioLinea.padre_id.is_(None),
            )
            .order_by(ComentarioLinea.creado_en, ComentarioLinea.id)
        )
    )
    if not raices:
        return {}
    autores = {
        u.id: u.nombre
        for u in db.scalars(select(Usuario).where(Usuario.id.in_({r.autor_id for r in raices})))
    }
    salida: dict[tuple[int, str], list[str]] = {}
    for r in raices:
        estatus = ETIQUETA.get(r.estatus or "pendiente", "Pendiente")
        linea = f"[{estatus}] {r.texto} — {autores.get(r.autor_id, '')}"
        salida.setdefault((r.linea_id, r.bloque), []).append(linea)
    return {clave: "\n".join(v)[:MAX_CELDA] for clave, v in salida.items()}
