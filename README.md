# Proyecto RIT parte 2: Indexador de colección

**Tema:** Intervención de Estados Unidos en América Latina  

**Autores:** Elías Ramírez Hernández, Ignacio Ramírez Sandí.  

**Curso:** Recuperación de la Información Textual.

## ¿Qué vamos a hacer?

La idea es indexar la colección de 16GB que tenemos, usando 2 tipos de indexador: uno en Lucene (impLucine/)
y otro propio (impPropia/). La estructura del proyecto es tentativamente la siguiente:

```
indexador/
|
|-- config/
|   |-- indexer.conf          # archivo de configuración para ambos indexadores
|-- impLucene/
|   |-- IndexadorLucine.java
|   |-- Main.java
|   |-- pom.xml               # dependencias para el de Lucine
|-- impPropia/
|   |-- indexadorAPata.py
|-- output/
|   |-- indexLucene.bin
|   |-- indexAPata.bin
|-- normalizar.py             # limpiar stopwords y otra basura de la colección
|-- README.md                 # este archivo
```

## ¿Cómo se piensa hacerlo?

### Para el indexador hecho a pata

Primero debemos limpiar la colección. Para esto podemos hacer un programa en Python separado que borre stopwords, trunque
palabras, acomode fechas, busque sinónimos en un tesauro.

## TODO:
 - [] Crear el script de normalización de la colección.
 - [] Empezar a implementar el indexador a pata y aprender cómo crear un índice en archivo binario.
 - [] Investigar Lucene para implementar el indexador en Java.