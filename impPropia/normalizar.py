import configparser
import datetime
import os
import re
import unicodedata
from functools import lru_cache

import nltk
from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer

RUTA_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUTA_CONFIG_DEFECTO = os.path.join(RUTA_RAIZ, "config", "indexer.conf")
RUTA_THESAURUS_DEFECTO = os.path.join(RUTA_RAIZ, "thesaurus.txt")

IDIOMAS = ("es", "en", "pt")
NOMBRES_NLTK = {"es": "spanish", "en": "english", "pt": "portuguese"}


def quitarAcentos(texto: str) -> str:
    return ''.join(
        caracter for caracter in unicodedata.normalize('NFD', texto)
        if unicodedata.category(caracter) != 'Mn'
    )


# ---------------------------------------------------------------------------
# Patrones
# ---------------------------------------------------------------------------

meses = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10,
    'noviembre': 11, 'diciembre': 12,
    'janeiro': 1, 'fevereiro': 2, 'marco': 3, 'maio': 5, 'junho': 6,
    'julho': 7, 'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11,
    'december': 12,
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'jun': 6, 'jul': 7, 'ago': 8,
    'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dic': 12,
    'jan': 1, 'apr': 4, 'aug': 8, 'dec': 12,
}
patronMeses = '|'.join(sorted(map(re.escape, meses), key=len, reverse=True))

patronFecha = re.compile(
    r'\b(?:(?P<dia>\d{1,2})\s+(?:de\s+|del\s+|do\s+|da\s+)?(?P<mes>' +
    patronMeses + r')\.?\s*(?:de\s+|del\s+|do\s+|da\s+)?,?\s*(?P<anio>\d{4})'
    r'|(?P<mes2>' + patronMeses + r')\.?\s+(?P<dia2>\d{1,2}),?\s+(?P<anio2>\d{4}))\b'
)
patronFechaISO = re.compile(
    r'\b(?P<anio>\d{4})[/\-. ](?P<mes>\d{1,2})[/\-. ](?P<dia>\d{1,2})\b'
)
patronFechaNumerica = re.compile(
    r'\b(?P<a>\d{1,2})[/\-. ](?P<b>\d{1,2})[/\-. ](?P<c>\d{2,4})\b'
)
patronFecha2 = re.compile(
    r'\b((?:18|19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\b'
)
patronRangoAnios = re.compile(
    r'\b((?:18|19|20)\d{2})((?:18|19|20)\d{2})\b'
)
patronToken = re.compile(r'\b\d{4}-\d{2}-\d{2}\b|\b\d{4}-\d{4}\b|<num>|[a-z0-9]+')
patronSiglas = re.compile(r'\b(?:[a-z]{1,2}\.){2,}')
patronNumero = re.compile(r'(?<![\w-])\d+(?![\w-])')

opcionesDefault = {
    'stopwords': True,
    'stemming': True,
    'thesaurus': True,
    'fechas': True,
    'numeros': 'agrupar',
    'anioMin': 1000,
    'anioMax': 2999,
    'idioma': 'auto',
    'longitudMinima': 2,
    'limpiezaBoilerplate': True,
}


# ---------------------------------------------------------------------------
# Stopwords y stemmers
# ---------------------------------------------------------------------------

def _cargarStopwords():
    resultado = {}
    for idioma, nombre in NOMBRES_NLTK.items():
        try:
            palabras = stopwords.words(nombre)
        except LookupError:
            nltk.download('stopwords')
            palabras = stopwords.words(nombre)
        resultado[idioma] = {quitarAcentos(p.lower()) for p in palabras}
    return resultado


stopWordsPorIdioma = _cargarStopwords()
stopWords = stopWordsPorIdioma['es']  # compatibilidad
_universal = set().union(*stopWordsPorIdioma.values())
stopWordsDistintivas = {
    idioma: stopWordsPorIdioma[idioma] - set().union(
        *(stopWordsPorIdioma[otro] for otro in IDIOMAS if otro != idioma)
    )
    for idioma in IDIOMAS
}

stemmers = {idioma: SnowballStemmer(nombre) for idioma, nombre in NOMBRES_NLTK.items()}
lematizador = stemmers['es']  # compatibilidad


@lru_cache(maxsize=500000)
def _stem(idioma: str, token: str) -> str:
    return stemmers[idioma].stem(token)


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

def _leerConfig(rutaConfig=None):
    if rutaConfig is None:
        rutaConfig = RUTA_CONFIG_DEFECTO
    parser = configparser.ConfigParser()
    if rutaConfig and os.path.exists(rutaConfig):
        parser.read(rutaConfig, encoding='utf-8')
    return parser


def cargarConfiguracionCompleta(rutaConfig=None) -> dict:
    parser = _leerConfig(rutaConfig)
    norm = dict(opcionesDefault)

    if parser.has_section('Normalizacion'):
        for clave in list(norm):
            if not parser.has_option('Normalizacion', clave):
                continue
            if isinstance(norm[clave], bool):
                norm[clave] = parser.getboolean('Normalizacion', clave)
            elif isinstance(norm[clave], int):
                norm[clave] = parser.getint('Normalizacion', clave)
            else:
                norm[clave] = parser.get('Normalizacion', clave).strip().lower()

    coleccion = {'rutaColeccion': 'coleccion', 'extensiones': '.txt'}
    if parser.has_section('Coleccion'):
        if parser.has_option('Coleccion', 'rutaColeccion'):
            coleccion['rutaColeccion'] = parser.get('Coleccion', 'rutaColeccion').strip()
        if parser.has_option('Coleccion', 'extensiones'):
            coleccion['extensiones'] = parser.get('Coleccion', 'extensiones').strip()

    thesaurusCfg = {'ruta': RUTA_THESAURUS_DEFECTO, 'estricto': False}
    if parser.has_section('Thesaurus'):
        if parser.has_option('Thesaurus', 'ruta'):
            thesaurusCfg['ruta'] = parser.get('Thesaurus', 'ruta').strip()
        if parser.has_option('Thesaurus', 'estricto'):
            thesaurusCfg['estricto'] = parser.getboolean('Thesaurus', 'estricto')

    indexador = {'rutaIndice': 'output/indexAPata', 'bloqueDocs': 20000}
    if parser.has_section('Indexador'):
        if parser.has_option('Indexador', 'rutaIndice'):
            indexador['rutaIndice'] = parser.get('Indexador', 'rutaIndice').strip()
        if parser.has_option('Indexador', 'bloqueDocs'):
            indexador['bloqueDocs'] = parser.getint('Indexador', 'bloqueDocs')

    return {
        'normalizacion': norm,
        'coleccion': coleccion,
        'thesaurus': thesaurusCfg,
        'indexador': indexador,
    }


def cargarConfiguracion(rutaConfig: str = None) -> dict:
    return cargarConfiguracionCompleta(rutaConfig)['normalizacion']


# ---------------------------------------------------------------------------
# Tesauro
# ---------------------------------------------------------------------------

CONECTORES = {'de', 'del', 'la', 'el', 'los', 'las', 'al', 'y', 'o'}

thesaurus = {}
thesaurusFrases = {}
frasesPorPrimera = {}
maxPalabrasConcepto = 1


def _tokensClave(texto: str):
    return patronToken.findall(quitarAcentos(texto.lower()))


def _canonico(texto: str) -> str:
    partes = [p for p in _tokensClave(texto) if p not in CONECTORES]
    return '_'.join(partes)


def cargarThesaurus(ruta: str = None) -> int:
    """Carga el tesauro convirtiendo cada valor en un token atómico."""
    global thesaurus, thesaurusFrases, frasesPorPrimera, maxPalabrasConcepto
    if ruta is None:
        ruta = RUTA_THESAURUS_DEFECTO
    thesaurus = {}
    thesaurusFrases = {}
    frasesPorPrimera = {}
    if not ruta or not os.path.exists(ruta):
        maxPalabrasConcepto = 1
        return 0

    with open(ruta, 'r', encoding='utf-8') as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea or linea.startswith('#') or ':' not in linea:
                continue
            clave, valor = linea.split(':', 1)
            tokens = _tokensClave(clave)
            canonico = _canonico(valor)
            if not tokens or not canonico:
                continue
            if len(tokens) == 1:
                # Las claves que son stopwords (p.ej. "para", "contra")
                # se descartan para no expandir preposiciones.
                if tokens[0] in stopWordsPorIdioma['es']:
                    continue
                thesaurus[tokens[0]] = canonico
            else:
                frase = tuple(tokens)
                thesaurusFrases[frase] = canonico
                frasesPorPrimera.setdefault(frase[0], []).append((frase, canonico))

    for lista in frasesPorPrimera.values():
        lista.sort(key=lambda x: -len(x[0]))
    maxPalabrasConcepto = max((len(f) for f in thesaurusFrases), default=1)
    return len(thesaurus) + len(thesaurusFrases)


cargarThesaurus(RUTA_THESAURUS_DEFECTO)


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------

def _fechaValida(anio: int, mes: int, dia: int) -> bool:
    try:
        datetime.date(anio, mes, dia)
        return True
    except ValueError:
        return False


def normalizarFecha(coincidencia) -> str:
    dia = int(coincidencia.group('dia') or coincidencia.group('dia2'))
    mes = meses[coincidencia.group('mes') or coincidencia.group('mes2')]
    anio = int(coincidencia.group('anio') or coincidencia.group('anio2'))
    if not _fechaValida(anio, mes, dia):
        return coincidencia.group(0)
    return f'{anio:04d}-{mes:02d}-{dia:02d}'


def _normalizarFechaISO(coincidencia) -> str:
    anio = int(coincidencia.group('anio'))
    mes = int(coincidencia.group('mes'))
    dia = int(coincidencia.group('dia'))
    if not _fechaValida(anio, mes, dia):
        return coincidencia.group(0)
    return f'{anio:04d}-{mes:02d}-{dia:02d}'


def _normalizarFechaNumerica(coincidencia, idioma: str = 'es') -> str:
    a = int(coincidencia.group('a'))
    b = int(coincidencia.group('b'))
    c = int(coincidencia.group('c'))

    if a > 31 or b > 31:
        return coincidencia.group(0)
    anio = c
    if c < 100:
        anio = 2000 + c if c <= 29 else 1900 + c

    if a > 12:
        dia, mes = a, b
    elif b > 12:
        dia, mes = b, a
    elif idioma == 'en':
        mes, dia = a, b
    else:
        dia, mes = a, b

    if not _fechaValida(anio, mes, dia):
        return coincidencia.group(0)
    return f'{anio:04d}-{mes:02d}-{dia:02d}'


def _normalizarFechaCompacta(coincidencia) -> str:
    anio, mes, dia = int(coincidencia.group(1)), int(coincidencia.group(2)), int(coincidencia.group(3))
    if not _fechaValida(anio, mes, dia):
        return coincidencia.group(0)
    return f'{anio:04d}-{mes:02d}-{dia:02d}'


# ---------------------------------------------------------------------------
# Limpieza y normalización de texto
# ---------------------------------------------------------------------------

def _colapsarSiglas(texto: str) -> str:
    texto = re.sub(r'(?<=[a-z]\.)\s+(?=[a-z]{1,2}\.)', '', texto)
    return patronSiglas.sub(lambda m: m.group(0).replace('.', ''), texto)


def _limpiarBoilerplate(texto: str) -> str:
    texto = re.sub(r'https?://\S+', ' ', texto)
    texto = re.sub(r'www\.\S+', ' ', texto)
    texto = re.sub(r'\b\d{14}\b', ' ', texto)
    texto = re.sub(r'\b\d+\s+captures?\b', ' ', texto)
    texto = re.sub(r'\b(?:wayback machine|about this capture|save page now|timestamps?)\b', ' ', texto)
    # El crawler guarda las URLs sin puntos: "https webarchiveorg web ..."
    texto = re.sub(r'\b(?:https?|www|webarchiveorg)\b', ' ', texto)
    return texto


def _normalizarNumeros(texto: str, opciones: dict) -> str:
    modo = opciones.get('numeros', 'agrupar')
    if modo == 'conservar':
        return texto
    anioMin = int(opciones.get('anioMin', 1000))
    anioMax = int(opciones.get('anioMax', 2999))

    # Números con separadores de miles/decimales: 1.234,56 -> <num>.
    texto = re.sub(
        r'(?<![\w-])\d{1,3}(?:[.,]\d{1,3})+(?![\w-])',
        '<num>' if modo == 'agrupar' else ' ',
        texto,
    )

    def reemplazar(m):
        token = m.group(0)
        if len(token) == 4 and anioMin <= int(token) <= anioMax:
            return token
        return '<num>' if modo == 'agrupar' else ' '

    return patronNumero.sub(reemplazar, texto)


def detectarIdioma(texto: str) -> str:
    tokens = patronToken.findall(quitarAcentos(texto.lower()))
    conteos = {idioma: 0 for idioma in IDIOMAS}
    for token in tokens[:4000]:
        for idioma in IDIOMAS:
            if token in stopWordsDistintivas[idioma]:
                conteos[idioma] += 1
    mejor = max(conteos, key=conteos.get)
    if conteos[mejor] > 0:
        return mejor
    return 'es'


def normalizarTexto(texto: str, opciones: dict = None, idioma: str = None) -> list:
    opciones = {**opcionesDefault, **(opciones or {})}

    texto = quitarAcentos(texto.lower())
    texto = re.sub(r'\[\d+\]', '', texto)

    if opciones['limpiezaBoilerplate']:
        texto = _limpiarBoilerplate(texto)

    # Las siglas se colapsan antes de tokenizar (EE.UU. -> eeuu).
    texto = _colapsarSiglas(texto)

    if idioma is None:
        if opciones.get('idioma', 'auto') == 'auto':
            idioma = detectarIdioma(texto)
        else:
            idioma = opciones['idioma']

    if opciones['fechas']:
        texto = patronFecha.sub(normalizarFecha, texto)
        texto = patronFechaISO.sub(_normalizarFechaISO, texto)
        idiomaFecha = idioma or 'es'
        texto = patronFechaNumerica.sub(
            lambda m: _normalizarFechaNumerica(m, idiomaFecha), texto
        )
        texto = patronFecha2.sub(_normalizarFechaCompacta, texto)
        texto = patronRangoAnios.sub(r'\1-\2', texto)

    texto = _normalizarNumeros(texto, opciones)

    tokens = patronToken.findall(texto)

    if idioma not in IDIOMAS:
        idioma = 'otro'

    stop = stopWordsPorIdioma.get(idioma, set()) if opciones['stopwords'] else set()
    longitudMinima = int(opciones.get('longitudMinima', 2))

    resultado = []
    indice = 0
    while indice < len(tokens):
        concepto = None
        salto = 1

        if opciones['thesaurus']:
            for frase, canonico in frasesPorPrimera.get(tokens[indice], ()):
                largo = len(frase)
                if tuple(tokens[indice:indice + largo]) == frase:
                    concepto = canonico
                    salto = largo
                    break

        if concepto is not None:
            resultado.append(concepto)
            indice += salto
            continue

        token = tokens[indice]
        indice += 1

        if token in ('<num>',) or re.fullmatch(r'\d{4}-\d{2}-\d{2}|\d{4}-\d{4}', token):
            resultado.append(token)
            continue

        if token in stop:
            continue

        if opciones['thesaurus'] and token in thesaurus:
            resultado.append(thesaurus[token])
            continue

        if len(token) < longitudMinima:
            continue

        if opciones['stemming'] and idioma != 'otro':
            token = _stem(idioma, token)

        if token:
            resultado.append(token)

    return resultado


def normalizarDocumentoInfo(rutaArchivo: str, opciones: dict = None):
    with open(rutaArchivo, 'r', encoding='utf-8', errors='ignore') as archivo:
        texto = archivo.read()
    if opciones is None:
        opciones = opcionesDefault
    if opciones.get('idioma', 'auto') == 'auto':
        idioma = detectarIdioma(texto)
    else:
        idioma = opciones['idioma']
    return normalizarTexto(texto, opciones, idioma), idioma


def normalizarDocumento(rutaArchivo: str, opciones: dict = None) -> list:
    return normalizarDocumentoInfo(rutaArchivo, opciones)[0]


def recorrerDirectorio(rutaDirectorio: str):
    for root, dirs, files in os.walk(rutaDirectorio):
        dirs.sort()
        for file in sorted(files):
            yield os.path.join(root, file)
