"""
scraper.py
==========
Lógica de scraping sobre Argenprop.

Responsabilidades:
  1. Construir la URL de búsqueda a partir de los criterios del usuario.
  2. Detectar automáticamente la cantidad de páginas (sin número fijo).
  3. Extraer las "cards" de cada página de listado.
  4. Entrar a cada publicación (scraping profundo) en paralelo
     (ThreadPoolExecutor, 10–20 workers).
  5. Devolver una lista de diccionarios con toda la información cruda.

No realiza cálculos ni filtros: eso vive en analysis.py.
"""

from __future__ import annotations

import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Iterable

import requests
from bs4 import BeautifulSoup

from . import config


# --------------------------------------------------------------------------- #
#  Utilidades de parseo numérico
# --------------------------------------------------------------------------- #
def parse_number(text: str | None) -> float | None:
    """
    Extrae el primer número de un texto respetando el formato argentino
    (punto = miles, coma = decimales).

    "USD 150.000"   -> 150000.0
    "65,5 m²"       -> 65.5
    "$ 1.234.567"   -> 1234567.0
    """
    if not text:
        return None
    match = re.search(r"\d[\d.,]*", text)
    if not match:
        return None
    raw = match.group()

    # Si tiene coma, se asume coma decimal -> los puntos son miles.
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    else:
        # Sin coma: los puntos son separadores de miles.
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


def parse_int(text: str | None) -> int | None:
    value = parse_number(text)
    return int(value) if value is not None else None


def detect_currency(text: str | None) -> str:
    """Devuelve 'USD' o 'ARS' según el símbolo encontrado."""
    if not text:
        return ""
    low = text.lower()
    if "usd" in low or "u$s" in low or "dólar" in low or "dolar" in low:
        return "USD"
    if "$" in low:
        return "ARS"
    return ""


def _find_value_for_label(text: str, labels: Iterable[str]) -> float | None:
    """
    Busca, dentro de `text`, un número asociado a alguna de las `labels`.
    Soporta los dos órdenes habituales:
        "Cant. Ambientes 3"   (etiqueta antes del número)
        "65 m² Sup. Cubierta" (número antes de la etiqueta)
    """
    for label in labels:
        esc = re.escape(label)
        # etiqueta -> número
        m = re.search(esc + r"[^\d]{0,15}(\d[\d.,]*)", text, re.IGNORECASE)
        if m:
            return parse_number(m.group(1))
        # número -> etiqueta
        m = re.search(r"(\d[\d.,]*)[^\d]{0,15}" + esc, text, re.IGNORECASE)
        if m:
            return parse_number(m.group(1))
    return None


# --------------------------------------------------------------------------- #
#  Criterios de búsqueda
# --------------------------------------------------------------------------- #
@dataclass
class SearchCriteria:
    operation: str = "venta"                 # slug: venta / alquiler
    property_types: list[str] = field(default_factory=list)  # slugs
    location_slugs: list[str] = field(default_factory=list)  # slugs
    # Rango de precio CANÓNICO en USD. Se busca tanto en dólares como en pesos
    # (convirtiendo el rango con la cotización) para no perder publicaciones
    # baratas en pesos que, al cambio, entran en el rango en dólares.
    price_min_usd: int | None = None
    price_max_usd: int | None = None
    usd_rate: float | None = None            # ARS por USD (dólar oficial venta)
    workers: int = config.DEFAULT_WORKERS


# --------------------------------------------------------------------------- #
#  Scraper
# --------------------------------------------------------------------------- #
class ArgenpropScraper:
    """Encapsula la sesión HTTP y todo el proceso de scraping."""

    def __init__(self, log: Callable[[str], None] | None = None):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": config.USER_AGENT,
                "Accept-Language": "es-AR,es;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        self._log = log or (lambda msg: None)
        self._cancel = threading.Event()

    # ----------------------------- control -------------------------------- #
    def cancel(self) -> None:
        self._cancel.set()

    def _cancelled(self) -> bool:
        return self._cancel.is_set()

    # --------------------------- construcción URL ------------------------- #
    def build_url(
        self,
        criteria: SearchCriteria,
        currency: str | None = None,
        pmin: int | None = None,
        pmax: int | None = None,
    ) -> str:
        """
        Arma la URL de una pasada de búsqueda. Ejemplo:

        https://www.argenprop.com/casas-o-departamentos-o-ph/venta/palermo-o-belgrano/dolares-10000-70000

        `currency`/`pmin`/`pmax` definen el segmento de precio de ESA pasada.
        Si `currency` es None (o no hay extremos), se omite el segmento y
        Argenprop devuelve ambas monedas.
        """
        parts: list[str] = [config.BASE_URL]

        types = criteria.property_types or list(config.PROPERTY_TYPES.values())
        parts.append("-o-".join(types))
        parts.append(criteria.operation)

        if criteria.location_slugs:
            parts.append("-o-".join(criteria.location_slugs))

        price_segment = self._price_segment(currency, pmin, pmax)
        if price_segment:
            parts.append(price_segment)

        return "/".join(parts)

    @staticmethod
    def _price_segment(currency: str | None, pmin: int | None, pmax: int | None) -> str:
        if not currency or (not pmin and not pmax):
            return ""
        if pmin and pmax:
            return f"{currency}-{pmin}-{pmax}"
        if pmin:
            return f"{currency}-desde-{pmin}"
        return f"{currency}-hasta-{pmax}"

    def _search_passes(
        self, criteria: SearchCriteria
    ) -> list[tuple[str | None, int | None, int | None]]:
        """
        Pasadas (moneda, pmin, pmax) a buscar para cubrir ambas monedas:

          * Sin rango de precio -> 1 pasada sin segmento (Argenprop ya devuelve
            dólares y pesos juntos).
          * Con rango en USD -> 1 pasada en dólares con ese rango y otra en
            pesos con el rango convertido por la cotización.
        """
        mn, mx = criteria.price_min_usd, criteria.price_max_usd
        if not mn and not mx:
            return [(None, None, None)]

        passes: list[tuple[str | None, int | None, int | None]] = [("dolares", mn, mx)]
        rate = criteria.usd_rate
        if rate:
            passes.append(
                (
                    "pesos",
                    round(mn * rate) if mn else None,
                    round(mx * rate) if mx else None,
                )
            )
        return passes

    @staticmethod
    def page_url(base_url: str, page: int) -> str:
        """Argenprop pagina con el query ?pagina-N."""
        if page <= 1:
            return base_url
        sep = "&" if "?" in base_url else "?"
        return f"{base_url}{sep}pagina-{page}"

    # ------------------------------ HTTP ---------------------------------- #
    def _fetch(self, url: str) -> BeautifulSoup | None:
        """GET con reintentos. Devuelve un BeautifulSoup o None."""
        for attempt in range(1, config.REQUEST_RETRIES + 1):
            if self._cancelled():
                return None
            try:
                resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    return BeautifulSoup(resp.text, "lxml")
                if resp.status_code == 404:
                    return None
                self._log(f"  · {url} -> HTTP {resp.status_code} (intento {attempt})")
            except requests.RequestException as exc:
                self._log(f"  · error de red en {url}: {exc} (intento {attempt})")
            time.sleep(1.0 * attempt)
        return None

    # -------------------------- detección páginas ------------------------- #
    def detect_total_pages(self, soup: BeautifulSoup) -> int:
        """
        Detecta la cantidad de páginas (Anterior 1 2 3 … 29 Siguiente).

        Señal CONFIABLE: los hrefs con `pagina-N`. No escaneamos cualquier
        número de la página porque años ("2024"), precios o m² darían un total
        disparatado (y sin tope eso escrapearía miles de páginas inexistentes).
        """
        numbers: list[int] = []

        # 1) Hrefs con ?pagina-N -> el número real de página.
        for a in soup.find_all("a", href=True):
            m = re.search(r"pagina-(\d+)", a["href"])
            if m:
                numbers.append(int(m.group(1)))

        # 2) Sólo si no hubo hrefs, miramos los números DENTRO del bloque de
        #    paginación (no de toda la página).
        if not numbers:
            pager = soup.select_one(
                "[class*='pagination'], [class*='paginacion'], "
                "[class*='pagination'], nav[aria-label*='pag']"
            )
            if pager:
                for el in pager.select("a, span"):
                    text = el.get_text(strip=True)
                    if text.isdigit():
                        numbers.append(int(text))

        if not numbers:
            return 1
        total = max(numbers)
        return min(total, config.MAX_PAGES_HARD_LIMIT)

    # ----------------------- extracción de cards -------------------------- #
    def parse_cards(self, soup: BeautifulSoup) -> list[dict]:
        """
        Extrae la información visible de cada card del listado.
        Card raíz esperada: <div class="listing__item">
        """
        results: list[dict] = []
        cards = soup.select("div.listing__item")

        for card in cards:
            link = card.find("a", href=True)
            if not link:
                continue
            href = link["href"]
            url = href if href.startswith("http") else config.BASE_URL + href

            card_text = card.get_text(" ", strip=True)

            results.append(
                {
                    "url": url,
                    "card_price": self._card_text(card, ".card__price"),
                    "card_address": self._card_text(card, ".card__address"),
                    "card_title": self._card_text(card, ".card__title"),
                    "card_features": self._card_text(card, ".card__main-features"),
                    "card_neighborhood": self._guess_neighborhood(card),
                    "card_image": self._card_image(card),
                    "card_raw": card_text,
                }
            )
        return results

    @staticmethod
    def _card_text(card, selector: str) -> str:
        el = card.select_one(selector)
        return el.get_text(" ", strip=True) if el else ""

    @staticmethod
    def _card_image(card) -> str:
        """URL de la primera foto del aviso (para los thumbnails de la galería)."""
        img = card.find("img")
        if not img:
            return ""
        src = (
            img.get("data-src")
            or img.get("src")
            or (img.get("srcset", "").split()[0] if img.get("srcset") else "")
        )
        if src.startswith("//"):
            src = "https:" + src
        return src

    @staticmethod
    def _guess_neighborhood(card) -> str:
        el = card.select_one(".card__address")
        if not el:
            return ""
        text = el.get_text(" ", strip=True)
        # La dirección suele ser "Calle 123, Barrio". Tomamos el último tramo.
        if "," in text:
            return text.split(",")[-1].strip()
        return text

    # ----------------------- listado completo ----------------------------- #
    def collect_listing(
        self,
        criteria: SearchCriteria,
        progress: Callable[[str, int, int], None] | None = None,
    ) -> list[dict]:
        """
        Recorre todas las páginas de TODAS las pasadas (dólares + pesos) y
        devuelve las cards crudas, deduplicadas por URL y por contenido
        (misma propiedad republicada con otra URL), conservando el orden.
        """
        all_cards: list[dict] = []
        seen: set[str] = set()
        seen_fp: set[tuple] = set()

        for currency, pmin, pmax in self._search_passes(criteria):
            if self._cancelled():
                break
            base_url = self.build_url(criteria, currency, pmin, pmax)
            self._log(f"URL de búsqueda ({currency or 'ambas monedas'}): {base_url}")
            self._collect_pass(base_url, all_cards, seen, seen_fp, progress)

        self._log(f"Cards únicas encontradas: {len(all_cards)}")
        return all_cards

    @staticmethod
    def _card_fingerprint(card: dict) -> tuple | None:
        """
        Huella de contenido para detectar la MISMA propiedad republicada con
        otra URL (mismo precio + título + características). Devuelve None si no
        hay señal suficiente (para no colapsar avisos distintos por error).
        """
        price = " ".join((card.get("card_price") or "").lower().split())
        title = " ".join((card.get("card_title") or "").lower().split())
        feats = " ".join((card.get("card_features") or "").lower().split())
        if not price or not (title or feats):
            return None
        return (price, title, feats)

    def _collect_pass(
        self,
        base_url: str,
        out: list[dict],
        seen: set[str],
        seen_fp: set[tuple],
        progress: Callable[[str, int, int], None] | None,
    ) -> None:
        """Recorre las páginas de UNA pasada y agrega cards nuevas a `out`."""
        first = self._fetch(base_url)
        if first is None:
            self._log("No se pudo obtener la primera página de esta pasada.")
            return

        total_pages = self.detect_total_pages(first)
        self._log(f"Páginas detectadas: {total_pages}")

        def add(cards: list[dict]) -> None:
            for c in cards:
                if c["url"] in seen:
                    continue
                fp = self._card_fingerprint(c)
                if fp is not None and fp in seen_fp:
                    continue  # misma propiedad, otra URL
                seen.add(c["url"])
                if fp is not None:
                    seen_fp.add(fp)
                out.append(c)

        add(self.parse_cards(first))
        if progress:
            progress("listado", 1, total_pages)

        for page in range(2, total_pages + 1):
            if self._cancelled():
                break
            soup = self._fetch(self.page_url(base_url, page))
            if soup is not None:
                page_cards = self.parse_cards(soup)
                # Defensa: si una página viene SIN avisos, llegamos al final
                # real (aunque la detección haya estimado de más). Cortamos.
                if not page_cards:
                    self._log(f"Página {page} sin avisos: fin del listado.")
                    break
                add(page_cards)
            if progress:
                progress("listado", page, total_pages)

    # ----------------------- scraping profundo ---------------------------- #
    def scrape_detail(self, card: dict) -> dict:
        """
        Entra a una publicación y extrae todos los datos profundos.
        Combina lo del detalle con lo de la card como respaldo.
        """
        result = dict(card)  # arranca con lo visible de la card
        soup = self._fetch(card["url"])
        if soup is None:
            result["detail_ok"] = False
            return result
        result["detail_ok"] = True

        # --- Precio ---
        price_text = self._sel_text(soup, ".titlebar__price") or card.get("card_price", "")
        result["price"] = parse_number(price_text)
        result["currency"] = detect_currency(price_text)

        # --- Dirección ---
        result["address"] = (
            self._sel_text(soup, ".titlebar__address")
            or card.get("card_address", "")
        )

        # --- Expensas ---
        result["expenses"] = self._extract_expenses(soup)

        # --- Características (zona de features del detalle) ---
        features_text = self._features_text(soup)

        result["rooms"] = _find_value_for_label(
            features_text, ["Cant. Ambientes", "Ambientes"]
        )
        result["bedrooms"] = _find_value_for_label(
            features_text, ["Cant. Dormitorios", "Dormitorios"]
        )
        result["bathrooms"] = _find_value_for_label(
            features_text, ["Cant. Baños", "Baños", "Banos"]
        )
        result["age"] = _find_value_for_label(
            features_text, ["Antigüedad", "Antiguedad"]
        )
        result["m2_covered"] = _find_value_for_label(
            features_text, ["Sup. Cubierta", "Superficie cubierta"]
        )
        result["m2_total"] = _find_value_for_label(
            features_text, ["Sup. Total", "Superficie total"]
        )

        # --- Título ---
        result["title"] = (
            self._sel_text(soup, ".titlebar__title")
            or self._sel_text(soup, "h1")
            or card.get("card_title", "")
        )

        # --- Descripción ---
        result["description"] = self._sel_text(soup, ".section-description--content")

        # --- Barrio: lo derivamos del título de detalle, la card o la dirección ---
        result["neighborhood"] = self._derive_neighborhood(result, card)

        return result

    @staticmethod
    def _derive_neighborhood(result: dict, card: dict) -> str:
        """
        El título de detalle suele ser "Venta en Palermo Chico, Palermo":
        tomamos el barrio entre " en " y la primera coma. Si no, caemos a la
        pista de la card y por último a la dirección.
        """
        title = result.get("title") or ""
        m = re.search(r"\ben\s+(.+?),", title, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        if card.get("card_neighborhood"):
            return card["card_neighborhood"]
        return result.get("address", "")

    @staticmethod
    def _sel_text(soup: BeautifulSoup, selector: str) -> str:
        el = soup.select_one(selector)
        return el.get_text(" ", strip=True) if el else ""

    @staticmethod
    def _features_text(soup: BeautifulSoup) -> str:
        """Texto concentrado de las secciones de características del detalle."""
        chunks: list[str] = []
        selectors = [
            ".property-features",
            ".section-icon-features",
            ".property-features__item",
            "ul.property-features",
            ".section-bullets",
            ".section-feature",
        ]
        for sel in selectors:
            for el in soup.select(sel):
                chunks.append(el.get_text(" ", strip=True))
        text = " ".join(chunks).strip()
        # Si no encontramos secciones específicas, usamos todo el documento
        # como último recurso (las etiquetas son específicas, no hay ruido).
        if not text:
            text = soup.get_text(" ", strip=True)
        return text

    # Expensas reales: tienen $ pegado al número ("Expensas: $119.000" o
    # "+ $119.000 expensas"). Exigir el $ evita capturar los m² de la barra de
    # avisos relacionados ("expensas 40 m² cubie."). Piso mínimo de seguridad.
    MIN_EXPENSES = 1000
    _EXPENSES_PATTERNS = (
        re.compile(r"expensas\s*[:\-]?\s*\$\s*(\d[\d.,]*)", re.IGNORECASE),
        re.compile(r"\$\s*(\d[\d.,]*)\s*(?:de\s+)?expensas", re.IGNORECASE),
    )

    @classmethod
    def _extract_expenses(cls, soup: BeautifulSoup) -> float | None:
        # 1) Selector dedicado (camino rápido, sin recorrer toda la página).
        el = soup.select_one(".titlebar__expenses")
        if el:
            value = parse_number(el.get_text(" ", strip=True))
            if value and value >= cls.MIN_EXPENSES:
                return value
        # 2) Sólo si hizo falta: texto completo, exigiendo el signo $.
        page_text = soup.get_text(" ", strip=True)
        for pattern in cls._EXPENSES_PATTERNS:
            m = pattern.search(page_text)
            if m:
                value = parse_number(m.group(1))
                if value and value >= cls.MIN_EXPENSES:
                    return value
        return None

    # ------------------- scraping profundo concurrente -------------------- #
    def scrape_details_parallel(
        self,
        cards: list[dict],
        workers: int,
        progress: Callable[[str, int, int], None] | None = None,
    ) -> list[dict]:
        """
        Ejecuta scrape_detail sobre todas las cards en paralelo.
        """
        workers = max(config.MIN_WORKERS, min(workers, config.MAX_WORKERS))
        total = len(cards)
        results: list[dict] = []
        done = 0

        self._log(f"Scraping profundo de {total} publicaciones con {workers} workers...")

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self.scrape_detail, c): c for c in cards}
            for fut in as_completed(futures):
                if self._cancelled():
                    break
                try:
                    results.append(fut.result())
                except Exception as exc:  # noqa: BLE001 - no queremos que un fallo aborte todo
                    card = futures[fut]
                    self._log(f"  · fallo en {card['url']}: {exc}")
                    results.append({**card, "detail_ok": False})
                done += 1
                if progress:
                    progress("detalle", done, total)

        return results
