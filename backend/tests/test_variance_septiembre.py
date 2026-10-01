"""Septiembre 2026: segunda prueba del motor (3.7).

Hoy solo existe el CON130 de septiembre; **no** hay Variance ni Budget de septiembre de
Contraloría, así que todavía no hay contra qué comparar cifra por cifra. Lo que sí se prueba:
- el motor calcula septiembre y su acumulado julio–septiembre sin tocar el mapeo de agosto;
- el acumulado es exactamente el de agosto más el mes de septiembre, línea por línea;
- el Budget de septiembre no se inventa (solo está el anual) y se avisa;
- la validación del mapeo destapa las cuentas nuevas de septiembre que agosto no conoce.

`test_septiembre_contra_el_excel_de_contraloria` es el arnés de la "diferencia cero": se activa
solo cuando `FPA_DATOS_REALES` trae el Variance de septiembre (un `*Variance*Sept*.xlsx`).
"""

from decimal import Decimal

import pytest
from real_agosto import CARPETA, CON130, AgostoReal, agosto_real  # noqa: F401
from test_variance_dorada import BLOQUES, _igual

from fpa.ingesta.novohit_con130 import leer_con130
from fpa.ingesta.variance_valores import leer_variance_valores
from fpa.servicios.cargar_archivo import Resolucion, cargar_archivo
from fpa.servicios.cargas import DatosArchivo
from fpa.servicios.validacion_mapeo import validar_mapeo
from fpa.servicios.variance import calcular_variance

D = Decimal
pytestmark = pytest.mark.skipif(not CON130.exists(), reason="No está el CON130 de septiembre")


@pytest.fixture(scope="module")
def septiembre(agosto_real: AgostoReal) -> AgostoReal:  # noqa: F811
    a = agosto_real
    res = cargar_archivo(
        a.db,
        organizacion_id=a.organizacion_id,
        hotel_id=a.hotel_id,
        usuario_id=None,
        resultado=leer_con130(CON130),
        archivo=DatosArchivo(nombre=CON130.name, sha256="s" * 64),
    )
    assert res.resolucion is Resolucion.CREADA
    a.db.commit()
    return a


def _variance(a: AgostoReal, periodo: str):  # type: ignore[no-untyped-def]
    return calcular_variance(
        a.db, hotel_id=a.hotel_id, periodo=periodo, version_mapeo_id=a.version_mapeo_id
    )


def test_el_acumulado_de_septiembre_es_agosto_mas_el_mes(septiembre: AgostoReal) -> None:
    a = septiembre
    agosto, sept = _variance(a, "2026-08"), _variance(a, "2026-09")
    assert sept.periodos_ytd == ["2026-07", "2026-08", "2026-09"] and sept.periodos_sin_datos == []
    revisadas = 0
    for linea in sept.lineas:
        if linea.id in a.reglas:
            continue  # los totales se verifican por sus partes
        revisadas += 1
        esperado = agosto.resultado[linea.id].ytd.actual + sept.resultado[linea.id].mes.actual
        assert sept.resultado[linea.id].ytd.actual == esperado, linea.descripcion
    assert revisadas > 400


def test_el_budget_de_septiembre_no_se_inventa(septiembre: AgostoReal) -> None:
    sept = _variance(septiembre, "2026-09")
    assert any("solo el anual" in x for x in sept.advertencias)
    for linea in sept.lineas:
        c = sept.resultado[linea.id]
        assert c.mes.budget is None and c.mes.var is None and c.mes.pct is None
        assert c.ytd.budget is None and c.ytd.var is None
    con_anual = [x for x in sept.lineas if sept.resultado[x.id].anual.budget is not None]
    assert len(con_anual) > 400  # el Budget anual sí es del año fiscal completo


def test_agosto_no_cambia_al_cargar_septiembre(septiembre: AgostoReal) -> None:
    a = septiembre
    agosto = _variance(a, "2026-08")
    sueldos = agosto.resultado[a.por_fila[29].id]
    assert sueldos.mes.actual == D("321190.84") and sueldos.ytd.actual == D("625928.70")


def test_la_validacion_destapa_las_cuentas_nuevas_de_septiembre(septiembre: AgostoReal) -> None:
    a = septiembre
    v = validar_mapeo(
        a.db, hotel_id=a.hotel_id, version_mapeo_id=a.version_mapeo_id, periodo="2026-09"
    )
    sin_mapear = {c.cuenta_codigo: c.neto for c in v.sin_mapear}
    # Hallazgo: el mapeo de agosto no conoce 154 cuentas con movimiento en septiembre
    # (cuentas nuevas como 4001006.x y 4003001.010, un ingreso de ~4.6 millones). Hay que
    # extender el mapeo con Contraloría antes de calcular septiembre en serio.
    assert len(sin_mapear) == 154 and "4003001.010" in sin_mapear
    assert not v.aprobable


# --- Arnés: la prueba de "diferencia cero" para cuando exista el Variance de septiembre ---------

SEPTIEMBRE = next(iter(sorted(CARPETA.glob("*Variance*Sep*.xlsx"))), None)


@pytest.mark.skipif(SEPTIEMBRE is None, reason="Falta el Variance de septiembre de Contraloría")
def test_septiembre_contra_el_excel_de_contraloria(septiembre: AgostoReal) -> None:
    assert SEPTIEMBRE is not None
    a = septiembre
    esperado = leer_variance_valores(SEPTIEMBRE)
    r = _variance(a, "2026-09")
    # Con el Budget de septiembre importado también habría que comparar Budget, Var y %; aquí se
    # compara el Actual (mes, YTD y anual). Las diferencias que se expliquen se documentan como
    # excepciones con su causa, igual que en `test_variance_dorada.py`.
    diferencias: dict[int, list[str]] = {}
    for linea in r.lineas:
        valores = esperado.get(linea.fila_origen)
        if valores is None:
            continue
        for bloque, campos in BLOQUES.items():
            cifras = getattr(r.resultado[linea.id], bloque)
            dato = getattr(valores, campos[0])
            if dato is not None and not _igual(cifras.actual, dato, campos[0]):
                diferencias.setdefault(linea.fila_origen, []).append(campos[0])
    assert diferencias == {}, sorted(diferencias)
