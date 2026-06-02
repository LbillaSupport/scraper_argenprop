"""
main.py
=======
Punto de entrada de la aplicación de escritorio Scraper Argenprop.

Uso:
    python main.py
"""

import sys


def _check_dependencies() -> None:
    faltantes = []
    for mod, pip_name in [
        ("requests", "requests"),
        ("bs4", "beautifulsoup4"),
        ("pandas", "pandas"),
        ("openpyxl", "openpyxl"),
        ("customtkinter", "customtkinter"),
    ]:
        try:
            __import__(mod)
        except ImportError:
            faltantes.append(pip_name)
    if faltantes:
        print("Faltan dependencias. Instalalas con:\n")
        print("    pip install " + " ".join(faltantes))
        sys.exit(1)


def main() -> None:
    _check_dependencies()
    from src.gui import run
    run()


if __name__ == "__main__":
    main()
