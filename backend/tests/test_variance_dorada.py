"""Prueba dorada: el motor reproduce las columnas D a Q de la hoja `Ago` (agosto 2026).

Se comparan **todas** las celdas con número (5,822) de las líneas del reporte. Lo que no se puede
reproducir con los datos disponibles está en `EXCEPCIONES`, cada una con su causa; cualquier
diferencia fuera de esa lista (o una excepción que deje de serlo) hace fallar la prueba.
Tolerancias: 0.10 en importes (el propio Excel acumula centavos: ver sus columnas de control U/V)
y 1e-5 relativo en porcentajes.
"""

from decimal import Decimal

from real_agosto import AgostoReal, agosto_real  # noqa: F401

from fpa.servicios.variance import calcular_variance

D = Decimal
BLOQUES = {
    "mes": ("mes_actual", "mes_budget", "mes_var", "mes_pct"),
    "ytd": ("ytd_actual", "ytd_budget", "ytd_var", "ytd_pct"),
    "anual": ("anual_actual", "anual_budget", "anual_var", "anual_pct"),
}

# fila de la hoja `Ago` -> causa. Son 19 de las 512 líneas.
EXCEPCIONES = {
    # --- el Base de Datos no trae el dato (no es un error del motor) ---------------------------
    12: "Other Income: el Excel toma celdas puntuales de la hoja de la cuenta y deja fuera 5,000",
    25: "Total Other Income: arrastra la fila 12",
    272: "IVA Taxes: cuentas de pasivo (2007003, 213-0001-000) que el Base de Datos no trae",
    277: "Lodging Tax: cuenta de pasivo (2002014) que el Base de Datos no trae",
    285: "Bank Commissions: cuenta corporativa 504-0001-000 fuera del Base de Datos",
    289: "Audit Fees: cuentas corporativas 602-0038-000 y 504-0003-000 fuera del Base de Datos",
    292: "Income Taxes: cuenta corporativa 611-0001-000 fuera del Base de Datos",
    294: "Total Other Taxes: arrastra 272, 277, 285, 289 y 292",
    336: "TOTAL OPERATION EXPENSES: arrastra 294",
    533: "TOTAL OPERATION EXPENSES (resumen): arrastra 336 y 25",
    535: "PUERTO VALLARTA: arrastra 533",
    573: "Grand Total Budget: arrastra 535",
    273: "Administration Fee: el YTD del Excel es un valor pegado, sin cuentas ni fórmula",
    576: "Allocated (resumen): valor pegado sin fórmula",
    577: "Allocated (resumen): valor pegado sin fórmula",
    8: "Exchange Rate: es el tipo de cambio, no dinero; no se calcula",
    14: "Employee Dining: un residuo de un centavo del Excel (0.00 contra 0.01) cambia su %",
    # --- convenciones del Excel que difieren de la regla general (por validar) ------------------
    344: "Telephone Profit: el Excel la trata como gasto (Budget − Actual) aunque es una utilidad",
    530: "NET PROFIT COMMERCIAL SERVICES: su % usa |Budget|; el resto del reporte usa el signo",
}


def _igual(calculado: Decimal | None, esperado: Decimal, campo: str) -> bool:
    if calculado is None:
        return False
    if campo.endswith("pct"):
        return abs(calculado - esperado) <= D("0.00001") + D("0.00001") * abs(esperado)
    return abs(calculado - esperado) <= D("0.10")


def test_el_motor_reproduce_el_variance_de_agosto(agosto_real: AgostoReal) -> None:  # noqa: F811
    a = agosto_real
    r = calcular_variance(
        a.db, hotel_id=a.hotel_id, periodo="2026-08", version_mapeo_id=a.version_mapeo_id
    )
    assert r.version_plan_id == a.version_plan_id
    # Lo único que avisa son las dos cuentas de Vallarta sin línea (4002013 y 4003003): es lo que
    # el aviso de «cuentas sin línea» debe detectar
    sin_linea = [a for a in r.advertencias if "no están en ninguna línea" in a]
    assert len(sin_linea) == 1
    assert "2 cuentas" in sin_linea[0] and "4003003" in sin_linea[0] and "4002013" in sin_linea[0]
    # y las líneas sin cuentas de Vallarta (Administration Fee…) no tienen Actual capturado
    assert (
        len(r.advertencias) == 2 and "sin cuentas no tienen Actual capturado" in r.advertencias[1]
    )
    assert r.periodos_ytd == ["2026-07", "2026-08"] and r.periodos_sin_datos == []

    comparadas, con_diferencia = 0, {}
    for linea in r.lineas:
        valores = a.valores.get(linea.fila_origen)
        if valores is None:
            continue
        for bloque, campos in BLOQUES.items():
            cifras = getattr(r.resultado[linea.id], bloque)
            for campo, atributo in zip(campos, ("actual", "budget", "var", "pct"), strict=True):
                esperado = getattr(valores, campo)
                if esperado is None:
                    continue
                comparadas += 1
                if not _igual(getattr(cifras, atributo), esperado, campo):
                    con_diferencia.setdefault(linea.fila_origen, []).append(campo)

    assert comparadas > 5800
    assert set(con_diferencia) == set(EXCEPCIONES), {
        "inesperadas": sorted(set(con_diferencia) - set(EXCEPCIONES)),
        "ya_cuadran": sorted(set(EXCEPCIONES) - set(con_diferencia)),
    }


def test_las_253_lineas_vinculadas_cuadran_salvo_las_excepciones(
    agosto_real: AgostoReal,  # noqa: F811
) -> None:
    """263 líneas con cuentas (253 en S y T + 10 solo en T): 256 cuadran en las 12 columnas."""
    from fpa.repositorios.mapeo import RepositorioMapeo

    a = agosto_real
    vinculadas = {
        v.linea_id for v in RepositorioMapeo(a.db, a.hotel_id).vinculos(a.version_mapeo_id)
    }
    filas = {x.fila_origen for x in a.lineas if x.id in vinculadas and x.tipo == "detalle"}
    assert len(filas) == 263  # 253 con fórmula en S y T + 10 solo con fórmula en T
    con_excepcion = filas & set(EXCEPCIONES)
    assert con_excepcion == {12, 14, 272, 277, 285, 289, 292}
    assert len(filas - con_excepcion) == 256


def test_cero_diferencia_en_lo_que_el_excel_si_calcula_con_movimientos(
    agosto_real: AgostoReal,  # noqa: F811
) -> None:
    """Un caso concreto y legible: Salaries (fila 29) y Total Mgmt & Check In (71)."""
    a = agosto_real
    r = calcular_variance(
        a.db, hotel_id=a.hotel_id, periodo="2026-08", version_mapeo_id=a.version_mapeo_id
    )
    sueldos = r.resultado[a.por_fila[29].id]
    assert sueldos.mes.actual == D("321190.84") and sueldos.ytd.actual == D("625928.70")
    assert sueldos.mes.var is not None and abs(sueldos.mes.var - D("11745.070568")) < D("0.000001")
    total = r.resultado[a.por_fila[71].id]
    assert total.mes.actual == D("483198.48")
