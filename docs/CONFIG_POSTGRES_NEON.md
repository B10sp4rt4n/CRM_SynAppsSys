# Configuracion Neon/PostgreSQL

Usa una credencial rotada y guardala fuera del codigo fuente.

## Opcion 1: Streamlit

Crea el archivo `.streamlit/secrets.toml` en la raiz del repo con este contenido:

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require&channel_binding=require"
```

Este archivo esta ignorado por git. El ejemplo versionado esta en `.streamlit/secrets.toml.example`.

## Opcion 2: Shell local / scripts

Exporta la variable antes de ejecutar scripts:

```bash
export DATABASE_URL="postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require&channel_binding=require"
```

Si quieres dejar un recordatorio local, usa `.env` en la raiz del repo. El archivo de ejemplo versionado es `.env.example`.

## Recomendacion operativa

- Para la app de Streamlit: usa `.streamlit/secrets.toml`.
- Para scripts, migraciones y utilidades CLI: usa `DATABASE_URL` en el entorno.
- No vuelvas a pegar credenciales reales en archivos versionados.