import argparse
import json
import math
import os
import re
import struct
import sys
import time
from collections import defaultdict
from datetime import datetime

# por si se ejecuta desde raiz
try:
    from . import normalizar as norm
except ImportError:
    import normalizar as norm


def escribirTexto(archivo, texto):
    datos = texto.encode('utf-8')
    archivo.write(struct.pack('<I', len(datos)))
    archivo.write(datos)


def leerTexto(archivo):
    largo = struct.unpack('<I', archivo.read(4))[0]
    return archivo.read(largo).decode('utf-8', errors='replace')


def construirIndice(rutaColeccion, rutaIndice, opciones, limite=0):
    inicio = time.time()
    os.makedirs(rutaIndice, exist_ok=True)

    archivos = []
    for root, dirs, files in os.walk(rutaColeccion):
        dirs.sort()
        for nombre in sorted(files):
            # si es txt, metalo
            if nombre.endswith('.txt'):
                archivos.append(os.path.join(root, nombre))
    archivos.sort()
    if limite:
        archivos = archivos[:limite]

    postings = defaultdict(list)
    docs = []
    tokensTotales = 0
    saltados = 0
    idiomas = defaultdict(int)

    for ruta in archivos:
        try:
            tokens, idioma, meta = norm.normalizarDocumentoConMetadatos(ruta, opciones)
        except Exception as error:
            saltados += 1
            print(f'aviso: saltado {ruta}: {error}', file=sys.stderr)
            continue

        docId = len(docs)
        tf = defaultdict(int)
        for token in tokens:
            tf[token] += 1
        for token, frecuencia in tf.items():
            postings[token].append((docId, frecuencia))

        relativa = os.path.relpath(ruta, rutaColeccion)
        docs.append((
            meta.get('url') or relativa,
            meta.get('titulo', ''),
            meta.get('fecha', ''),
            len(tokens),
            idioma,
            relativa,
        ))
        tokensTotales += len(tokens)
        idiomas[idioma] += 1

        if len(docs) % 100 == 0:
            print(f'{len(docs)} docs, {tokensTotales} tokens', file=sys.stderr)

    totalPostings = 0
    with open(os.path.join(rutaIndice, 'postings.bin'), 'wb') as fp, \
            open(os.path.join(rutaIndice, 'lexico.bin'), 'wb') as fl:
        for termino in sorted(postings):
            lista = postings[termino]
            escribirTexto(fl, termino)
            fl.write(struct.pack('<II', len(lista), fp.tell()))
            for docId, tf in lista:
                fp.write(struct.pack('<II', docId, tf))
            totalPostings += len(lista)

    with open(os.path.join(rutaIndice, 'docs.bin'), 'wb') as archivo:
        archivo.write(b'DESCL3\x00\x00' + struct.pack('<I', len(docs)))
        for url, titulo, fecha, largo, idioma, relativa in docs:
            escribirTexto(archivo, url)
            escribirTexto(archivo, titulo)
            escribirTexto(archivo, fecha)
            archivo.write(struct.pack('<IB', largo, ('es', 'en', 'pt', 'otro').index(idioma)))
            escribirTexto(archivo, relativa)

    duracion = time.time() - inicio
    stats = {
        'formato': 3,
        'fechaIndexado': datetime.now().isoformat(timespec='seconds'),
        'N': len(docs),
        'tokens': tokensTotales,
        'vocabulario': len(postings),
        'postings': totalPostings,
        'avgdl': (tokensTotales / len(docs)) if docs else 0,
        'saltados': saltados,
        'idiomas': dict(idiomas),
        'tiempo': duracion,
        'opciones': opciones,
    }
    with open(os.path.join(rutaIndice, 'stats.json'), 'w', encoding='utf-8') as archivo:
        json.dump(stats, archivo, ensure_ascii=False, indent=2)

    print(f'indexado: {len(docs)} docs, {tokensTotales} tokens, '
          f'{len(postings)} terminos, {totalPostings} postings, '
          f'{duracion:.1f}s, saltados={saltados}')
    return stats


def cargarIndice(rutaIndice):
    lexico = {}
    with open(os.path.join(rutaIndice, 'lexico.bin'), 'rb') as archivo:
        while True:
            datos = archivo.read(4)
            if not datos:
                break
            largo = struct.unpack('<I', datos)[0]
            termino = archivo.read(largo).decode('utf-8')
            df, offset = struct.unpack('<II', archivo.read(8))
            lexico[termino] = (df, offset)

    docs = []
    with open(os.path.join(rutaIndice, 'docs.bin'), 'rb') as archivo:
        magia, cantidad = struct.unpack('<8sI', archivo.read(12))
        if magia != b'DESCL3\x00\x00':
            raise ValueError('indice viejo o corrupto: volver a ejecutar "indexar"')
        for _ in range(cantidad):
            url = leerTexto(archivo)
            titulo = leerTexto(archivo)
            fecha = leerTexto(archivo)
            largo, codigo = struct.unpack('<IB', archivo.read(5))
            relativa = leerTexto(archivo)
            docs.append((url, titulo, fecha, largo, ('es', 'en', 'pt', 'otro')[codigo], relativa))

    with open(os.path.join(rutaIndice, 'stats.json'), encoding='utf-8') as archivo:
        stats = json.load(archivo)
    return lexico, docs, stats


def buscar(rutaIndice, consulta, opciones, topk=10):
    lexico, docs, stats = cargarIndice(rutaIndice)
    N = stats['N']
    puntajes = defaultdict(float)

    with open(os.path.join(rutaIndice, 'postings.bin'), 'rb') as postings:
        # se puede usar OR en la consulta
        for grupo in re.split(r'\s+OR\s+', consulta, flags=re.IGNORECASE):
            terminos = norm.normalizarTexto(grupo, opciones)
            terminos = [t for t in terminos if t]
            if not terminos:
                continue

            listas = []
            for termino in terminos:
                if termino not in lexico:
                    listas = []
                    break
                df, offset = lexico[termino]
                postings.seek(offset)
                lista = {}
                for _ in range(df):
                    # 2 enteros, little endian
                    docId, tf = struct.unpack('<II', postings.read(8))
                    lista[docId] = tf
                listas.append((df, lista))

            if not listas:
                continue

            comunes = dict(listas[0][1])
            for _, lista in listas[1:]:
                comunes = {d: comunes[d] for d in comunes.keys() & lista.keys()}
            if not comunes:
                continue

            for df, lista in listas:
                idf = math.log((N + 1) / (df + 1)) + 1.0
                for docId in comunes:
                    puntajes[docId] += (1.0 + math.log(lista[docId])) * idf

    resultados = []
    for docId, puntaje in puntajes.items():
        largo = docs[docId][3] or 1
        resultados.append((docId, puntaje / math.sqrt(largo)))
    resultados.sort(key=lambda x: (-x[1], x[0]))
    return [(docId, puntaje, docs[docId]) for docId, puntaje in resultados[:topk]]


def main():
    parser = argparse.ArgumentParser(description='Indexador propio TF/IDF')
    parser.add_argument('comando', choices=['indexar', 'buscar'])
    parser.add_argument('consulta', nargs='?')
    parser.add_argument('--config')
    parser.add_argument('--coleccion')
    parser.add_argument('--indice')
    parser.add_argument('--limite', type=int, default=0)
    parser.add_argument('--topk', type=int, default=10)
    args = parser.parse_args()

    config = norm.cargarConfiguracionCompleta(args.config)

    def ruta(valor):
        return valor if os.path.isabs(valor) else os.path.join(norm.RUTA_RAIZ, valor)

    rutaIndice = ruta(args.indice or config['indexador']['rutaIndice'])

    if args.comando == 'indexar':
        norm.cargarThesaurus(ruta(config['thesaurus']['ruta']))
        coleccion = ruta(args.coleccion or config['coleccion']['rutaColeccion'])
        construirIndice(coleccion, rutaIndice, config['normalizacion'], args.limite)
        return

    if not args.consulta:
        parser.error('falta la consulta')
    norm.cargarThesaurus(ruta(config['thesaurus']['ruta']))
    for docId, puntaje, (url, titulo, fecha, largo, idioma, relativa) in buscar(
            rutaIndice, args.consulta, config['normalizacion'], args.topk):
        print(f'{puntaje:.4f}\t{docId}\t{idioma}\t{fecha or "-"}\t{url}\t{titulo}')


if __name__ == '__main__':
    main()
