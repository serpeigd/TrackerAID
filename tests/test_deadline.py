from datetime import date

from trackeraid.extraction.deadline import resolver_plazo, resolver_por_regex
from trackeraid.ingestion.bdns import ConvocatoriaDetalle

BASE_DETALLE = {
    "id": 1,
    "descripcion": "Convocatoria de prueba",
}


def _detalle(**overrides) -> ConvocatoriaDetalle:
    return ConvocatoriaDetalle.from_api({**BASE_DETALLE, **overrides})


def test_resolver_plazo_usa_campo_estructurado_si_existe():
    det = _detalle(fechaFinSolicitud="2026-10-31", textFin="esto no debería mirarse")
    r = resolver_plazo(det)
    assert r.metodo == "estructurado"
    assert r.fecha_fin == date(2026, 10, 31)
    assert r.sin_plazo is False


def test_resolver_por_regex_detecta_sin_plazo():
    r = resolver_por_regex("Sin plazo de solicitud")
    assert r.metodo == "regex_sin_plazo"
    assert r.sin_plazo is True
    assert r.fecha_fin is None


def test_resolver_por_regex_fecha_textual_con_mes_en_letra():
    r = resolver_por_regex("HASTA EL 31 DE OCTUBRE DE 2026")
    assert r.metodo == "regex_fecha_absoluta"
    assert r.fecha_fin == date(2026, 10, 31)


def test_resolver_por_regex_fecha_con_barras():
    r = resolver_por_regex("El plazo finaliza el 15/09/2026")
    assert r.metodo == "regex_fecha_absoluta"
    assert r.fecha_fin == date(2026, 9, 15)


def test_resolver_por_regex_relativo_con_fecha_de_referencia():
    r = resolver_por_regex(
        "15 días hábiles contados a partir del día 4 de septiembre de 2026",
        fecha_referencia=date(2026, 9, 4),
    )
    # Coincide primero con la fecha absoluta embebida en el propio texto
    # ("4 de septiembre de 2026") — comportamiento correcto: si el texto ya
    # trae una fecha explícita, no hace falta la aproximación relativa.
    assert r.metodo == "regex_fecha_absoluta"
    assert r.fecha_fin == date(2026, 9, 4)


def test_resolver_por_regex_relativo_puro_sin_fecha_absoluta():
    r = resolver_por_regex("El plazo es de 20 días naturales", fecha_referencia=date(2026, 1, 1))
    assert r.metodo == "regex_relativo"
    assert r.fecha_fin == date(2026, 1, 21)


def test_resolver_por_regex_relativo_sin_fecha_referencia_no_resuelve():
    r = resolver_por_regex("El plazo es de 20 días naturales", fecha_referencia=None)
    assert r.metodo == "no_resuelto"
    assert r.fecha_fin is None


def test_resolver_por_regex_texto_no_reconocido():
    r = resolver_por_regex("Consultar bases reguladoras para más información")
    assert r.metodo == "no_resuelto"
    assert r.fecha_fin is None


def test_resolver_plazo_usa_texto_fin_si_no_hay_fecha_estructurada():
    det = _detalle(fechaFinSolicitud=None, textFin="Sin plazo de solicitud")
    r = resolver_plazo(det)
    assert r.metodo == "regex_sin_plazo"
    assert r.sin_plazo is True


def test_resolver_plazo_no_resuelto_sin_ningun_dato():
    det = _detalle(fechaFinSolicitud=None, textFin=None)
    r = resolver_plazo(det)
    assert r.metodo == "no_resuelto"
    assert r.fecha_fin is None
