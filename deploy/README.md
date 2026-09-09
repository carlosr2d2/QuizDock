# Staging (VPS + Docker)

Un solo servidor con el mismo Compose que en local, pero en modo producción: Next `standalone`, sin `--reload`, sin Mailpit/Flower, y Caddy en 80/443.

Postgres, Redis y el almacenamiento de PDFs **no** se publican a internet.

## Requisitos

- VPS Ubuntu 22.04+ (2 GB RAM mínimo; 4 GB si vas a generar con LLM)
- Dominio con registro **A** (y AAAA si hay IPv6) apuntando al VPS, por ejemplo `staging.tudominio.com`
- Puertos **80** y **443** abiertos (Let's Encrypt)
- Docker Engine + Compose plugin

## En el servidor

```bash
sudo apt-get update
sudo apt-get install -y git docker.io docker-compose-v2
sudo usermod -aG docker "$USER"   # cierra sesión y vuelve a entrar
git clone https://github.com/carlosr2d2/QuizDock.git
cd QuizDock
cp deploy/staging.env.example .env.staging
```

Edita `.env.staging`:

- `STAGING_SITE` = hostname (sin `https://`)
- `APP_PUBLIC_URL` = `https://` + ese hostname
- `ACME_EMAIL` = correo para avisos de Let's Encrypt
- `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `API_SECRET_KEY` = `openssl rand -hex 32`
- `LLM_API_KEY` si quieres Gemini en staging

```bash
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build
```

La API aplica `alembic upgrade head` al arrancar (incluye `0016_audit_events`).

Comprueba:

- `https://staging.tudominio.com` — web
- `https://staging.tudominio.com/health` — `{"status":"ok"}`
- `https://staging.tudominio.com/api/docs` — OpenAPI

Datos de demo (opcional, **borra** usuarios y documentos de esa base):

```bash
docker compose -f docker-compose.staging.yml --env-file .env.staging exec api python scripts/reset_dev_db.py --yes
```

## Actualizar

```bash
cd QuizDock
git pull
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build
```

Los volúmenes (`staging_postgres_data`, PDFs, certificados) se conservan.

## Notas

- El navegador llama a `/api/v1/...` en el mismo origen; Caddy reenvía al API. No hace falta un subdominio `api.`.
- Sin SMTP, las invitaciones no llegan al buzón; el enlace queda en los logs de `api` (`docker compose -f docker-compose.staging.yml logs api`).
- La pasarela simulada sigue activa en staging (`PAYMENT_ALLOW_SIMULATED=true`). Apágala solo en producción real.
- Redis exige contraseña; no uses `@`, `:`, `/` ni espacios en `REDIS_PASSWORD`.
- No ejecutes el Compose de desarrollo (`docker compose up`) en el mismo host que staging: el de desarrollo publica Postgres y Redis.

## HTTP sin dominio (solo prueba interna)

Si aún no hay DNS, Caddy no puede sacar certificado. Pon en `.env.staging`:

```
STAGING_SITE=http://IP_PUBLICA
APP_PUBLIC_URL=http://IP_PUBLICA
```

Las cookies de sesión en producción van con `Secure` y **no** se enviarán por HTTP. Para una prueba usable hace falta HTTPS y un hostname.
