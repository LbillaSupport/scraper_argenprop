"""
config.py
=========
Datos de configuración estáticos: operaciones, tipos de propiedad,
provincias y sus ubicaciones (barrios / municipios) con el slug que
usa Argenprop en las URLs.

Pensado para ampliarse fácilmente: agregar una entrada al diccionario
correspondiente alcanza para que aparezca en la interfaz.
"""

# --------------------------------------------------------------------------- #
#  Operaciones
# --------------------------------------------------------------------------- #
# etiqueta visible -> slug usado en la URL
OPERATIONS = {
    "Venta": "venta",
    "Alquiler": "alquiler",
}

# Moneda del precio. etiqueta visible -> slug usado en la URL de Argenprop.
CURRENCIES = {
    "USD": "dolares",
    "Pesos": "pesos",
}

# Moneda sugerida por defecto según la operación.
DEFAULT_CURRENCY_BY_OPERATION = {
    "Venta": "USD",
    "Alquiler": "Pesos",
}

# --------------------------------------------------------------------------- #
#  Tipos de propiedad
# --------------------------------------------------------------------------- #
# etiqueta visible -> slug (en plural, como lo arma Argenprop)
PROPERTY_TYPES = {
    "Departamento": "departamentos",
    "Casa": "casas",
    "PH": "ph",
}

# --------------------------------------------------------------------------- #
#  Provincias + ubicaciones
# --------------------------------------------------------------------------- #
# Estructura:  PROVINCE -> { "Nombre visible": "slug-argenprop" }
LOCATIONS = {
    "CABA": {
        "Palermo": "palermo",
        "Belgrano": "belgrano",
        "Recoleta": "recoleta",
        "Núñez": "nunez",
        "Colegiales": "colegiales",
        "Coghlan": "coghlan",
        "Caballito": "caballito",
        "Villa Urquiza": "villa-urquiza",
        "Villa Crespo": "villa-crespo",
        "Almagro": "almagro",
        "Saavedra": "saavedra",
        "Flores": "flores",
        "Puerto Madero": "puerto-madero",
        "San Telmo": "san-telmo",
        "Barrio Norte": "barrio-norte",
        "Villa Devoto": "villa-devoto",
        "Villa del Parque": "villa-del-parque",
        "Chacarita": "chacarita",
        "Boedo": "boedo",
        "Parque Patricios": "parque-patricios",
        "Monserrat": "monserrat",
        "Balvanera": "balvanera",
        "Retiro": "retiro",
        "Constitución": "constitucion",
        "Versalles": "versalles",
    },
    "Buenos Aires": {
        "Vicente López": "vicente-lopez",
        "San Isidro": "san-isidro",
        "Tigre": "tigre",
        "San Fernando": "san-fernando",
        "Morón": "moron",
        "La Plata": "la-plata",
        "Quilmes": "quilmes",
        "Lomas de Zamora": "lomas-de-zamora",
        "Avellaneda": "avellaneda",
        "Lanús": "lanus",
        "Pilar": "pilar",
        "Escobar": "escobar",
        "San Miguel": "san-miguel",
        "Tres de Febrero": "tres-de-febrero",
        "La Matanza": "la-matanza",
        "Berazategui": "berazategui",
        "Florencio Varela": "florencio-varela",
        "Mar del Plata": "mar-del-plata",
    },
    "Córdoba": {
        "Córdoba Capital": "cordoba",
        "Villa Carlos Paz": "villa-carlos-paz",
        "Río Cuarto": "rio-cuarto",
        "Alta Gracia": "alta-gracia",
        "Villa Allende": "villa-allende",
        "Jesús María": "jesus-maria",
        "La Falda": "la-falda",
        "Villa María": "villa-maria",
        "Cosquín": "cosquin",
    },
}

# --------------------------------------------------------------------------- #
#  Detección de "en pozo"
# --------------------------------------------------------------------------- #
POZO_KEYWORDS = [
    "en pozo",
    "pozo",
    "preventa",
    "fideicomiso",
    "en construcción",
    "en construccion",
    "entrega estimada",
    "entrega 202",
    "emprendimiento",
]

# --------------------------------------------------------------------------- #
#  Parámetros de scraping
# --------------------------------------------------------------------------- #
BASE_URL = "https://www.argenprop.com"

# Cantidad de workers concurrentes para el scraping profundo (10–20).
DEFAULT_WORKERS = 15
MIN_WORKERS = 10
MAX_WORKERS = 20

# Cota de seguridad: nunca recorrer más páginas que esto aunque el sitio
# reporte más (evita búsquedas accidentales gigantescas).
MAX_PAGES_HARD_LIMIT = 200

REQUEST_TIMEOUT = 20  # segundos
REQUEST_RETRIES = 3

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# --------------------------------------------------------------------------- #
#  Scoring de oportunidad
# --------------------------------------------------------------------------- #
# El score final se calcula así (ver analysis.py):
#
#     base  = w_value·valor + w_size·tamaño + w_exp·expensas   (cada uno 0–100)
#     score = base · factor_de_zona                            (factor ≈ 0.75–1.25)
#
#   * valor    -> USD/m² cubierto, INVERTIDO (más barato por m² = más puntos).
#   * tamaño   -> m² cubiertos (más grande = más puntos), peso bajo a propósito.
#   * expensas -> INVERTIDO (más baratas = más puntos).
#   * factor_de_zona -> calidad de la zona (ver abajo): premia las buenas
#     ubicaciones y castiga las malas, aunque precio y metros sean iguales.
#
# Los pesos son editables y deben sumar 1.0 (no es obligatorio, pero conviene).
SCORE_WEIGHTS = {
    "value": 0.55,     # qué tan barato es el m²
    "size": 0.20,      # superficie cubierta
    "expenses": 0.25,  # expensas
}

# Rango del multiplicador de zona: una zona pésima multiplica por 0.75,
# una excelente por 1.25. Ampliá el rango si querés que la zona pese más.
ZONE_FACTOR_MIN = 0.75
ZONE_FACTOR_MAX = 1.25

# Fuente del puntaje de zona:
#   "market"   -> se deriva del USD/m² MEDIANO de cada zona en la propia
#                 búsqueda (el mercado ya "precia" seguridad y servicios).
#   "override" -> usa ZONE_SCORES (tabla de abajo) si la zona está cargada;
#                 si no lo está, cae automáticamente a "market".
ZONE_SCORE_SOURCE = "market"

# Mínimo de propiedades en una zona para confiar en su mediana de mercado.
# Por debajo de esto, la zona recibe un puntaje neutro (factor ≈ 1.0).
MIN_ZONE_SAMPLES = 2

# --------------------------------------------------------------------------- #
#  Puntajes de zona (1–10)  — SEMILLA EDITABLE
# --------------------------------------------------------------------------- #
# Valoración subjetiva (seguridad / costo de vida / servicios) por barrio o
# partido. Son SOLO un punto de partida: ajustalos a tu criterio.
# Únicamente se usan cuando ZONE_SCORE_SOURCE = "override".
# Las claves se comparan sin distinguir mayúsculas ni acentos.
ZONE_SCORES = {
    # ---- CABA ----
    "Puerto Madero": 10,
    "Recoleta": 9,
    "Palermo": 9,
    "Belgrano": 9,
    "Núñez": 9,
    "Barrio Norte": 9,
    "Colegiales": 8,
    "Coghlan": 8,
    "Villa Urquiza": 8,
    "Caballito": 8,
    "Saavedra": 7,
    "Villa del Parque": 7,
    "Villa Devoto": 7,
    "Chacarita": 7,
    "Villa Crespo": 7,
    "Versalles": 7,
    "Retiro": 6,
    "Almagro": 6,
    "Boedo": 6,
    "San Telmo": 6,
    "Flores": 5,
    "Parque Patricios": 5,
    "Monserrat": 5,
    "Balvanera": 5,
    "Constitución": 3,
    # ---- Buenos Aires (GBA) ----
    "Vicente López": 9,
    "San Isidro": 9,
    "San Fernando": 7,
    "Tigre": 7,
    "Pilar": 7,
    "La Plata": 7,
    "Mar del Plata": 7,
    "Escobar": 6,
    "Morón": 6,
    "Tres de Febrero": 6,
    "San Miguel": 6,
    "Quilmes": 5,
    "Avellaneda": 5,
    "Lanús": 5,
    "Lomas de Zamora": 5,
    "Berazategui": 5,
    "La Matanza": 4,
    "Florencio Varela": 4,
    # ---- Córdoba ----
    "Córdoba Capital": 7,
    "Villa Allende": 8,
    "Villa Carlos Paz": 7,
    "Alta Gracia": 6,
    "Jesús María": 6,
    "Río Cuarto": 6,
    "La Falda": 6,
    "Villa María": 6,
    "Cosquín": 5,
}
