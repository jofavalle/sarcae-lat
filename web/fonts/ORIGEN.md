# Origen de las fuentes IBM Plex

Dos familias, como permite la ADR-001: **IBM Plex Sans** para el texto y **IBM Plex Mono** para
cifras, rótulos y datos. Licencia SIL Open Font License 1.1, en `OFL-ibm-plex-sans.txt` y
`OFL-ibm-plex-mono.txt`, que solo se diferencian en la línea de copyright de IBM Corp.

Vienen de los paquetes de Fontsource en el registro oficial de npm, que reempaquetan las
fuentes de IBM con su licencia. Se versionan tal como vienen, sin renombrarlas ni editarlas:
solo el subconjunto latino (cubre el español: tildes, ñ, ü, ¿ y ¡) y los pesos que se usan.

| Paquete | Tarball | Integridad (`dist.integrity`, comprobada sobre el tarball descargado) |
|---|---|---|
| `@fontsource/ibm-plex-sans` 5.3.0 | `https://registry.npmjs.org/@fontsource/ibm-plex-sans/-/ibm-plex-sans-5.3.0.tgz` | `sha512-CbE4CbbEEZJX860XyUiRpsksXIQR8Rp2XDva2VO53NJox9tVNtusrysd2x5YkUEY3ErQ66W1IiiQL8/wihhw5w==` |
| `@fontsource/ibm-plex-mono` 5.3.0 | `https://registry.npmjs.org/@fontsource/ibm-plex-mono/-/ibm-plex-mono-5.3.0.tgz` | `sha512-eTgnZjZEGk1QtD3ZstF+Vclo2HLAni8YMy34/DxllwZvyz1lR/1RF/xTiAquOBO7MvqBx8D2Ig2WCPMVfdZu7Q==` |

**Descarga:** 2026-11-28T00:59:46Z, en un directorio temporal fuera del repositorio. De cada
tarball se extrajeron solo estos archivos, y no se ejecutó nada de lo que trae.

| Archivo | En el tarball | Bytes | SHA-256 |
|---|---|---|---|
| `ibm-plex-sans-latin-400-normal.woff2` | `package/files/` de ibm-plex-sans | 22588 | `3b646991d30055a93a4ecc499713d4347953a74a947ecab435ab72070cbdab0e` |
| `ibm-plex-sans-latin-600-normal.woff2` | `package/files/` de ibm-plex-sans | 24252 | `8960851d691c054ed38e259bdcf1a6190d157b4203ed5bb32c632a863fb8ec2f` |
| `ibm-plex-mono-latin-400-normal.woff2` | `package/files/` de ibm-plex-mono | 14708 | `08949f728dc52d528e69b1667d15c89a5686a4ee9a296ff90983985f99c380f7` |
| `ibm-plex-mono-latin-500-normal.woff2` | `package/files/` de ibm-plex-mono | 14888 | `01d285447409c8a588692162439a038b8cbd7871309ee20267b0d2d91c6e8e22` |
| `OFL-ibm-plex-sans.txt` | `package/LICENSE` de ibm-plex-sans | 4429 | `d0283623ef57e722fd0eb688a8041589670c608ab780cd3612d06ba6f153d3fd` |
| `OFL-ibm-plex-mono.txt` | `package/LICENSE` de ibm-plex-mono | 5299 | `23b0a9d0c6d3f140a0b77e483c5cfa6bba574325ef5cb189ed9f2fec4884533f` |

Los cuatro woff2 suman 76,4 KB, por debajo de los 80 KB de tipografía de la primera pantalla
(ADR-001, "El presupuesto de carga").

Para comprobarlo, con los tarballs descargados en otra carpeta:

```
tar -xzf ibm-plex-sans-5.3.0.tgz package/LICENSE package/files/ibm-plex-sans-latin-400-normal.woff2 package/files/ibm-plex-sans-latin-600-normal.woff2
sha256sum package/LICENSE package/files/*.woff2
```
