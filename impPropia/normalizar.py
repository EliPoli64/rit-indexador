import configparser
import os
import re
import unicodedata
import nltk
from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer

baseRoute = os.path.dirname(os.path.abspath(__file__))

# tomado de https://www.nltk.org/api/nltk.html
try:
    stopWords = set(stopwords.words('spanish'))
except LookupError:
    nltk.download('stopwords')
    stopWords = set(stopwords.words('spanish'))

lematizador = SnowballStemmer('spanish')
thesaurus = {}

with open(os.path.join(baseRoute, "thesaurus.txt"), "r", encoding="utf-8") as archivoThesaurus:
    listaConceptos = archivoThesaurus.read().split("\n")
    # almacenamos conceptos en formato vocablo:significado
    for concepto in listaConceptos:
        if ":" in concepto:
            partes = concepto.split(":")
            thesaurus[partes[0].strip()] = partes[1].strip()

# el tesauro contiene conceptos de varias palabras, por lo que se buscan
# frases completas (de la mas larga a la mas corta), no solo palabra por palabra
maxPalabrasConcepto = max(
    (len(concepto.split()) for concepto in thesaurus if ' ' in concepto),
    default=4
)

# politicas de normalizacion; se pueden cambiar desde config/indexer.conf
opcionesDefault = {
    'stopwords': True,
    'stemming': True,
    'thesaurus': True,
    'fechas': True,
}


def cargarConfiguracion(rutaConfig: str = None) -> dict:
    opciones = dict(opcionesDefault)
    if rutaConfig is None:
        rutaConfig = os.path.join(baseRoute, 'config/indexer.conf')
    if not os.path.exists(rutaConfig):
        return opciones

    parser = configparser.ConfigParser()
    parser.read(rutaConfig, encoding='utf-8')

    if parser.has_section('Normalizacion'):
        for clave in opciones:
            if parser.has_option('Normalizacion', clave):
                opciones[clave] = parser.getboolean('Normalizacion', clave)

    return opciones

meses = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
    'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10,
    'noviembre': 11, 'diciembre': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11,
    'december': 12,
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'jun': 6, 'jul': 7, 'ago': 8,
    'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dic': 12,
    'jan': 1, 'apr': 4, 'aug': 8, 'dec': 12,
}
patronMeses = '|'.join(sorted(map(re.escape, meses), key=len, reverse=True))

# fechas con mes escrito: "20 de octubre de 2019" u "october 20 2019"
patronFecha = re.compile(
    r'\b(?:(?P<dia>\d{1,2})\s+(?:de\s+|del\s+)?(?P<mes>' + patronMeses +
    r')\s+(?:de\s+|del\s+)?(?P<anio>\d{4})'
    r'|(?P<mes2>' + patronMeses + r')\s+(?P<dia2>\d{1,2})\s+(?P<anio2>\d{4}))\b'
)
# fechas compactas del tipo aaaammdd (por ejemplo 20091231)
patronFecha2 = re.compile(
    r'\b((?:18|19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\b'
)
# anios pegados que representan un rango (por ejemplo 20062019)
patronRangoAnios = re.compile(
    r'\b((?:18|19|20)\d{2})((?:18|19|20)\d{2})\b'
)
# las fechas ya normalizadas deben conservarse como un solo token
patronToken = re.compile(r'\b\d{4}-\d{2}-\d{2}\b|\b\d{4}-\d{4}\b|[a-z0-9]+')


def quitarAcentos(texto: str) -> str:
    return ''.join(
        caracter for caracter in unicodedata.normalize('NFD', texto)
        if unicodedata.category(caracter) != 'Mn'
    )


def normalizarFecha(coincidencia) -> str:
    dia = int(coincidencia.group('dia') or coincidencia.group('dia2'))
    mes = meses[coincidencia.group('mes') or coincidencia.group('mes2')]
    anio = int(coincidencia.group('anio') or coincidencia.group('anio2'))
    if not 1 <= dia <= 31:
        return coincidencia.group(0)
    return f'{anio:04d}-{mes:02d}-{dia:02d}'


def normalizarTexto(texto: str, opciones: dict = None) -> list:
    opciones = {**opcionesDefault, **(opciones or {})}

    # unificar mayusculas y quitar tildes para que coincidan con el
    # tesauro y las stopwords (que estan sin tildes)
    texto = quitarAcentos(texto.lower())
    # remover referencias puestas entre corchetes (como [1], [45])
    texto = re.sub(r'\[\d+\]', '', texto)

    if opciones['fechas']:
        # buscar fechas y llevarlas a un unico token en formato aaaa-mm-dd
        texto = patronFecha.sub(normalizarFecha, texto)
        texto = patronFecha2.sub(
            lambda m: f'{m.group(1)}-{m.group(2)}-{m.group(3)}', texto
        )
        # buscar anios que empiecen en 18-19-20 y que esten pegados
        texto = patronRangoAnios.sub(r'\1-\2', texto)

    tokens = patronToken.findall(texto)
    tokensProcesados = []
    indice = 0

    while indice < len(tokens):
        concepto = None

        # buscar primero los conceptos del tesauro de varias palabras
        if opciones['thesaurus']:
            maximo = min(maxPalabrasConcepto, len(tokens) - indice)
            for cantidad in range(maximo, 1, -1):
                frase = ' '.join(tokens[indice:indice + cantidad])
                if frase in thesaurus:
                    concepto = thesaurus[frase]
                    indice += cantidad
                    break

        if concepto is None:
            token = tokens[indice]
            indice += 1

            if opciones['stopwords'] and token in stopWords:
                continue

            if re.fullmatch(r'\d{4}-\d{2}-\d{2}|\d{4}-\d{4}', token):
                tokensProcesados.append(token)
                continue

            concepto = thesaurus.get(token, token) if opciones['thesaurus'] else token

        # un concepto del tesauro puede tener varias palabras: se lematiza
        # cada una por separado
        for parte in concepto.split():
            if opciones['stopwords'] and parte in stopWords:
                continue
            tokensProcesados.append(
                lematizador.stem(parte) if opciones['stemming'] else parte
            )
        
    return tokensProcesados


def normalizarDocumento(rutaArchivo: str, opciones: dict = None) -> list:
    with open(rutaArchivo, 'r', encoding='utf-8', errors='ignore') as archivo:
        return normalizarTexto(archivo.read(), opciones)

def recorrerDirectorio(rutaDirectorio: str):
    for root, dirs, files in os.walk(rutaDirectorio):
        for file in files:
            rutaArchivo = os.path.join(root, file)
            yield rutaArchivo
