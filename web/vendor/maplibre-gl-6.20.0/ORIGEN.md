# Origen de MapLibre GL JS 6.20.0

Estos cuatro archivos vienen del paquete oficial de npm y se versionan tal como vienen, sin
renombrarlos ni editarlos. `maplibre-gl.mjs` carga el worker desde su misma carpeta
(ADR-001). La licencia es BSD-3-Clause, en `LICENSE.txt`.

- **Paquete:** `https://registry.npmjs.org/maplibre-gl/-/maplibre-gl-6.20.0.tgz`
- **Integridad del tarball** (`dist.integrity` en `https://registry.npmjs.org/maplibre-gl/6.20.0`, que
  coincide con el sha512 calculado sobre el tarball descargado):
  `sha512-7manvqXeNoN0mKRzenYDopkb3VW9j7iag45RvopkOVFZ7c+La7CBWtK8eBS5bKrI6NyxqAIxPxIG1PMcotcY1w==`
- **Descarga:** 2026-11-27T23:56:37Z, en un directorio temporal fuera del repositorio. Del tarball
  se extrajeron solo estos cuatro archivos, y no se ejecutó nada de lo que trae.

| Archivo | En el tarball | Bytes | SHA-256 |
|---|---|---|---|
| `maplibre-gl.mjs` | `package/dist/maplibre-gl.mjs` | 1120720 | `3e7652abcc851c11130c2cf8420466a6406fa21005b7dead60c3cbd822daf5f9` |
| `maplibre-gl-worker.mjs` | `package/dist/maplibre-gl-worker.mjs` | 556631 | `03106a5a6e0cff7d459d36f6ca0c3fdea15cfcacec85b5ad19370a49512de598` |
| `maplibre-gl.css` | `package/dist/maplibre-gl.css` | 71596 | `a90798a1953017790e590f7e1bd35ff103a8a4263972cb47290b78adf86f8c20` |
| `LICENSE.txt` | `package/LICENSE.txt` | 5984 | `ee5fc05a0677eaf69601d2c7db0d9ecd6cc27c3abc1d0733bc9ed34707cf8ef2` |

Para comprobarlo, con el tarball descargado en otra carpeta:

```
tar -xzf maplibre-gl-6.20.0.tgz package/dist/maplibre-gl.mjs package/dist/maplibre-gl-worker.mjs package/dist/maplibre-gl.css package/LICENSE.txt
sha256sum package/dist/maplibre-gl.mjs package/dist/maplibre-gl-worker.mjs package/dist/maplibre-gl.css package/LICENSE.txt
```
