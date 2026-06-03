"""
gui.py
======
Interfaz de escritorio con CustomTkinter.

Orquesta todo el flujo:
    criterios -> scraping listado -> scraping profundo concurrente ->
    cálculo de métricas -> filtros -> exportación a Excel.

El scraping corre en un hilo aparte para no congelar la interfaz; las
actualizaciones de la UI se programan siempre con `self.after(...)`.
"""

from __future__ import annotations

import difflib
import io
import os
import queue
import threading
import traceback
import unicodedata
import webbrowser
from concurrent.futures import ThreadPoolExecutor

import customtkinter as ctk
import requests
from PIL import Image

from . import analysis, config, exporter, fx
from .scraper import ArgenpropScraper, SearchCriteria

# Tamaño del thumbnail en la galería de resultados.
THUMB_SIZE = (168, 120)
# Cuántas tarjetas se muestran por tanda.
RESULTS_BATCH = 30

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


def _to_number(text: str):
    """Convierte el texto de un entry a número o None si está vacío/ inválido."""
    text = (text or "").strip().replace(".", "").replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _norm(text: str) -> str:
    """Minúsculas y sin acentos, para buscar ubicaciones de forma tolerante."""
    s = (text or "").strip().lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Scraper Argenprop — Buscador de Oportunidades")
        self.geometry("1040x760")
        self.minsize(960, 680)

        # Estado
        self.scraper: ArgenpropScraper | None = None
        self.worker_thread: threading.Thread | None = None
        self.log_queue: "queue.Queue[tuple[str, object]]" = queue.Queue()

        # Estado de la galería de resultados
        self.results: list[dict] = []          # terminadas, ordenadas por score
        self.results_shown = 0
        self.last_excel_path: str | None = None
        self._img_session = requests.Session()
        self._img_session.headers.update({"User-Agent": config.USER_AGENT})
        self._img_pool = ThreadPoolExecutor(max_workers=6)
        self._img_refs: list[ctk.CTkImage] = []  # refs para que no las junte el GC
        self._results_gen = 0                  # generación, para descartar cargas viejas

        # Variables de control
        self.var_operation = ctk.StringVar(value="Venta")
        self.var_currency = ctk.StringVar(value="USD")
        self.var_types: dict[str, ctk.BooleanVar] = {}
        self.var_province = ctk.StringVar(value="CABA")
        self.var_loc_filter = ctk.StringVar(value="")
        self.location_vars: dict[str, ctk.BooleanVar] = {}
        self.location_checkboxes: list[tuple[str, ctk.CTkCheckBox]] = []

        self._build_layout()
        self._build_locations("CABA")
        self.after(100, self._drain_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        """Cierre prolijo: corta descargas de imágenes pendientes."""
        try:
            self._img_pool.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        self.destroy()

    # ===================================================================== #
    #  Construcción de la interfaz
    # ===================================================================== #
    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ----- Panel izquierdo: criterios (scrollable) -----
        self.left = ctk.CTkScrollableFrame(self, width=470, label_text="Criterios de búsqueda")
        self.left.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=12)

        self._build_operation(self.left)
        self._build_types(self.left)
        self._build_province(self.left)
        self._build_location_panel(self.left)
        self._build_filters(self.left)
        self._build_workers(self.left)

        # ----- Panel derecho: acciones + log -----
        self.right = ctk.CTkFrame(self)
        self.right.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
        self.right.grid_rowconfigure(3, weight=1)
        self.right.grid_columnconfigure(0, weight=1)

        self._build_actions(self.right)

    def _section(self, parent, title: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=10, pady=(8, 4)
        )
        return frame

    def _build_operation(self, parent) -> None:
        frame = self._section(parent, "Operación y moneda")
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 4))
        for op in config.OPERATIONS:
            ctk.CTkRadioButton(
                row, text=op, variable=self.var_operation, value=op,
                command=self._on_operation_change,
            ).pack(side="left", padx=(0, 16))

        cur_row = ctk.CTkFrame(frame, fg_color="transparent")
        cur_row.pack(fill="x", padx=10, pady=(0, 2))
        ctk.CTkLabel(cur_row, text="Moneda del precio que ingresás:").pack(side="left", padx=(0, 10))
        for cur in config.CURRENCIES:
            ctk.CTkRadioButton(
                cur_row, text=cur, variable=self.var_currency, value=cur
            ).pack(side="left", padx=(0, 16))

        ctk.CTkLabel(
            frame, text="El precio se compara en ambas monedas usando el dólar "
            "oficial: una propiedad en pesos que al cambio entra en tu rango, aparece.",
            font=ctk.CTkFont(size=11), text_color="gray",
            wraplength=430, justify="left", anchor="w",
        ).pack(fill="x", padx=10, pady=(0, 8))

    def _on_operation_change(self) -> None:
        """Al cambiar la operación, sugiere la moneda habitual (editable)."""
        default_cur = config.DEFAULT_CURRENCY_BY_OPERATION.get(self.var_operation.get())
        if default_cur:
            self.var_currency.set(default_cur)

    def _build_types(self, parent) -> None:
        frame = self._section(parent, "Tipo de propiedad")
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 8))
        for name in config.PROPERTY_TYPES:
            var = ctk.BooleanVar(value=(name == "Departamento"))
            self.var_types[name] = var
            ctk.CTkCheckBox(row, text=name, variable=var).pack(side="left", padx=(0, 16))

    def _build_province(self, parent) -> None:
        frame = self._section(parent, "Provincia")
        ctk.CTkOptionMenu(
            frame,
            values=list(config.LOCATIONS.keys()),
            variable=self.var_province,
            command=self._on_province_change,
        ).pack(fill="x", padx=10, pady=(0, 8))

    def _build_location_panel(self, parent) -> None:
        frame = self._section(parent, "Ubicación (selección múltiple)")

        # Buscador de texto: indispensable con 135 partidos cargados.
        search = ctk.CTkEntry(
            frame, textvariable=self.var_loc_filter,
            placeholder_text="🔎 Filtrar ubicación… (ej: tigre, villa)",
        )
        search.pack(fill="x", padx=10, pady=(0, 4))
        self.var_loc_filter.trace_add("write", lambda *_: self._filter_locations())

        # Botones de ayuda
        helper = ctk.CTkFrame(frame, fg_color="transparent")
        helper.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkButton(helper, text="Seleccionar visibles", width=140, height=26,
                      command=lambda: self._set_all_locations(True)).pack(side="left", padx=(0, 6))
        ctk.CTkButton(helper, text="Limpiar visibles", width=120, height=26,
                      command=lambda: self._set_all_locations(False)).pack(side="left")

        self.loc_count_label = ctk.CTkLabel(
            frame, text="", anchor="w", font=ctk.CTkFont(size=11)
        )
        self.loc_count_label.pack(fill="x", padx=10, pady=(0, 2))

        self.location_container = ctk.CTkScrollableFrame(frame, height=180)
        self.location_container.pack(fill="x", padx=10, pady=(0, 8))

    def _build_locations(self, province: str) -> None:
        """(Re)construye los checkboxes de ubicaciones para la provincia dada."""
        for _, cb in self.location_checkboxes:
            cb.destroy()
        self.location_checkboxes.clear()
        self.location_vars.clear()

        for name in config.LOCATIONS.get(province, {}):
            var = ctk.BooleanVar(value=False)
            self.location_vars[name] = var
            cb = ctk.CTkCheckBox(
                self.location_container, text=name, variable=var,
                command=self._refresh_loc_count,
            )
            self.location_checkboxes.append((name, cb))
        self._filter_locations()  # ubica los checkboxes según el filtro actual

    def _matching_locations(self, query: str) -> list[str]:
        """
        Ubicaciones que matchean el texto buscado (ya normalizado), tolerante:

          1. Sin acentos ni mayúsculas: "moron" encuentra "Morón".
          2. Por substring: "villa" lista todas las Villa *.
          3. Si nada matchea por substring, cae a un acercamiento DIFUSO
             (tolera errores de tipeo: "belgrno" -> "Belgrano").

        Al tildar el checkbox se selecciona el nombre canónico, así que la
        ubicación queda "autocorregida" sola.
        """
        names = [name for name, _ in self.location_checkboxes]
        if not query:
            return names

        subs = [name for name in names if query in _norm(name)]
        if subs:
            return subs

        scored: list[tuple[float, str]] = []
        for name in names:
            nn = _norm(name)
            ratio = max(
                [difflib.SequenceMatcher(None, query, nn).ratio()]
                + [difflib.SequenceMatcher(None, query, w).ratio() for w in nn.split()]
            )
            if ratio >= 0.6:
                scored.append((ratio, name))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [name for _, name in scored]

    def _filter_locations(self) -> None:
        """Muestra solo las ubicaciones que matchean el texto del buscador.

        Las selecciones se conservan aunque una ubicación quede oculta: así se
        puede buscar, tildar, volver a buscar y seguir tildando.
        """
        matches = self._matching_locations(_norm(self.var_loc_filter.get()))
        matchset = set(matches)
        cb_by_name = dict(self.location_checkboxes)
        for name, cb in self.location_checkboxes:
            if name not in matchset:
                cb.grid_remove()
        for i, name in enumerate(matches):
            cb_by_name[name].grid(row=i // 2, column=i % 2, sticky="w", padx=6, pady=3)
        self._refresh_loc_count(len(matches))

    def _refresh_loc_count(self, visible: int | None = None) -> None:
        total = len(self.location_checkboxes)
        if visible is None:
            visible = len(self._matching_locations(_norm(self.var_loc_filter.get())))
        selected = sum(1 for v in self.location_vars.values() if v.get())
        self.loc_count_label.configure(
            text=f"{visible}/{total} visibles · {selected} seleccionadas"
        )

    def _on_province_change(self, province: str) -> None:
        self.var_loc_filter.set("")  # reset del filtro al cambiar de provincia
        self._build_locations(province)

    def _set_all_locations(self, value: bool) -> None:
        """Aplica a las ubicaciones VISIBLES (las que pasan el filtro actual)."""
        for name in self._matching_locations(_norm(self.var_loc_filter.get())):
            self.location_vars[name].set(value)
        self._refresh_loc_count()

    def _build_filters(self, parent) -> None:
        frame = self._section(parent, "Filtros de búsqueda")
        ctk.CTkLabel(
            frame, text="Todos opcionales. Lo que dejes vacío no filtra.",
            font=ctk.CTkFont(size=11), text_color="gray", anchor="w",
        ).pack(fill="x", padx=10, pady=(0, 2))
        grid = ctk.CTkFrame(frame, fg_color="transparent")
        grid.pack(fill="x", padx=10, pady=(0, 8))
        grid.grid_columnconfigure((1, 3), weight=1)

        self.entries: dict[str, ctk.CTkEntry] = {}

        def add_range(row, label, key_min, key_max):
            ctk.CTkLabel(grid, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=3)
            e_min = ctk.CTkEntry(grid, placeholder_text="mín", width=90)
            e_min.grid(row=row, column=1, sticky="ew", padx=(0, 6), pady=3)
            e_max = ctk.CTkEntry(grid, placeholder_text="máx", width=90)
            e_max.grid(row=row, column=2, columnspan=2, sticky="ew", pady=3)
            self.entries[key_min] = e_min
            self.entries[key_max] = e_max

        def add_single(row, label, key):
            ctk.CTkLabel(grid, text=label).grid(row=row, column=0, sticky="w", padx=(0, 6), pady=3)
            e = ctk.CTkEntry(grid, placeholder_text="máx", width=90)
            e.grid(row=row, column=1, columnspan=3, sticky="ew", pady=3)
            self.entries[key] = e

        add_range(0, "Precio (en moneda elegida)", "price_min", "price_max")
        add_range(1, "Sup. cubierta (m²)", "m2_covered_min", "m2_covered_max")
        add_range(2, "Sup. total (m²)", "m2_total_min", "m2_total_max")
        add_range(3, "Ambientes", "rooms_min", "rooms_max")
        add_range(4, "Dormitorios", "bedrooms_min", "bedrooms_max")
        add_single(5, "Expensas (máx)", "expenses_max")
        add_single(6, "Antigüedad (máx, años)", "age_max")

    def _build_workers(self, parent) -> None:
        frame = self._section(parent, "Velocidad de descarga")

        # Explicación en lenguaje simple: qué hace y por qué existe esta perilla.
        help_text = (
            "Cuántas publicaciones se descargan AL MISMO TIEMPO. Más = termina "
            "antes, pero satura: Argenprop puede frenarte y, en una PC lenta, la "
            "app puede quedar en «no responde» un rato (no se rompe, sigue y "
            "termina). 12–15 es un buen equilibrio: bajalo si se traba o ves "
            "errores; subilo si va lento y todo viene funcionando."
        )
        ctk.CTkLabel(
            frame, text=help_text, font=ctk.CTkFont(size=11), text_color="gray",
            wraplength=430, justify="left", anchor="w",
        ).pack(fill="x", padx=10, pady=(0, 6))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 10))
        self.var_workers = ctk.IntVar(value=config.DEFAULT_WORKERS)
        self.lbl_workers = ctk.CTkLabel(row, text=str(config.DEFAULT_WORKERS), width=30)

        ctk.CTkLabel(row, text="Suave", font=ctk.CTkFont(size=11),
                     text_color="gray").pack(side="left", padx=(0, 6))
        slider = ctk.CTkSlider(
            row,
            from_=config.MIN_WORKERS,
            to=config.MAX_WORKERS,
            number_of_steps=config.MAX_WORKERS - config.MIN_WORKERS,
            variable=self.var_workers,
            command=lambda v: self.lbl_workers.configure(text=str(int(float(v)))),
        )
        slider.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkLabel(row, text="Rápido", font=ctk.CTkFont(size=11),
                     text_color="gray").pack(side="left", padx=(0, 8))
        self.lbl_workers.pack(side="left")

    def _build_actions(self, parent) -> None:
        # Botones
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        btn_row.grid_columnconfigure((0, 1), weight=1)
        btn_row.grid_columnconfigure(2, weight=0)

        self.btn_search = ctk.CTkButton(
            btn_row, text="🔎  Buscar y exportar", height=44,
            font=ctk.CTkFont(size=15, weight="bold"), command=self._start_search
        )
        self.btn_search.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.btn_cancel = ctk.CTkButton(
            btn_row, text="Cancelar", height=44, fg_color="#8B2E2E",
            hover_color="#6E2424", command=self._cancel_search, state="disabled"
        )
        self.btn_cancel.grid(row=0, column=1, sticky="ew", padx=(6, 6))

        self.btn_excel = ctk.CTkButton(
            btn_row, text="📂 Excel", height=44, width=90, command=self._open_excel,
            state="disabled", fg_color="#2E7D46", hover_color="#256138",
        )
        self.btn_excel.grid(row=0, column=2, sticky="ew")

        # Estado / progreso
        self.status_label = ctk.CTkLabel(parent, text="Listo.", anchor="w")
        self.status_label.grid(row=1, column=0, sticky="ew", padx=12)

        self.progress = ctk.CTkProgressBar(parent)
        self.progress.set(0)
        self.progress.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 8))

        # Galería de resultados (reemplaza al log)
        self.results_frame = ctk.CTkScrollableFrame(
            parent, label_text="Mejores resultados (por score)"
        )
        self.results_frame.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.results_frame.grid_columnconfigure(0, weight=1)
        self._results_placeholder()

    def _results_placeholder(self, text: str | None = None) -> None:
        """Muestra un mensaje centrado cuando todavía no hay resultados."""
        for child in self.results_frame.winfo_children():
            child.destroy()
        msg = text or (
            "Configurá los criterios y presioná «Buscar y exportar».\n"
            "Acá vas a ver las mejores propiedades, ordenadas por score."
        )
        ctk.CTkLabel(
            self.results_frame, text=msg, text_color="gray", justify="center",
        ).grid(row=0, column=0, pady=40, padx=10)

    # ===================================================================== #
    #  Logging / progreso (thread-safe vía cola)
    # ===================================================================== #
    def _log(self, msg: str) -> None:
        self.log_queue.put(("log", msg))

    def _set_status(self, msg: str) -> None:
        self.log_queue.put(("status", msg))

    def _set_progress(self, value: float) -> None:
        self.log_queue.put(("progress", value))

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "log":
                    print(str(payload), flush=True)  # detalle al terminal
                elif kind == "status":
                    self.status_label.configure(text=str(payload))
                elif kind == "progress":
                    self.progress.set(float(payload))
                elif kind == "done":
                    self._on_finished(payload)
        except queue.Empty:
            pass
        self.after(120, self._drain_queue)

    # ===================================================================== #
    #  Recolección de criterios desde la UI
    # ===================================================================== #
    def _collect_criteria(self) -> tuple[SearchCriteria, analysis.Filters] | None:
        province = self.var_province.get()
        loc_map = config.LOCATIONS.get(province, {})

        selected_locations = [
            loc_map[name] for name, var in self.location_vars.items() if var.get()
        ]
        selected_types = [
            config.PROPERTY_TYPES[name] for name, var in self.var_types.items() if var.get()
        ]

        if not selected_types:
            self._set_status("⚠ Seleccioná al menos un tipo de propiedad.")
            return None
        if not selected_locations:
            self._set_status("⚠ Seleccioná al menos una ubicación.")
            return None

        e = self.entries
        # El precio se ingresa en la moneda elegida; la conversión a USD se hace
        # en el hilo de trabajo (necesita la cotización online). Acá sólo lo
        # guardamos crudo; los bounds de USD se completan en _run_pipeline.
        self._price_input = (
            self.var_currency.get(),               # "USD" / "Pesos"
            _to_number(e["price_min"].get()),
            _to_number(e["price_max"].get()),
        )

        criteria = SearchCriteria(
            operation=config.OPERATIONS[self.var_operation.get()],
            property_types=selected_types,
            location_slugs=selected_locations,
            workers=int(self.var_workers.get()),
        )

        filters = analysis.Filters(
            m2_covered_min=_to_number(e["m2_covered_min"].get()),
            m2_covered_max=_to_number(e["m2_covered_max"].get()),
            m2_total_min=_to_number(e["m2_total_min"].get()),
            m2_total_max=_to_number(e["m2_total_max"].get()),
            rooms_min=_to_number(e["rooms_min"].get()),
            rooms_max=_to_number(e["rooms_max"].get()),
            bedrooms_min=_to_number(e["bedrooms_min"].get()),
            bedrooms_max=_to_number(e["bedrooms_max"].get()),
            expenses_max=_to_number(e["expenses_max"].get()),
            age_max=_to_number(e["age_max"].get()),
        )
        return criteria, filters

    # ===================================================================== #
    #  Control de la búsqueda
    # ===================================================================== #
    def _start_search(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            return
        collected = self._collect_criteria()
        if collected is None:
            return
        criteria, filters = collected

        self.btn_search.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.btn_excel.configure(state="disabled")
        self.progress.set(0)

        # Limpiar la galería anterior (e invalidar cargas de imágenes en vuelo).
        self._results_gen += 1
        self.results = []
        self.results_shown = 0
        self._img_refs.clear()
        self._results_placeholder("Buscando… los resultados aparecerán al terminar.")

        self.scraper = ArgenpropScraper(log=self._log)
        self.worker_thread = threading.Thread(
            target=self._run_pipeline, args=(criteria, filters), daemon=True
        )
        self.worker_thread.start()

    def _cancel_search(self) -> None:
        if self.scraper:
            self.scraper.cancel()
            self._set_status("Cancelando…")

    # ===================================================================== #
    #  Pipeline completo (corre en hilo aparte)
    # ===================================================================== #
    def _run_pipeline(self, criteria: SearchCriteria, filters: analysis.Filters) -> None:
        try:
            # --- 0. Cotización del dólar y rango de precio en USD ---
            self._set_status("Consultando cotización del dólar…")
            rate = fx.get_official_usd(self._log)
            cur_label, raw_min, raw_max = self._price_input
            # USD -> tal cual; Pesos -> a USD dividiendo por la cotización.
            to_usd = (lambda v: v) if cur_label == "USD" else (lambda v: v / rate)
            usd_min = to_usd(raw_min) if raw_min else None
            usd_max = to_usd(raw_max) if raw_max else None

            criteria.usd_rate = rate
            criteria.price_min_usd = int(usd_min) if usd_min else None
            criteria.price_max_usd = int(usd_max) if usd_max else None
            filters.price_min = usd_min
            filters.price_max = usd_max
            if usd_min or usd_max:
                self._log(
                    f"Rango de precio en USD: "
                    f"{int(usd_min) if usd_min else '–'} a "
                    f"{int(usd_max) if usd_max else '–'} "
                    f"(se busca en dólares y en pesos)."
                )

            # --- 1. Listado ---
            self._set_status("Recolectando listado…")

            def listing_progress(stage, current, total):
                self._set_status(f"Listado: página {current}/{total}")
                self._set_progress((current / max(total, 1)) * 0.30)

            cards = self.scraper.collect_listing(criteria, progress=listing_progress)
            if not cards:
                self._set_status("No se encontraron publicaciones.")
                self.log_queue.put(("done", None))
                return
            if self.scraper._cancelled():
                self.log_queue.put(("done", None))
                return

            # --- 2. Scraping profundo concurrente ---
            self._set_status(f"Analizando {len(cards)} publicaciones…")

            def detail_progress(stage, done, total):
                self._set_status(f"Detalle: {done}/{total} publicaciones")
                self._set_progress(0.30 + (done / max(total, 1)) * 0.55)

            records = self.scraper.scrape_details_parallel(
                cards, criteria.workers, progress=detail_progress
            )

            # --- 3. Métricas + filtros + pozo ---
            self._set_status("Calculando métricas y aplicando filtros…")
            self._set_progress(0.90)
            grouped = analysis.process(records, filters, rate)
            ok, pozo, financiado = grouped["ok"], grouped["pozo"], grouped["financiado"]
            self._log(
                f"Terminadas: {len(ok)} · En pozo: {len(pozo)} · "
                f"Financiadas: {len(financiado)}"
            )

            # --- 4. Exportar ---
            self._set_status("Generando Excel…")
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            out_dir = os.path.join(base_dir, "resultados")
            os.makedirs(out_dir, exist_ok=True)
            from datetime import datetime
            fname = f"argenprop_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
            path = os.path.join(out_dir, fname)
            exporter.export(ok, pozo, financiado, path)

            # Las mejores primero, para la galería.
            ranked = sorted(
                ok, key=lambda r: (r.get("score") is None, -(r.get("score") or 0))
            )

            self._set_progress(1.0)
            self.log_queue.put((
                "done",
                {
                    "path": path, "ok": len(ok), "pozo": len(pozo),
                    "financiado": len(financiado), "results": ranked,
                },
            ))

        except Exception:  # noqa: BLE001 - mostramos el error al usuario
            self._log("ERROR:\n" + traceback.format_exc())
            self._set_status("Ocurrió un error (ver consola).")
            self.log_queue.put(("done", None))

    def _on_finished(self, payload) -> None:
        self.btn_search.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        if not payload:
            if not self.results:
                self._results_placeholder("Sin resultados para mostrar.")
            return

        self.status_label.configure(
            text=f"✔ Listo · {payload['ok']} terminadas · "
            f"{payload['pozo']} en pozo · {payload.get('financiado', 0)} financiadas "
            f"· Excel guardado."
        )
        self.last_excel_path = payload["path"]
        self.btn_excel.configure(state="normal")

        self.results = payload["results"]
        self.results_shown = 0
        self._show_results()

    # ===================================================================== #
    #  Galería de resultados
    # ===================================================================== #
    def _show_results(self) -> None:
        """(Re)dibuja la galería desde cero y muestra la primera tanda."""
        for child in self.results_frame.winfo_children():
            child.destroy()
        self._img_refs.clear()
        self.results_shown = 0
        if not self.results:
            self._results_placeholder("Ninguna propiedad pasó los filtros.")
            return
        self._render_more()

    def _render_more(self) -> None:
        """Dibuja la siguiente tanda de tarjetas y reubica el botón 'ver más'."""
        if hasattr(self, "_more_btn") and self._more_btn.winfo_exists():
            self._more_btn.destroy()

        start = self.results_shown
        end = min(start + RESULTS_BATCH, len(self.results))
        for idx in range(start, end):
            self._render_card(self.results[idx], idx + 1)
        self.results_shown = end

        remaining = len(self.results) - self.results_shown
        if remaining > 0:
            self._more_btn = ctk.CTkButton(
                self.results_frame,
                text=f"Ver más  ({remaining} restantes)",
                command=self._render_more,
            )
            self._more_btn.grid(row=self.results_shown, column=0, pady=10, padx=20, sticky="ew")

    def _render_card(self, rec: dict, rank: int) -> None:
        """Una tarjeta: foto + datos clave, clickeable para abrir el aviso."""
        card = ctk.CTkFrame(self.results_frame)
        card.grid(row=rank - 1, column=0, sticky="ew", padx=4, pady=4)
        card.grid_columnconfigure(1, weight=1)

        # --- Foto (placeholder hasta que cargue) ---
        photo = ctk.CTkLabel(card, text="📷", width=THUMB_SIZE[0], height=THUMB_SIZE[1],
                             fg_color="#2A2D2E", corner_radius=6)
        photo.grid(row=0, column=0, rowspan=2, padx=8, pady=8)
        self._load_thumb(rec.get("card_image"), photo)

        # --- Encabezado: rank + score + precio ---
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.grid(row=0, column=1, sticky="new", padx=(0, 10), pady=(8, 0))
        head.grid_columnconfigure(1, weight=1)

        score = rec.get("score")
        ctk.CTkLabel(
            head, text=f"#{rank}  ★ {score:.1f}" if score is not None else f"#{rank}",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=_score_color(score),
        ).grid(row=0, column=0, sticky="w")

        if rec.get("financed"):
            ctk.CTkLabel(
                head, text="💳 Contado", font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#D29922",
            ).grid(row=0, column=1, sticky="w", padx=(10, 0))

        ctk.CTkLabel(
            head, text=self._price_text(rec), font=ctk.CTkFont(size=14, weight="bold"),
            anchor="e",
        ).grid(row=0, column=2, sticky="e")

        # --- Cuerpo: título, zona y datos ---
        title = (rec.get("title") or rec.get("card_title") or "Sin título").strip()
        ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w", justify="left", wraplength=360,
        ).grid(row=1, column=1, sticky="nw", padx=(0, 10))

        ctk.CTkLabel(
            card, text=self._detail_text(rec), text_color="gray",
            anchor="w", justify="left", wraplength=380,
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(0, 8))

        # Toda la tarjeta abre el aviso en el navegador.
        url = rec.get("url")
        if url:
            self._bind_open(card, url)

    @staticmethod
    def _price_text(rec: dict) -> str:
        price, cur = rec.get("price"), rec.get("currency") or ""
        usd = rec.get("price_usd")
        if price is None:
            return "Precio s/d"
        symbol = "US$" if cur == "USD" else "$"
        base = f"{symbol} {price:,.0f}"
        if rec.get("price_converted") and usd:
            base += f"  (≈ US$ {usd:,.0f})"
        return base

    @staticmethod
    def _detail_text(rec: dict) -> str:
        kind = {"departamento": "Depto", "ph": "PH", "casa": "Casa"}.get(
            rec.get("property_kind"), ""
        )
        bits = [b for b in [kind, rec.get("neighborhood")] if b]
        if rec.get("m2_covered"):
            bits.append(f"{rec['m2_covered']:.0f} m²")
        if rec.get("rooms"):
            bits.append(f"{rec['rooms']:.0f} amb")
        exp = rec.get("expenses") or rec.get("expenses_est")
        if exp:
            tag = "" if rec.get("expenses") else " (est)"
            bits.append(f"exp ${exp:,.0f}{tag}")
        if rec.get("usd_m2_covered"):
            bits.append(f"US$ {rec['usd_m2_covered']:,.0f}/m²")
        return "   ·   ".join(bits)

    def _bind_open(self, widget, url: str) -> None:
        """Hace clickeable un widget y todos sus hijos (abre el aviso)."""
        widget.configure(cursor="hand2")
        widget.bind("<Button-1>", lambda _e: webbrowser.open(url))
        for child in widget.winfo_children():
            self._bind_open(child, url)

    def _load_thumb(self, url: str | None, label: ctk.CTkLabel) -> None:
        """Descarga el thumbnail en segundo plano y lo coloca al terminar."""
        if not url:
            return
        gen = self._results_gen

        def work():
            try:
                resp = self._img_session.get(url, timeout=10)
                if resp.status_code != 200:
                    return
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            except Exception:
                return
            # El CTkImage se crea en el hilo principal (toca Tk).
            self.after(0, lambda: self._place_thumb(label, img, gen))

        self._img_pool.submit(work)

    def _place_thumb(self, label: ctk.CTkLabel, pil_img, gen: int) -> None:
        # Si arrancó otra búsqueda, descartamos la imagen vieja.
        if gen != self._results_gen:
            return
        try:
            if not label.winfo_exists():
                return
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=THUMB_SIZE)
            self._img_refs.append(ctk_img)
            label.configure(image=ctk_img, text="")
        except Exception:
            pass

    def _open_excel(self) -> None:
        if self.last_excel_path:
            try:
                os.startfile(os.path.dirname(self.last_excel_path))  # Windows
            except Exception:
                pass


def _score_color(score) -> str:
    """Verde si el score es alto, ámbar medio, gris si bajo/None."""
    if score is None:
        return "gray"
    if score >= 70:
        return "#3FB950"
    if score >= 45:
        return "#D29922"
    return "#C9D1D9"


def run() -> None:
    app = App()
    app.mainloop()
