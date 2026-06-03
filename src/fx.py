"""
fx.py
=====
Cotización del dólar oficial (DolarApi) para comparar precios en USD y en pesos
sobre una misma escala.

  * `get_official_usd()` -> ARS por USD (dólar oficial, venta). Se cachea durante
    la corrida y cae a un respaldo configurable si la API no responde.
  * `to_usd()` -> convierte un precio a USD según la moneda detectada.

Es el único lugar que sabe de la cotización: el resto del programa sólo recibe
el número.
"""

from __future__ import annotations

from typing import Callable

import requests

from . import config

# Cache de proceso: una sola consulta por corrida.
_cache: dict[str, float | None] = {"rate": None}


def get_official_usd(
    log: Callable[[str], None] | None = None, force: bool = False
) -> float:
    """
    Devuelve los ARS por USD del dólar oficial (campo `venta` de DolarApi).

    Cachea el valor. Si la API falla, usa `config.FX_USD_FALLBACK` para no
    abortar la búsqueda. Nunca devuelve None.
    """
    log = log or (lambda _m: None)
    if _cache["rate"] is not None and not force:
        return _cache["rate"]

    try:
        resp = requests.get(config.DOLARAPI_URL, timeout=config.REQUEST_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            rate = float(data.get("venta") or data.get("compra") or 0)
            if rate > 0:
                _cache["rate"] = rate
                fecha = data.get("fechaActualizacion", "")
                log(f"Dólar oficial (venta): ${rate:,.0f} ARS — DolarApi {fecha}")
                return rate
        log(f"DolarApi respondió HTTP {resp.status_code}; uso respaldo.")
    except requests.RequestException as exc:
        log(f"No se pudo consultar DolarApi ({exc}); uso respaldo.")

    _cache["rate"] = float(config.FX_USD_FALLBACK)
    log(f"Cotización de respaldo: ${config.FX_USD_FALLBACK:,.0f} ARS/USD")
    return _cache["rate"]


def to_usd(price: float | None, currency: str, rate: float | None) -> float | None:
    """
    Convierte `price` a USD según `currency` ('USD' / 'ARS').

      * USD (o moneda desconocida) -> se devuelve tal cual (se asume USD).
      * ARS -> se divide por la cotización; si no hay cotización, None.
    """
    if price is None:
        return None
    if currency == "ARS":
        return round(price / rate, 2) if rate else None
    return float(price)
