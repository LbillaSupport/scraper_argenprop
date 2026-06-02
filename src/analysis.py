"""
analysis.py
===========
Procesa las publicaciones crudas devueltas por el scraper:

  * Calcula métricas propias (USD/m² cubierto, USD/m² total, score).
  * Detecta propiedades "en pozo".
  * Aplica los filtros avanzados del usuario.
  * Normaliza cada registro a la forma final que consume el exporter.

No realiza I/O ni red: es puro procesamiento en memoria.
"""

from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass

from . import config


# --------------------------------------------------------------------------- #
#  Filtros avanzados
# --------------------------------------------------------------------------- #
@dataclass
class Filters:
    price_min: float | None = None
    price_max: float | None = None
    m2_covered_min: float | None = None
    m2_covered_max: float | None = None
    m2_total_min: float | None = None
    m2_total_max: float | None = None
    rooms_min: float | None = None
    rooms_max: float | None = None
    bedrooms_min: float | None = None
    bedrooms_max: float | None = None
    expenses_max: float | None = None
    age_max: float | None = None


# --------------------------------------------------------------------------- #
#  Detección "en pozo"
# --------------------------------------------------------------------------- #
def is_en_pozo(record: dict) -> bool:
    """Busca palabras clave de obra en pozo en el título y la descripción."""
    haystack = " ".join(
        [
            str(record.get("title") or ""),
            str(record.get("card_title") or ""),
            str(record.get("description") or ""),
        ]
    ).lower()
    return any(kw in haystack for kw in config.POZO_KEYWORDS)


# --------------------------------------------------------------------------- #
#  Tipo de propiedad (para estimar expensas faltantes)
# --------------------------------------------------------------------------- #
def property_kind(record: dict) -> str:
    """
    Clasifica la propiedad en 'ph', 'casa' o 'departamento' a partir del
    título/card. Sirve para estimar expensas cuando el aviso no las publica:
    casas no suelen tener expensas, los PH tienen expensas reducidas y los
    departamentos pagan según m² y categoría del edificio.
    """
    hay = " " + " ".join(
        [str(record.get("title") or ""), str(record.get("card_title") or "")]
    ).lower() + " "
    if re.search(r"\bph\b", hay):
        return "ph"
    if re.search(r"\b(casa|casas|casona|chalet|duplex|dúplex)\b", hay):
        return "casa"
    return "departamento"


# --------------------------------------------------------------------------- #
#  Métricas
# --------------------------------------------------------------------------- #
def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if not numerator or not denominator:
        return None
    if denominator <= 0:
        return None
    return round(numerator / denominator, 2)


def compute_metrics(record: dict) -> dict:
    """
    Agrega al registro las métricas que se calculan por propiedad de forma
    aislada: usd_m2_covered, usd_m2_total y en_pozo.

    El `score` y el `zone_score` NO se calculan acá: dependen del conjunto
    completo de resultados (normalización + mediana por zona) y se asignan
    luego en `apply_scoring()`. Acá quedan como placeholders en None.
    """
    price = record.get("price")
    m2_cov = record.get("m2_covered")
    m2_tot = record.get("m2_total")

    record["usd_m2_covered"] = _safe_div(price, m2_cov)
    record["usd_m2_total"] = _safe_div(price, m2_tot)

    record["score"] = None
    record["zone_score"] = None
    record["en_pozo"] = is_en_pozo(record)
    record["property_kind"] = property_kind(record)

    # Expensas: placeholders. Si el aviso no las publica, se estiman en
    # `apply_scoring()` (necesita el conjunto completo para sacar la tarifa
    # $/m² por zona). `expenses_used` es lo que consume el scoring.
    record["expenses_est"] = None
    record["expenses_estimated"] = False
    record["expenses_used"] = record.get("expenses")
    return record


# --------------------------------------------------------------------------- #
#  Scoring con factor de zona
# --------------------------------------------------------------------------- #
def _norm_key(text: str | None) -> str:
    """Normaliza un nombre de zona: minúsculas, sin acentos, espacios simples."""
    s = (text or "").strip().lower()
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(s.split())


# Mapa: nombre de zona normalizado -> nombre canónico (el de config.LOCATIONS).
_KNOWN_ZONES: dict[str, str] = {}
for _prov_locs in config.LOCATIONS.values():
    for _display in _prov_locs:
        _KNOWN_ZONES[_norm_key(_display)] = _display

# Mapa: zona normalizada -> puntaje manual (override).
_ZONE_OVERRIDES: dict[str, float] = {
    _norm_key(k): float(v) for k, v in config.ZONE_SCORES.items()
}


def canonical_zone(neighborhood: str | None) -> str:
    """
    Lleva 'Palermo Chico' / 'Palermo Hollywood' a su barrio canónico 'Palermo'
    para que las subzonas no fragmenten las medianas ni los overrides.
    """
    nk = _norm_key(neighborhood)
    if not nk:
        return "Sin zona"
    if nk in _KNOWN_ZONES:
        return _KNOWN_ZONES[nk]
    for known_nk, display in _KNOWN_ZONES.items():
        if known_nk and (known_nk in nk or nk in known_nk):
            return display
    return (neighborhood or "").strip().title() or "Sin zona"


def _minmax(value, lo, hi, invert: bool = False) -> float:
    """Normaliza `value` a 0–100 dentro de [lo, hi]. Neutro (50) si no aplica."""
    if value is None or lo is None or hi is None or hi == lo:
        return 50.0
    n = (value - lo) / (hi - lo) * 100.0
    n = max(0.0, min(100.0, n))
    return 100.0 - n if invert else n


def _range(values) -> tuple[float | None, float | None]:
    nums = [v for v in values if v is not None]
    return (min(nums), max(nums)) if nums else (None, None)


def _zone_quality(
    zone: str,
    zone_median: dict[str, float],
    zone_count: dict[str, int],
    zm_lo: float | None,
    zm_hi: float | None,
) -> float:
    """Devuelve la calidad de la zona en escala 0–100."""
    # 1) Override manual (solo si está configurado y la zona está cargada).
    if config.ZONE_SCORE_SOURCE == "override":
        ov = _ZONE_OVERRIDES.get(_norm_key(zone))
        if ov is not None:
            return max(0.0, min(100.0, ov / 10.0 * 100.0))

    # 2) Derivado del mercado: mediana de USD/m² de la zona, normalizada.
    if zone_count.get(zone, 0) < config.MIN_ZONE_SAMPLES:
        return 50.0  # pocas muestras -> neutro
    return _minmax(zone_median.get(zone), zm_lo, zm_hi, invert=False)


def _amenity_factor(record: dict) -> float:
    """
    Multiplicador de expensas según los amenities mencionados en el aviso.

    Un edificio con pileta + gimnasio + seguridad + encargado paga MUCHO más
    de expensas que uno sin nada. Recorremos título, descripción y features de
    la card; cada GRUPO de amenities presente suma un escalón al factor.
    Devuelve un número ≈ 0.75 (sin amenities) … 1.70 (edificio full).
    """
    hay = _norm_key(" ".join(
        str(record.get(k) or "")
        for k in ("title", "card_title", "description", "card_features", "card_raw")
    ))
    groups_hit = sum(
        any(kw in hay for kw in group) for group in config.EXPENSE_AMENITY_GROUPS
    )
    factor = config.EXPENSE_AMENITY_BASE + config.EXPENSE_AMENITY_STEP * groups_hit
    return min(factor, config.EXPENSE_AMENITY_MAX)


def _estimate_missing_expenses(records: list[dict]) -> None:
    """
    Rellena `expenses_used` para las propiedades que NO publican expensas,
    estimándolas a partir de la propia búsqueda. Marca `expenses_estimated`
    y deja el valor estimado en `expenses_est` (para mostrarlo aparte del real).

    Criterio:
      * Casas         -> sin expensas comunes (0).
      * PH            -> expensas reducidas respecto a un depto equivalente.
      * Departamentos -> tarifa $/m² MEDIANA de su zona (o global) × m² cubiertos.

    Requiere que `_zone` y `property_kind` ya estén asignados. Si no hay datos
    suficientes para estimar, deja `expenses_used` en None (neutro en el score).
    """
    PH_FACTOR = 0.35  # un PH paga ~35% de lo que pagaría un depto similar

    # Tarifa $/m² de expensas tomada de los DEPARTAMENTOS con expensas reales.
    rate_by_zone: dict[str, list[float]] = {}
    rate_all: list[float] = []
    abs_dep: list[float] = []
    for r in records:
        exp, m2 = r.get("expenses"), r.get("m2_covered")
        if r.get("property_kind") == "departamento" and exp and m2 and m2 > 0:
            rate_by_zone.setdefault(r["_zone"], []).append(exp / m2)
            rate_all.append(exp / m2)
            abs_dep.append(exp)

    zone_rate = {z: statistics.median(v) for z, v in rate_by_zone.items()}
    global_rate = statistics.median(rate_all) if rate_all else None
    global_abs = statistics.median(abs_dep) if abs_dep else None

    for r in records:
        if r.get("expenses") is not None:
            r["expenses_used"] = r["expenses"]
            continue

        kind = r.get("property_kind", "departamento")
        m2 = r.get("m2_covered")
        est: float | None = None

        if kind == "casa":
            est = 0.0
        else:
            # Amenities y tipo modulan la estimación base ($/m² de la zona).
            kind_f = PH_FACTOR if kind == "ph" else 1.0
            amenity_f = _amenity_factor(r)
            rate = zone_rate.get(r["_zone"]) or global_rate
            if rate is not None and m2 and m2 > 0:
                est = rate * m2 * kind_f * amenity_f
            elif global_abs is not None:  # sin m²: caemos al valor absoluto típico
                est = global_abs * kind_f * amenity_f

        if est is not None:
            est = round(est, 2)
            r["expenses_est"] = est
            r["expenses_estimated"] = True
        r["expenses_used"] = est


def apply_scoring(records: list[dict]) -> None:
    """
    Calcula `zone_score` (0–10) y `score` final para cada registro, EN SITIO.

    Importante: la normalización es RELATIVA al conjunto recibido, así que los
    scores comparan las propiedades de ESTA búsqueda entre sí (no son valores
    absolutos entre búsquedas distintas).
    """
    if not records:
        return

    w = config.SCORE_WEIGHTS

    # --- Zona canónica de cada propiedad ---
    for r in records:
        r["_zone"] = canonical_zone(r.get("neighborhood"))

    # --- Estima expensas faltantes (usa zona + tipo + m²) ---
    _estimate_missing_expenses(records)

    # --- Rangos globales para normalizar cada componente ---
    v_lo, v_hi = _range(r.get("usd_m2_covered") for r in records)
    s_lo, s_hi = _range(r.get("m2_covered") for r in records)
    e_lo, e_hi = _range(r.get("expenses_used") for r in records)

    # --- Medianas de USD/m² por zona canónica ---
    by_zone: dict[str, list[float]] = {}
    for r in records:
        usd = r.get("usd_m2_covered")
        if usd is not None:
            by_zone.setdefault(r["_zone"], []).append(usd)

    zone_median = {z: statistics.median(vs) for z, vs in by_zone.items()}
    zone_count = {z: len(vs) for z, vs in by_zone.items()}
    zm_lo, zm_hi = _range(zone_median.values())

    # --- Score por propiedad ---
    for r in records:
        zone = r["_zone"]
        zq = _zone_quality(zone, zone_median, zone_count, zm_lo, zm_hi)
        r["zone_score"] = round(zq / 10.0, 1)  # 0–10 para mostrar

        factor = config.ZONE_FACTOR_MIN + (zq / 100.0) * (
            config.ZONE_FACTOR_MAX - config.ZONE_FACTOR_MIN
        )

        value_n = _minmax(r.get("usd_m2_covered"), v_lo, v_hi, invert=True)
        size_n = _minmax(r.get("m2_covered"), s_lo, s_hi, invert=False)
        exp_n = _minmax(r.get("expenses_used"), e_lo, e_hi, invert=True)

        base = w["value"] * value_n + w["size"] * size_n + w["expenses"] * exp_n
        r["score"] = round(base * factor, 1)

    for r in records:
        r.pop("_zone", None)


# --------------------------------------------------------------------------- #
#  Filtros
# --------------------------------------------------------------------------- #
def _passes_min(value: float | None, minimum: float | None) -> bool:
    # Política tolerante: si falta el dato, no se descarta por ese filtro.
    if minimum is None or value is None:
        return True
    return value >= minimum


def _passes_max(value: float | None, maximum: float | None) -> bool:
    if maximum is None or value is None:
        return True
    return value <= maximum


def passes_filters(record: dict, f: Filters) -> bool:
    checks = [
        _passes_min(record.get("price"), f.price_min),
        _passes_max(record.get("price"), f.price_max),
        _passes_min(record.get("m2_covered"), f.m2_covered_min),
        _passes_max(record.get("m2_covered"), f.m2_covered_max),
        _passes_min(record.get("m2_total"), f.m2_total_min),
        _passes_max(record.get("m2_total"), f.m2_total_max),
        _passes_min(record.get("rooms"), f.rooms_min),
        _passes_max(record.get("rooms"), f.rooms_max),
        _passes_min(record.get("bedrooms"), f.bedrooms_min),
        _passes_max(record.get("bedrooms"), f.bedrooms_max),
        _passes_max(record.get("expenses"), f.expenses_max),
        _passes_max(record.get("age"), f.age_max),
    ]
    return all(checks)


# --------------------------------------------------------------------------- #
#  Pipeline de procesamiento
# --------------------------------------------------------------------------- #
def process(records: list[dict], filters: Filters) -> dict[str, list[dict]]:
    """
    Procesa todos los registros y devuelve dos grupos:
        {"ok": [...], "pozo": [...]}
    'ok'   -> propiedades terminadas que pasaron los filtros.
    'pozo' -> propiedades en pozo (no se mezclan en el ranking principal).

    Las propiedades en pozo NO se filtran por los criterios avanzados:
    se reportan siempre todas las detectadas, según la especificación.
    """
    ok: list[dict] = []
    pozo: list[dict] = []

    for raw in records:
        rec = compute_metrics(raw)
        if rec["en_pozo"]:
            pozo.append(rec)
            continue
        if passes_filters(rec, filters):
            ok.append(rec)

    # El score (normalizado + factor de zona) se calcula sobre el conjunto
    # de propiedades terminadas, que es lo que se rankea.
    apply_scoring(ok)

    return {"ok": ok, "pozo": pozo}
