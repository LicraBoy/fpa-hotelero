from decimal import Decimal

import pytest
import test_versionado_mapeo as tv
from conftest import Mundo
from sqlalchemy.orm import Session
from test_versionado_mapeo import Escenario, fila

from fpa.repositorios.mapeo import RepositorioMapeo
from fpa.servicios.drilldown import desglose_de_linea
from fpa.servicios.versionado_mapeo import (
    aprobar,
    crear_borrador_desde,
    excluir_cuenta,
)
from fpa.servicios.vincular_cuentas import VinculoPedido, vincular_cuentas

D = Decimal
NO_SE_UTILIZA = "No se utiliza (catálogo corporativo: #N/D)"

# Una sección «Mgmt & Check In» con tres líneas; solo Salaries tiene cuenta en el Excel
ESTRUCTURA = [
    fila(),
    fila("Account #", "Account Description", "AUGUST"),
    fila(None, None, "Actual"),
    fila("M g m t   &   C h e c k   I n"),
    fila("029-0111-60010-000", "Salaries", 30, "='6009001.001'!L9", None),
    fila("029-0111-60010-000", "Holidays", 0, None, None),
    fila("029-0111-61410-000", "Equipment", 0, None, None),
    fila("029-0111-61800-000", "Postage", 0, None, None),
]


@pytest.fixture
def esc(db: Session, mundo: Mundo, monkeypatch: pytest.MonkeyPatch) -> Escenario:
    monkeypatch.setattr(tv, "EJEMPLO", ESTRUCTURA)
    e = Escenario(
        db,
        mundo,
        [
            tv._mov("6009001.001", "30", "0"),
            tv._mov("6009001.004", "7", "0"),  # Holidays: tiene movimientos
            tv._mov("6009020", "5", "0"),  # Equipment: tiene movimientos
        ],
    )
    # El mapeo del Excel no trae esas dos cuentas: Contraloría las dejó fuera «a propósito»
    for cuenta in ("6009001.004", "6009020"):
        excluir_cuenta(
            db,
            version_id=e.borrador.id,  # type: ignore[union-attr]
            cuenta_codigo=cuenta,
            motivo="No se ocupan todavía (decisión de Contraloría)",
            **e.kw,  # type: ignore[arg-type]
        )
    aprobar(db, version_id=e.borrador.id, **e.kw)  # type: ignore[union-attr, arg-type]
    db.commit()
    return e


def _vincular(esc: Escenario, pedidos: list[VinculoPedido], seccion: str = "Mgmt & Check In"):  # type: ignore[no-untyped-def]
    r = vincular_cuentas(
        esc.db,
        organizacion_id=esc.mundo.org1,
        hotel_id=esc.mundo.hotel_a,
        editor_id=None,
        aprobador_id=None,
        seccion=seccion,
        pedidos=pedidos,
    )
    esc.db.commit()
    return r


PEDIDOS = [
    VinculoPedido("Holidays", "6009001.004"),
    VinculoPedido("Equipment", "6009020"),
    VinculoPedido("Postage", "6009028", NO_SE_UTILIZA),
]


def test_crea_y_aprueba_una_version_nueva_con_las_cuentas_y_sus_notas(esc: Escenario) -> None:
    r = _vincular(esc, PEDIDOS)
    assert r.version_numero == 2 and len(r.agregados) == 3
    assert r.exclusiones_quitadas == ["6009001.004", "6009020"]
    repo = RepositorioMapeo(esc.db, esc.mundo.hotel_a)
    nueva = repo.aprobada()
    assert nueva is not None and nueva.numero == 2 and repo.borrador() is None
    por_cuenta = {v.cuenta_codigo: v for v in repo.vinculos(nueva.id)}
    assert por_cuenta["6009001.004"].linea_id == esc.linea("Holidays")
    assert por_cuenta["6009020"].linea_id == esc.linea("Equipment")
    assert por_cuenta["6009028"].nota == NO_SE_UTILIZA and por_cuenta["6009020"].nota is None
    assert por_cuenta["6009001.001"].linea_id == esc.linea("Salaries")  # lo anterior se conserva
    assert repo.excluidas(nueva.id) == []  # ya tienen línea: dejan de estar excluidas
    assert repo.obtener(esc.borrador.id).estado == "reemplazada"  # type: ignore[union-attr]


def test_es_idempotente(esc: Escenario) -> None:
    _vincular(esc, PEDIDOS)
    otra_vez = _vincular(esc, PEDIDOS)
    assert otra_vez.version_numero is None and otra_vez.agregados == []
    assert len(otra_vez.ya_estaban) == 3
    assert RepositorioMapeo(esc.db, esc.mundo.hotel_a).aprobada().numero == 2  # type: ignore[union-attr]


def test_la_nota_pasa_a_los_borradores_siguientes(esc: Escenario) -> None:
    _vincular(esc, PEDIDOS)
    borrador = crear_borrador_desde(esc.db, **esc.kw)  # type: ignore[arg-type]
    esc.db.commit()
    notas = {
        v.cuenta_codigo: v.nota
        for v in RepositorioMapeo(esc.db, esc.mundo.hotel_a).vinculos(borrador.id)
    }
    assert notas["6009028"] == NO_SE_UTILIZA and notas["6009020"] is None


def test_el_desglose_de_la_linea_trae_las_cuentas_y_la_nota(esc: Escenario) -> None:
    _vincular(esc, PEDIDOS)
    holidays = desglose_de_linea(
        esc.db,
        hotel_id=esc.mundo.hotel_a,
        periodo="2026-08",
        linea_id=esc.linea("Holidays"),
        bloque="mes",
    )
    assert [(c.cuenta_codigo, c.neto) for c in holidays.cuentas] == [("6009001.004", D("7.00"))]
    assert holidays.cifra == D("7.00") and holidays.motivos_cero == []
    postage = desglose_de_linea(
        esc.db,
        hotel_id=esc.mundo.hotel_a,
        periodo="2026-08",
        linea_id=esc.linea("Postage"),
        bloque="mes",
    )
    assert [(c.cuenta_codigo, c.nota) for c in postage.cuentas] == [("6009028", NO_SE_UTILIZA)]


def test_lineas_y_secciones_inexistentes_se_rechazan(esc: Escenario) -> None:
    with pytest.raises(LookupError, match="no existe"):
        _vincular(esc, [VinculoPedido("Linea Fantasma", "6009099")])
    with pytest.raises(LookupError, match="sección"):
        _vincular(esc, PEDIDOS, seccion="Otra Seccion")
    assert RepositorioMapeo(esc.db, esc.mundo.hotel_a).aprobada().numero == 1  # type: ignore[union-attr]


def test_los_pedidos_de_accounting_son_dos_lineas_con_su_cuenta() -> None:
    from fpa.mapeo_accounting import PEDIDOS as ACCOUNTING

    assert [(p.linea, p.cuenta) for p in ACCOUNTING] == [
        ("Seniority Premium", "6011001.010"),
        ("Education Bonus", "6011001.011"),
    ]
    assert all(p.signo == 1 and p.nota is None for p in ACCOUNTING)


def test_los_pedidos_de_maid_linen_son_dos_lineas_con_su_cuenta() -> None:
    from fpa.mapeo_maid_linen import PEDIDOS as MAID_LINEN

    assert [(p.linea, p.cuenta) for p in MAID_LINEN] == [
        ("Seniority Premium", "6010001.010"),
        ("Education Bonus", "6010001.011"),
    ]
    assert all(p.signo == 1 and p.nota is None for p in MAID_LINEN)


def test_mover_una_cuenta_la_quita_de_una_linea_y_la_pone_en_otra(esc: Escenario) -> None:
    _vincular(esc, PEDIDOS)  # v2: 6009020 está en Equipment
    r = vincular_cuentas(
        esc.db,
        organizacion_id=esc.mundo.org1,
        hotel_id=esc.mundo.hotel_a,
        editor_id=None,
        aprobador_id=None,
        seccion="Mgmt & Check In",
        pedidos=[VinculoPedido("Postage", "6009020")],
        quitar=[VinculoPedido("Equipment", "6009020")],
    )
    esc.db.commit()
    assert r.version_numero == 3 and r.vinculos_quitados == ["6009020 ← Equipment"]
    repo = RepositorioMapeo(esc.db, esc.mundo.hotel_a)
    nueva = repo.aprobada()
    assert nueva is not None
    lineas_de_6009020 = [
        v.linea_id for v in repo.vinculos(nueva.id) if v.cuenta_codigo == "6009020"
    ]
    assert lineas_de_6009020 == [esc.linea("Postage")]  # ya no está en Equipment
    # repetirlo no hace nada (la cuenta ya se movió)
    otra = vincular_cuentas(
        esc.db,
        organizacion_id=esc.mundo.org1,
        hotel_id=esc.mundo.hotel_a,
        editor_id=None,
        aprobador_id=None,
        seccion="Mgmt & Check In",
        pedidos=[VinculoPedido("Postage", "6009020")],
        quitar=[VinculoPedido("Equipment", "6009020")],
    )
    assert otra.version_numero is None


def test_los_pedidos_de_apartment_interior_mueven_6012106() -> None:
    from fpa.mapeo_apartment_interior import PEDIDOS as AI
    from fpa.mapeo_apartment_interior import QUITAR

    assert [(p.linea, p.cuenta) for p in AI] == [
        ("Education Bonus", "6012001.011"),
        ("Equipment/Supplies", "6012106"),
    ]
    assert [(p.linea, p.cuenta) for p in QUITAR] == [("Equip/Supplies PH", "6012106")]


def test_los_pedidos_de_common_area_son_dos_lineas_con_su_cuenta() -> None:
    from fpa.mapeo_common_area import PEDIDOS as COMMON_AREA

    assert [(p.linea, p.cuenta) for p in COMMON_AREA] == [
        ("Seniority Premium", "6006001.010"),
        ("Education Bonus", "6006001.011"),
    ]


def test_los_pedidos_de_owner_activities_son_dos_lineas_con_su_cuenta() -> None:
    from fpa.mapeo_owner_activities import PEDIDOS as OWNER_ACTIVITIES

    assert [(p.linea, p.cuenta) for p in OWNER_ACTIVITIES] == [
        ("Seniority Premium", "6003001.010"),
        ("Education Bonus", "6003001.011"),
    ]


def test_los_pedidos_de_owner_services_son_dos_lineas_con_su_cuenta() -> None:
    from fpa.mapeo_owner_services import PEDIDOS as OWNER_SERVICES

    assert [(p.linea, p.cuenta) for p in OWNER_SERVICES] == [
        ("Seniority Premium", "6007001.010"),
        ("Education Bonus", "6007001.011"),
    ]


def test_los_pedidos_de_purchasing_son_dos_lineas_con_su_cuenta() -> None:
    from fpa.mapeo_purchasing import PEDIDOS as PURCHASING

    assert [(p.linea, p.cuenta) for p in PURCHASING] == [
        ("Seniority Premium", "6013001.010"),
        ("Education Bonus", "6013001.011"),
    ]


def test_los_pedidos_de_los_negocios_comerciales_van_a_la_segunda_seccion() -> None:
    from fpa.mapeo_comerciales import NEGOCIOS, pedidos_de

    assert [s for s, _ in NEGOCIOS] == [
        "Travel Agency#2",
        "Store#2",
        "Cafeteria#2",
        "Bar#2",
        "Restaurant#2",
    ]
    assert [(p.linea, p.cuenta) for p in pedidos_de("6016001")] == [
        ("Seniority Premium", "6016001.010"),
        ("Education Bonus", "6016001.011"),
    ]


def test_una_seccion_repetida_se_elige_por_su_ordinal(esc: Escenario) -> None:
    # «Mgmt & Check In» existe una sola vez: con ordinal 1 se resuelve igual; con 2 no existe
    r = _vincular(
        esc, [VinculoPedido("Postage", "6009028", NO_SE_UTILIZA)], seccion="Mgmt & Check In#1"
    )
    assert r.version_numero is not None
    with pytest.raises(LookupError):
        _vincular(esc, [VinculoPedido("Postage", "6009028")], seccion="Mgmt & Check In#2")


def test_los_pedidos_de_legal_e_it_systems_son_dos_lineas_con_su_cuenta() -> None:
    from fpa.mapeo_legal_it import SECCIONES, pedidos_de

    assert SECCIONES == (("Legal", "6001001"), ("IT Systems", "6021001"))
    assert [(p.linea, p.cuenta) for p in pedidos_de("6021001")] == [
        ("Seniority Premium", "6021001.010"),
        ("Education Bonus", "6021001.011"),
    ]
