# Scraper Argenprop — Buscador de Oportunidades Inmobiliarias

Aplicación de escritorio en Python para buscar propiedades en
[Argenprop](https://www.argenprop.com), analizar cada publicación,
detectar oportunidades y exportar todo a Excel ya depurado y rankeado.

## Características

- Búsqueda de **venta** o **alquiler**.
- Filtro por **tipo** (Departamento / Casa / PH), **provincia** y **ubicación** (selección múltiple).
- **Cobertura completa de zonas**: los 48 barrios de CABA, los **135 partidos** de Buenos Aires y las principales localidades de Córdoba (193 en total, orden alfabético). Como son muchas, la interfaz incluye un **buscador de texto** (tolera acentos y errores de tipeo) para filtrarlas.
- **Comparación en dólares**: convierte todos los precios a USD con el dólar oficial (DolarApi) y busca en **ambas monedas**, así una propiedad en pesos que al cambio entra en tu rango también aparece.
- Filtros avanzados: precio, superficie cubierta/total, ambientes, dormitorios, expensas y antigüedad.
- **Detección automática de páginas** (no usa un número fijo).
- **Scraping profundo** de cada publicación (precio, expensas, ambientes, dormitorios, baños, antigüedad, superficies, dirección y descripción).
- **Concurrencia** con `ThreadPoolExecutor` (10–20 workers configurables).
- Detección de propiedades **"en pozo"** (se separan del ranking principal).
- Cálculo de **USD/m²** y un **score de oportunidad** propio con **factor de zona**.
- **Estimación de expensas faltantes** según zona, tipo de propiedad y amenities detectados.
- **Galería de resultados** dentro de la app: al terminar, muestra las mejores propiedades (por score) con foto, datos clave y link, cargando de a tandas.
- **Manejo de precios tramposos**: detecta avisos con **financiación/cuotas** (donde el precio publicado es solo el anticipo) y, si la descripción lo dice, usa el precio de **contado**; descarta los avisos **sin precio** (no se pueden rankear) y deduplica publicaciones repetidas.
- Exportación a **Excel** con varias hojas de ranking, autofiltros, primera fila congelada, anchos ajustados, formatos de moneda/número y **URLs como hipervínculos** (un solo click).

## Instalación

```bash
pip install -r requirements.txt
```

Requiere **Python 3.13**.

## Uso (interfaz gráfica)

```bash
python main.py
```

1. Elegí operación, tipo de propiedad y provincia.
2. Elegí las ubicaciones (usá el **buscador** para filtrar; "Seleccionar/Limpiar visibles" opera sobre lo filtrado y las selecciones se conservan al seguir buscando).
3. Completá los filtros (todos opcionales).
4. Ajustá la velocidad (workers).
5. Presioná **Buscar y exportar**.

El Excel se genera en la carpeta `resultados/` y la app abre la carpeta al terminar.

## Uso (línea de comandos, sin GUI)

```bash
python cli.py --operacion venta --tipos departamentos casas \
              --ubicaciones palermo belgrano \
              --precio-min 50000 --precio-max 150000 \
              --expensas-max 200000 --workers 15
```

## Hojas del Excel

| Hoja | Orden |
|------|-------|
| `TODAS` | todas las terminadas |
| `OPORTUNIDADES` | USD/m² cubierto ascendente |
| `MAYOR_M2` | m² cubiertos descendente |
| `MENOR_PRECIO` | precio ascendente |
| `BAJAS_EXPENSAS` | expensas ascendente |
| `SCORE` | score descendente |
| `FINANCIADO` | avisos con cuotas/financiación (precio = anticipo) |
| `EN_POZO` | todas las detectadas en pozo |

## Score de oportunidad

El score combina tres componentes normalizados (0–100, relativos a la búsqueda)
y los multiplica por un **factor de zona**:

```
base  = w_valor·valor + w_tamaño·tamaño + w_expensas·expensas
score = base × factor_de_zona            (factor ≈ 0.75–1.25)
```

- **valor**: USD/m² cubierto invertido (más barato por m² = más puntos).
- **tamaño**: m² cubiertos (peso bajo a propósito).
- **expensas**: invertidas (más baratas = más puntos).
- **factor de zona**: calidad de la ubicación. Así, dos propiedades de igual
  precio y metros pero en zonas distintas (p. ej. una villa vs. Núñez) **no
  empatan**: la mejor zona gana.

Cuanto **mayor** el score, más interesante la oportunidad.

### Puntaje de zona (`Punt_Zona`, 0–10)

Configurable en `src/config.py`:

- `ZONE_SCORE_SOURCE = "market"` (por defecto): la calidad de cada zona se
  deriva del **USD/m² mediano** de esa zona dentro de la propia búsqueda (el
  mercado ya "precia" seguridad y servicios).
- `ZONE_SCORE_SOURCE = "override"`: usa la tabla editable `ZONE_SCORES`
  (puntajes 1–10 por barrio/partido) y cae a mercado para zonas no cargadas.

Pesos y rango del factor se ajustan en `SCORE_WEIGHTS`, `ZONE_FACTOR_MIN/MAX`.

> Como la normalización es **relativa al conjunto de resultados**, los scores
> comparan las propiedades de una misma búsqueda entre sí (no son absolutos
> entre búsquedas distintas).

## Estimación de expensas

Muchos avisos no publican las expensas. Tomarlas como nulas haría que esas
propiedades puntúen artificialmente alto, así que cuando faltan se **estiman**
(sin pisar el dato real, que se exporta aparte en `Expensas`):

- **Casa** → sin expensas comunes (0).
- **PH** → ~35 % de lo que pagaría un departamento equivalente.
- **Departamento** → tarifa **$/m² mediana de su zona** (tomada de los avisos
  que sí publican expensas) × m² cubiertos.

Además, no es lo mismo un edificio "pelado" que uno con **amenities**: se
detectan palabras como *pileta, gimnasio, SUM, seguridad, encargado, solárium,
spa, laundry*, etc., y se aplica un **factor 0.75 → 1.70** sobre la estimación
(más amenities = expensas más altas). El Excel marca el valor estimado en la
columna `Expensas est.` y muestra el tipo detectado en `Tipo`.

Parámetros editables en `src/config.py`: `EXPENSE_AMENITY_BASE`,
`EXPENSE_AMENITY_STEP`, `EXPENSE_AMENITY_MAX` y la lista `EXPENSE_AMENITY_GROUPS`.

## Moneda (USD / Pesos)

Todos los precios se comparan en **dólares**, usando la cotización del **dólar
oficial** (DolarApi). Esto permite que el filtro de precio funcione *entre*
monedas: si buscás hasta **50.000 USD**, también aparece una propiedad publicada
**en pesos** que, al cambio, cuesta ≤ 50.000 USD (y se destacan los alquileres
cotizados en dólares).

Cómo funciona:

1. Elegís en qué moneda ingresás el precio (**USD** o **Pesos**); el rango se
   lleva a USD con la cotización.
2. La búsqueda hace **dos pasadas** en Argenprop — una en dólares con el rango y
   otra en pesos con el rango convertido — y junta los resultados sin duplicar.
3. Cada aviso lleva un **`Precio USD`** canónico (columna del Excel). El `Score`
   y el `$/m²` se calculan en USD, así no se mezclan monedas. La celda `Moneda`
   se **resalta en verde cuando el aviso está en USD**.

La cotización se toma online en cada corrida (`src/fx.py`); si DolarApi no
responde, usa el respaldo `config.FX_USD_FALLBACK`. Para usar otro dólar (p. ej.
MEP) basta cambiar `config.DOLARAPI_URL` (`/v1/dolares/bolsa`).

En el **CLI**, `--moneda usd|pesos` indica en qué moneda van `--precio-min/max`.

## Vista de resultados (galería)

Al terminar la búsqueda, el panel derecho muestra las **mejores propiedades
ordenadas por score**, como un mini-Argenprop ya filtrado: foto, ranking +
score (con color), precio (y el `≈ US$` si es en pesos), zona, m², ambientes,
expensas y `US$/m²`. Se cargan de a **30** con un botón «Ver más», las fotos
bajan en segundo plano y **un click en la tarjeta abre el aviso** en el
navegador. El Excel se sigue generando (botón «📂 Excel»).

## Calidad de datos (precios)

Para que el ranking no se ensucie con precios tramposos:

- **Financiación / cuotas**: muchos avisos publican como precio el **anticipo**
  ("U$D 45.000 a la firma + 12 cuotas…") y parecen baratísimos. Se detectan y,
  si la descripción indica el **precio de contado**, se usa ese para el score
  (quedan marcados «💳 Contado»). Si no hay contado, se separan a la hoja
  `FINANCIADO`. No se confunde "apto crédito" (que es legítimo).
- **Sin precio**: los avisos sin precio se descartan (no se pueden rankear).
- **Duplicados**: se deduplica por URL y por contenido (misma propiedad
  republicada con otra URL).
- **Expensas**: se toman sólo cuando vienen con `$` (evita capturar los m² de la
  barra de avisos relacionados) y, si faltan, se estiman (ver arriba).

## Estructura

```
SCRAPER_ARGENPROP/
├── main.py            # entry point GUI
├── cli.py             # runner sin GUI
├── requirements.txt
├── resultados/        # salidas .xlsx (se crea sola)
└── src/
    ├── config.py      # operaciones, tipos, provincias, ubicaciones, keywords, scoring
    ├── fx.py          # cotización del dólar (DolarApi) y conversión a USD
    ├── scraper.py     # URL, paginación, cards, scraping profundo concurrente
    ├── analysis.py    # métricas, score, expensas, detección en pozo, filtros
    ├── exporter.py    # Excel multi-hoja con formato
    └── gui.py         # interfaz CustomTkinter
```

## Nota sobre los selectores

Los selectores de scraping (`listing__item`, `titlebar__price`,
`titlebar__expenses`, `section-description--content`, etc.) están centralizados
y son tolerantes a faltantes. Si Argenprop cambia su HTML, ajustar los
selectores en `src/scraper.py` y los slugs de ubicación en `src/config.py`.
