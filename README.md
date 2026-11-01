# Proyecto RIT parte 2: Indexador de colección

**Tema:** Intervención de Estados Unidos en América Latina  

**Autores:** Elías Ramírez Hernández, Ignacio Ramírez Sandí.  

**Curso:** Recuperación de la Información Textual.

## ¿Qué vamos a hacer?

La idea es indexar la colección de 16GB que tenemos, usando 2 tipos de indexador: uno en Lucene (impLucine/) y otro propio (impPropia/). La estructura del proyecto es tentativamente la siguiente:

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
|   |-- normalizar.py         # tokenizar, lematizar, etc.
|   |-- indexadorAPata.py
|-- output/
|   |-- indexLucene.bin
|   |-- indexAPata.bin
|-- README.md                 # este archivo
```

## ¿Cómo se piensa hacerlo?

### Para el indexador hecho a pata

Primero debemos limpiar la colección. ~~Para esto podemos hacer un programa en Python separado que borre stopwords, trunque palabras, acomode fechas, busque sinónimos en un tesauro.~~ Nvm, mejor no modificamos la colección, mejor dejarla como está y trabajar sobre ella. Lo que haremos es crear una minibiblioteca por indexador que preprocese tokens, lematice y lea el  thesaurus para que el indexador bretee mejor. Vamos a trabajar con una pequeña parte de la colección (de unos 500 docs) en coleccion/. 

## TODO:
 - [] Crear ~~el script~~ la biblioteca de normalización de la colección.
 - [] Crear el thesaurus.
 - [] Empezar a implementar el indexador a pata y aprender cómo crear un índice en archivo binario.
 - [] Investigar Lucene para implementar el indexador en Java.