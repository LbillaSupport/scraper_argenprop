"""
cli.py
======
Runner por línea de comandos (sin interfaz gráfica).
Útil para pruebas rápidas o uso headless.

Ejemplos:
    python cli.py --tipos departamentos --operacion venta \
                  --ubicaciones palermo belgrano \
                  --precio-min 50000 --precio-max 150000 \
                  --expensas-max 200000 --workers 15
"""

from __future__ import annotations

import argparse

from src import analysis, exporter
from src.scraper import ArgenpropScraper, SearchCriteria


def _print(msg: str) -> None:
    print(msg, flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description="Scraper Argenprop (CLI)")
    p.add_argument("--operacion", default="venta", choices=["venta", "alquiler"])
    p.add_argument("--tipos", nargs="+", default=["departamentos"],
                   help="slugs: departamentos casas ph")
    p.add_argument("--ubicaciones", nargs="+", default=["palermo"],
                   help="slugs de barrios/municipios")
    p.add_argument("--precio-min", type=int, default=None)
    p.add_argument("--precio-max", type=int, default=None)
    p.add_argument("--m2cub-min", type=float, default=None)
    p.add_argument("--m2cub-max", type=float, default=None)
    p.add_argument("--amb-min", type=float, default=None)
    p.add_argument("--amb-max", type=float, default=None)
    p.add_argument("--expensas-max", type=float, default=None)
    p.add_argument("--antiguedad-max", type=float, default=None)
    p.add_argument("--workers", type=int, default=15)
    p.add_argument("--salida", default=None, help="ruta del .xlsx de salida")
    args = p.parse_args()

    criteria = SearchCriteria(
        operation=args.operacion,
        property_types=args.tipos,
        location_slugs=args.ubicaciones,
        price_min=args.precio_min,
        price_max=args.precio_max,
        workers=args.workers,
    )
    filters = analysis.Filters(
        price_min=args.precio_min,
        price_max=args.precio_max,
        m2_covered_min=args.m2cub_min,
        m2_covered_max=args.m2cub_max,
        rooms_min=args.amb_min,
        rooms_max=args.amb_max,
        expenses_max=args.expensas_max,
        age_max=args.antiguedad_max,
    )

    scraper = ArgenpropScraper(log=_print)
    _print(f"URL: {scraper.build_url(criteria)}")

    cards = scraper.collect_listing(criteria)
    if not cards:
        _print("Sin resultados.")
        return

    records = scraper.scrape_details_parallel(cards, args.workers)
    grouped = analysis.process(records, filters)
    ok, pozo = grouped["ok"], grouped["pozo"]
    _print(f"Terminadas: {len(ok)} · En pozo: {len(pozo)}")

    path = exporter.export(ok, pozo, args.salida)
    _print(f"Excel generado: {path}")


if __name__ == "__main__":
    main()
