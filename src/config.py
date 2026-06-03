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
        "Agronomía": "agronomia",
        "Almagro": "almagro",
        "Balvanera": "balvanera",
        "Barracas": "barracas",
        "Barrio Norte": "barrio-norte",
        "Belgrano": "belgrano",
        "Boedo": "boedo",
        "Caballito": "caballito",
        "Chacarita": "chacarita",
        "Coghlan": "coghlan",
        "Colegiales": "colegiales",
        "Constitución": "constitucion",
        "Flores": "flores",
        "Floresta": "floresta",
        "La Boca": "la-boca",
        "La Paternal": "la-paternal",
        "Liniers": "liniers",
        "Mataderos": "mataderos",
        "Monserrat": "monserrat",
        "Monte Castro": "monte-castro",
        "Nueva Pompeya": "nueva-pompeya",
        "Núñez": "nunez",
        "Palermo": "palermo",
        "Parque Avellaneda": "parque-avellaneda",
        "Parque Chacabuco": "parque-chacabuco",
        "Parque Chas": "parque-chas",
        "Parque Patricios": "parque-patricios",
        "Puerto Madero": "puerto-madero",
        "Recoleta": "recoleta",
        "Retiro": "retiro",
        "Saavedra": "saavedra",
        "San Cristóbal": "san-cristobal",
        "San Nicolás": "san-nicolas",
        "San Telmo": "san-telmo",
        "Vélez Sarsfield": "velez-sarsfield",
        "Versalles": "versalles",
        "Villa Crespo": "villa-crespo",
        "Villa del Parque": "villa-del-parque",
        "Villa Devoto": "villa-devoto",
        "Villa General Mitre": "villa-general-mitre",
        "Villa Lugano": "villa-lugano",
        "Villa Luro": "villa-luro",
        "Villa Ortúzar": "villa-ortuzar",
        "Villa Pueyrredón": "villa-pueyrredon",
        "Villa Real": "villa-real",
        "Villa Riachuelo": "villa-riachuelo",
        "Villa Santa Rita": "villa-santa-rita",
        "Villa Soldati": "villa-soldati",
        "Villa Urquiza": "villa-urquiza",
    },
    "Buenos Aires": {
        "Adolfo Alsina": "adolfo-alsina",
        "Adolfo Gonzales Chaves": "adolfo-gonzales-chaves",
        "Alberti": "alberti",
        "Almirante Brown": "almirante-brown",
        "Arrecifes": "arrecifes",
        "Avellaneda": "avellaneda",
        "Ayacucho": "ayacucho",
        "Azul": "azul",
        "Bahía Blanca": "bahia-blanca",
        "Balcarce": "balcarce",
        "Baradero": "baradero",
        "Benito Juárez": "benito-juarez",
        "Berazategui": "berazategui",
        "Berisso": "berisso",
        "Bolívar": "bolivar",
        "Bragado": "bragado",
        "Brandsen": "brandsen",
        "Campana": "campana",
        "Cañuelas": "canuelas",
        "Capitán Sarmiento": "capitan-sarmiento",
        "Carlos Casares": "carlos-casares",
        "Carlos Tejedor": "carlos-tejedor",
        "Carmen de Areco": "carmen-de-areco",
        "Castelli": "castelli",
        "Chacabuco": "chacabuco",
        "Chascomús": "chascomus",
        "Chivilcoy": "chivilcoy",
        "Colón": "colon",
        "Coronel Dorrego": "coronel-dorrego",
        "Coronel Pringles": "coronel-pringles",
        "Coronel Rosales": "coronel-rosales",
        "Coronel Suárez": "coronel-suarez",
        "Daireaux": "daireaux",
        "Dolores": "dolores",
        "Ensenada": "ensenada",
        "Escobar": "escobar",
        "Esteban Echeverría": "esteban-echeverria",
        "Exaltación de la Cruz": "exaltacion-de-la-cruz",
        "Ezeiza": "ezeiza",
        "Florencio Varela": "florencio-varela",
        "Florentino Ameghino": "florentino-ameghino",
        "General Alvarado": "general-alvarado",
        "General Alvear": "general-alvear",
        "General Arenales": "general-arenales",
        "General Belgrano": "general-belgrano",
        "General Guido": "general-guido",
        "General Juan Madariaga": "general-juan-madariaga",
        "General La Madrid": "general-la-madrid",
        "General Las Heras": "general-las-heras",
        "General Lavalle": "general-lavalle",
        "General Paz": "general-paz",
        "General Pinto": "general-pinto",
        "General Rodríguez": "general-rodriguez",
        "General San Martín": "general-san-martin",
        "General Viamonte": "general-viamonte",
        "General Villegas": "general-villegas",
        "Guaminí": "guamini",
        "Hipólito Yrigoyen": "hipolito-yrigoyen",
        "Hurlingham": "hurlingham",
        "Ituzaingó": "ituzaingo",
        "José C. Paz": "jose-c-paz",
        "Junín": "junin",
        "La Costa": "la-costa",
        "La Matanza": "la-matanza",
        "La Plata": "la-plata",
        "Lanús": "lanus",
        "Laprida": "laprida",
        "Las Flores": "las-flores",
        "Leandro N. Alem": "leandro-n-alem",
        "Lezama": "lezama",
        "Lincoln": "lincoln",
        "Lobería": "loberia",
        "Lobos": "lobos",
        "Lomas de Zamora": "lomas-de-zamora",
        "Luján": "lujan",
        "Magdalena": "magdalena",
        "Maipú": "maipu",
        "Malvinas Argentinas": "malvinas-argentinas",
        "Mar Chiquita": "mar-chiquita",
        "Mar del Plata": "mar-del-plata",
        "Marcos Paz": "marcos-paz",
        "Mercedes": "mercedes",
        "Merlo": "merlo",
        "Monte": "monte",
        "Monte Hermoso": "monte-hermoso",
        "Moreno": "moreno",
        "Morón": "moron",
        "Navarro": "navarro",
        "Necochea": "necochea",
        "Nueve de Julio": "nueve-de-julio",
        "Olavarría": "olavarria",
        "Patagones": "patagones",
        "Pehuajó": "pehuajo",
        "Pellegrini": "pellegrini",
        "Pergamino": "pergamino",
        "Pila": "pila",
        "Pilar": "pilar",
        "Pinamar": "pinamar",
        "Presidente Perón": "presidente-peron",
        "Puan": "puan",
        "Punta Indio": "punta-indio",
        "Quilmes": "quilmes",
        "Ramallo": "ramallo",
        "Rauch": "rauch",
        "Rivadavia": "rivadavia",
        "Rojas": "rojas",
        "Roque Pérez": "roque-perez",
        "Saavedra": "saavedra",
        "Saladillo": "saladillo",
        "Salliqueló": "salliquelo",
        "Salto": "salto",
        "San Andrés de Giles": "san-andres-de-giles",
        "San Antonio de Areco": "san-antonio-de-areco",
        "San Cayetano": "san-cayetano",
        "San Fernando": "san-fernando",
        "San Isidro": "san-isidro",
        "San Miguel": "san-miguel",
        "San Nicolás": "san-nicolas",
        "San Pedro": "san-pedro",
        "San Vicente": "san-vicente",
        "Suipacha": "suipacha",
        "Tandil": "tandil",
        "Tapalqué": "tapalque",
        "Tigre": "tigre",
        "Tordillo": "tordillo",
        "Tornquist": "tornquist",
        "Trenque Lauquen": "trenque-lauquen",
        "Tres Arroyos": "tres-arroyos",
        "Tres de Febrero": "tres-de-febrero",
        "Tres Lomas": "tres-lomas",
        "Veinticinco de Mayo": "veinticinco-de-mayo",
        "Vicente López": "vicente-lopez",
        "Villa Gesell": "villa-gesell",
        "Villarino": "villarino",
        "Zárate": "zarate",
    },
    "Córdoba": {
        "Alta Gracia": "alta-gracia",
        "Córdoba Capital": "cordoba",
        "Cosquín": "cosquin",
        "Jesús María": "jesus-maria",
        "La Falda": "la-falda",
        "Río Cuarto": "rio-cuarto",
        "Villa Allende": "villa-allende",
        "Villa Carlos Paz": "villa-carlos-paz",
        "Villa María": "villa-maria",
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

# Cota ANTI-RUNAWAY: tope altísimo, sólo para evitar un bucle accidental si la
# detección de páginas fallara. En la práctica NUNCA limita: se scrapean todas
# las páginas que el sitio reporte, haya las que haya.
MAX_PAGES_HARD_LIMIT = 100000

REQUEST_TIMEOUT = 20  # segundos
REQUEST_RETRIES = 3

# --------------------------------------------------------------------------- #
#  Cotización del dólar (para comparar precios USD/Pesos en una misma escala)
# --------------------------------------------------------------------------- #
# Se toma el dólar OFICIAL (venta) de DolarApi. Permite que una búsqueda por
# rango de precio capture publicaciones en pesos que, al cambio, entran en el
# rango en dólares (y viceversa), y destacar alquileres cotizados en USD.
DOLARAPI_URL = "https://dolarapi.com/v1/dolares/oficial"

# Respaldo si la API no responde (ARS por USD, dólar oficial venta). Es solo
# una red de seguridad: el valor real se toma online en cada corrida.
FX_USD_FALLBACK = 1450.0

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
#  Estimación de expensas faltantes
# --------------------------------------------------------------------------- #
# Cuando un aviso NO publica expensas, se estiman (ver analysis.py) a partir de
# la tarifa $/m² mediana de su zona. Pero un edificio con amenities (pileta,
# gimnasio, seguridad, encargado…) tiene expensas MUCHO más altas que uno
# "pelado": detectamos esas palabras y ajustamos la estimación con un factor.
#
# Cada GRUPO de amenities presente suma EXPENSE_AMENITY_STEP al factor, que
# arranca en EXPENSE_AMENITY_BASE (edificio sin nada -> expensas por debajo de
# la mediana) y se topea en EXPENSE_AMENITY_MAX.
EXPENSE_AMENITY_BASE = 0.75
EXPENSE_AMENITY_STEP = 0.17
EXPENSE_AMENITY_MAX = 1.70

# Grupos de sinónimos: cada grupo cuenta UNA sola vez (pileta y piscina no
# suman doble). Se comparan sin acentos ni mayúsculas.
EXPENSE_AMENITY_GROUPS = [
    ["pileta", "piscina"],
    ["gimnasio", "gym"],
    ["sum", "salon de usos", "microcine", "cine"],
    ["seguridad", "vigilancia", "24 horas", "24hs", "camaras", "circuito cerrado"],
    ["encargado", "portero", "porteria", "conserje"],
    ["amenities"],
    ["solarium", "terraza"],
    ["spa", "sauna", "jacuzzi", "hidromasaje"],
    ["laundry", "lavadero comun"],
    ["coworking", "business center"],
]

# --------------------------------------------------------------------------- #
#  Puntajes de zona (1–10)  — SEMILLA EDITABLE
# --------------------------------------------------------------------------- #
# Valoración subjetiva (seguridad / costo de vida / servicios) por barrio o
# partido. Son SOLO un punto de partida: ajustalos a tu criterio.
# Únicamente se usan cuando ZONE_SCORE_SOURCE = "override".
# Las claves se comparan sin distinguir mayúsculas ni acentos.
ZONE_SCORES = {
    # ---- CABA ----
    "Agronomía": 7,
    "Almagro": 6,
    "Balvanera": 5,
    "Barracas": 6,
    "Barrio Norte": 9,
    "Belgrano": 9,
    "Boedo": 6,
    "Caballito": 8,
    "Chacarita": 7,
    "Coghlan": 8,
    "Colegiales": 8,
    "Constitución": 3,
    "Flores": 5,
    "Floresta": 6,
    "La Boca": 5,
    "La Paternal": 6,
    "Liniers": 5,
    "Mataderos": 5,
    "Monserrat": 5,
    "Monte Castro": 7,
    "Nueva Pompeya": 4,
    "Núñez": 9,
    "Palermo": 9,
    "Parque Avellaneda": 5,
    "Parque Chacabuco": 6,
    "Parque Chas": 7,
    "Parque Patricios": 5,
    "Puerto Madero": 10,
    "Recoleta": 9,
    "Retiro": 6,
    "Saavedra": 4,
    "San Cristóbal": 5,
    "San Nicolás": 6,
    "San Telmo": 6,
    "Vélez Sarsfield": 6,
    "Versalles": 7,
    "Villa Crespo": 7,
    "Villa del Parque": 7,
    "Villa Devoto": 7,
    "Villa General Mitre": 6,
    "Villa Lugano": 3,
    "Villa Luro": 6,
    "Villa Ortúzar": 7,
    "Villa Pueyrredón": 7,
    "Villa Real": 6,
    "Villa Riachuelo": 4,
    "Villa Santa Rita": 6,
    "Villa Soldati": 3,
    "Villa Urquiza": 8,
    # ---- Buenos Aires ----
    "Adolfo Alsina": 4,
    "Adolfo Gonzales Chaves": 4,
    "Alberti": 4,
    "Almirante Brown": 5,
    "Arrecifes": 5,
    "Avellaneda": 5,
    "Ayacucho": 5,
    "Azul": 6,
    "Bahía Blanca": 6,
    "Balcarce": 6,
    "Baradero": 5,
    "Benito Juárez": 5,
    "Berazategui": 5,
    "Berisso": 6,
    "Bolívar": 5,
    "Bragado": 5,
    "Brandsen": 5,
    "Campana": 6,
    "Cañuelas": 5,
    "Capitán Sarmiento": 5,
    "Carlos Casares": 4,
    "Carlos Tejedor": 4,
    "Carmen de Areco": 5,
    "Castelli": 4,
    "Chacabuco": 5,
    "Chascomús": 6,
    "Chivilcoy": 5,
    "Colón": 5,
    "Coronel Dorrego": 5,
    "Coronel Pringles": 5,
    "Coronel Rosales": 5,
    "Coronel Suárez": 5,
    "Daireaux": 4,
    "Dolores": 6,
    "Ensenada": 6,
    "Escobar": 6,
    "Esteban Echeverría": 5,
    "Exaltación de la Cruz": 6,
    "Ezeiza": 5,
    "Florencio Varela": 4,
    "Florentino Ameghino": 4,
    "General Alvarado": 6,
    "General Alvear": 4,
    "General Arenales": 4,
    "General Belgrano": 5,
    "General Guido": 4,
    "General Juan Madariaga": 5,
    "General La Madrid": 4,
    "General Las Heras": 5,
    "General Lavalle": 5,
    "General Paz": 4,
    "General Pinto": 4,
    "General Rodríguez": 5,
    "General San Martín": 6,
    "General Viamonte": 4,
    "General Villegas": 5,
    "Guaminí": 4,
    "Hipólito Yrigoyen": 4,
    "Hurlingham": 6,
    "Ituzaingó": 6,
    "José C. Paz": 4,
    "Junín": 6,
    "La Costa": 7,
    "La Matanza": 4,
    "La Plata": 7,
    "Lanús": 5,
    "Laprida": 4,
    "Las Flores": 5,
    "Leandro N. Alem": 4,
    "Lezama": 4,
    "Lincoln": 5,
    "Lobería": 5,
    "Lobos": 6,
    "Lomas de Zamora": 5,
    "Luján": 6,
    "Magdalena": 6,
    "Maipú": 5,
    "Malvinas Argentinas": 5,
    "Mar Chiquita": 6,
    "Mar del Plata": 7,
    "Marcos Paz": 5,
    "Mercedes": 6,
    "Merlo": 4,
    "Monte": 5,
    "Monte Hermoso": 7,
    "Moreno": 4,
    "Morón": 6,
    "Navarro": 4,
    "Necochea": 6,
    "Nueve de Julio": 5,
    "Olavarría": 6,
    "Patagones": 4,
    "Pehuajó": 5,
    "Pellegrini": 4,
    "Pergamino": 6,
    "Pila": 4,
    "Pilar": 7,
    "Pinamar": 8,
    "Presidente Perón": 4,
    "Puan": 4,
    "Punta Indio": 6,
    "Quilmes": 5,
    "Ramallo": 5,
    "Rauch": 5,
    "Rivadavia": 4,
    "Rojas": 5,
    "Roque Pérez": 4,
    "Saavedra": 4,
    "Saladillo": 5,
    "Salliqueló": 4,
    "Salto": 5,
    "San Andrés de Giles": 5,
    "San Antonio de Areco": 7,
    "San Cayetano": 5,
    "San Fernando": 7,
    "San Isidro": 9,
    "San Miguel": 6,
    "San Nicolás": 6,
    "San Pedro": 6,
    "San Vicente": 5,
    "Suipacha": 5,
    "Tandil": 7,
    "Tapalqué": 4,
    "Tigre": 7,
    "Tordillo": 3,
    "Tornquist": 5,
    "Trenque Lauquen": 5,
    "Tres Arroyos": 6,
    "Tres de Febrero": 6,
    "Tres Lomas": 4,
    "Veinticinco de Mayo": 5,
    "Vicente López": 9,
    "Villa Gesell": 7,
    "Villarino": 4,
    "Zárate": 6,
    # ---- Córdoba ----
    "Alta Gracia": 6,
    "Córdoba Capital": 7,
    "Cosquín": 5,
    "Jesús María": 6,
    "La Falda": 6,
    "Río Cuarto": 6,
    "Villa Allende": 8,
    "Villa Carlos Paz": 7,
    "Villa María": 6,
}
