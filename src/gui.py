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

import os
import queue
import threading
import traceback
import unicodedata

import customtkinter as ctk

from . import analysis, config, exporter
from .scraper import ArgenpropScraper, SearchCriteria

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
        cur_row.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(cur_row, text="Moneda del precio:").pack(side="left", padx=(0, 10))
        for cur in config.CURRENCIES:
            ctk.CTkRadioButton(
                cur_row, text=cur, variable=self.var_currency, value=cur
            ).pack(side="left", padx=(0, 16))

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

    def _filter_locations(self) -> None:
        """Muestra solo las ubicaciones que matchean el texto del buscador.

        Las selecciones se conservan aunque una ubicación quede oculta: así se
        puede buscar, tildar, volver a buscar y seguir tildando.
        """
        query = _norm(self.var_loc_filter.get())
        visible = 0
        for name, cb in self.location_checkboxes:
            if query in _norm(name):
                cb.grid(row=visible // 2, column=visible % 2, sticky="w", padx=6, pady=3)
                visible += 1
            else:
                cb.grid_remove()
        self._refresh_loc_count(visible)

    def _refresh_loc_count(self, visible: int | None = None) -> None:
        total = len(self.location_checkboxes)
        if visible is None:
            query = _norm(self.var_loc_filter.get())
            visible = sum(1 for name, _ in self.location_checkboxes if query in _norm(name))
        selected = sum(1 for v in self.location_vars.values() if v.get())
        self.loc_count_label.configure(
            text=f"{visible}/{total} visibles · {selected} seleccionadas"
        )

    def _on_province_change(self, province: str) -> None:
        self.var_loc_filter.set("")  # reset del filtro al cambiar de provincia
        self._build_locations(province)

    def _set_all_locations(self, value: bool) -> None:
        """Aplica a las ubicaciones VISIBLES (las que pasan el filtro actual)."""
        query = _norm(self.var_loc_filter.get())
        for name, var in self.location_vars.items():
            if query in _norm(name):
                var.set(value)
        self._refresh_loc_count()

    def _build_filters(self, parent) -> None:
        frame = self._section(parent, "Filtros de búsqueda")
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
        frame = self._section(parent, "Velocidad (workers concurrentes)")
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 10))
        self.var_workers = ctk.IntVar(value=config.DEFAULT_WORKERS)
        self.lbl_workers = ctk.CTkLabel(row, text=str(config.DEFAULT_WORKERS), width=30)
        slider = ctk.CTkSlider(
            row,
            from_=config.MIN_WORKERS,
            to=config.MAX_WORKERS,
            number_of_steps=config.MAX_WORKERS - config.MIN_WORKERS,
            variable=self.var_workers,
            command=lambda v: self.lbl_workers.configure(text=str(int(float(v)))),
        )
        slider.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.lbl_workers.pack(side="left")

    def _build_actions(self, parent) -> None:
        # Botones
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        self.btn_search = ctk.CTkButton(
            btn_row, text="🔎  Buscar y exportar", height=44,
            font=ctk.CTkFont(size=15, weight="bold"), command=self._start_search
        )
        self.btn_search.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.btn_cancel = ctk.CTkButton(
            btn_row, text="Cancelar", height=44, fg_color="#8B2E2E",
            hover_color="#6E2424", command=self._cancel_search, state="disabled"
        )
        self.btn_cancel.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        # Estado / progreso
        self.status_label = ctk.CTkLabel(parent, text="Listo.", anchor="w")
        self.status_label.grid(row=1, column=0, sticky="ew", padx=12)

        self.progress = ctk.CTkProgressBar(parent)
        self.progress.set(0)
        self.progress.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 8))

        # Log
        self.log_box = ctk.CTkTextbox(parent, wrap="word")
        self.log_box.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.log_box.insert("end", "Configurá los criterios y presioná «Buscar y exportar».\n")
        self.log_box.configure(state="disabled")

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
                    self.log_box.configure(state="normal")
                    self.log_box.insert("end", str(payload) + "\n")
                    self.log_box.see("end")
                    self.log_box.configure(state="disabled")
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
        price_min = _to_number(e["price_min"].get())
        price_max = _to_number(e["price_max"].get())

        criteria = SearchCriteria(
            operation=config.OPERATIONS[self.var_operation.get()],
            property_types=selected_types,
            location_slugs=selected_locations,
            currency=config.CURRENCIES[self.var_currency.get()],
            price_min=int(price_min) if price_min else None,
            price_max=int(price_max) if price_max else None,
            workers=int(self.var_workers.get()),
        )

        filters = analysis.Filters(
            price_min=price_min,
            price_max=price_max,
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
        self.progress.set(0)

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
            grouped = analysis.process(records, filters)
            ok, pozo = grouped["ok"], grouped["pozo"]
            self._log(f"Terminadas (tras filtros): {len(ok)} · En pozo: {len(pozo)}")

            # --- 4. Exportar ---
            self._set_status("Generando Excel…")
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            out_dir = os.path.join(base_dir, "resultados")
            os.makedirs(out_dir, exist_ok=True)
            from datetime import datetime
            fname = f"argenprop_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
            path = os.path.join(out_dir, fname)
            exporter.export(ok, pozo, path)

            self._set_progress(1.0)
            self.log_queue.put(("done", path))

        except Exception:  # noqa: BLE001 - mostramos el error al usuario
            self._log("ERROR:\n" + traceback.format_exc())
            self._set_status("Ocurrió un error (ver log).")
            self.log_queue.put(("done", None))

    def _on_finished(self, path) -> None:
        self.btn_search.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        if path:
            self._set_status(f"✔ Listo. Excel generado.")
            self._log(f"\nArchivo: {path}")
            try:
                os.startfile(os.path.dirname(path))  # abre la carpeta (Windows)
            except Exception:
                pass
        else:
            if not (self.scraper and self.scraper._cancelled()):
                pass


def run() -> None:
    app = App()
    app.mainloop()
