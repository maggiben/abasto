
<div align="center">
<br>
<p align="center">
<img src="docs/logo.webp" alt="Abasto" height="72" />
</p>

<p align="center">
Abasto is a friendly ERP 🏬
</p>
</div>

Abasto is a barebone ERP for small stores: a **Next.js** storefront and admin UI, a **FastAPI** backend, and **PostgreSQL**. Checkout can drive a **USB thermal receipt printer** (e.g. XP-58 class devices) when the API runs on a host with USB access.

---

## Prerequisites

| Piece | Version / notes |
|--------|------------------|
| **Docker** & Docker Compose | For the all-in-one stack, or for Postgres-only hybrid dev |
| **Python** | 3.11+ (backend; CI uses 3.12) |
| **Node.js** | 22+ (frontend; matches the production Docker image) |
| **USB printing** | **Linux** (including Raspberry Pi): libusb + device access. **macOS**: run the API on the Mac (not inside Docker Desktop) for reliable USB; install [libusb](https://libusb.info/) (e.g. `brew install libusb`) |

---

## Run everything with Docker

From the repository root:

```bash
docker compose up --build
```

This starts:

| Service | Container | Host port | Role |
|---------|-----------|-----------|------|
| **postgres** | `abasto-postgres` | `5432` | Database (`abasto` / `abasto` / `abasto`) |
| **api** | `abasto-api` | `8000` | FastAPI + Alembic migrations on startup |
| **web** | `abasto-web` | `3000` | Next.js (production build) |

- **Web UI:** [http://localhost:3000](http://localhost:3000)  
- **API:** [http://localhost:8000](http://localhost:8000)  
- **OpenAPI docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

Set a strong secret in production (optional file `.env` next to `docker-compose.yml`):

```env
JWT_SECRET=your-long-random-secret
```

### LAN or custom hostnames

Browsers call the API on the **host**, not the Docker internal service name. If you access the site from another machine or a non-localhost URL:

1. Rebuild the **web** image with the API URL that browsers will use, for example:

   ```bash
   NEXT_PUBLIC_API_URL=http://192.168.1.10:8000 docker compose up --build web
   ```

2. Allow that web origin in CORS for the API, for example:

   ```env
   CORS_ORIGINS=http://192.168.1.10:3000,http://localhost:3000
   ```

---

## Local development (recommended for USB printing on macOS)

A practical setup is **Postgres in Docker** and **API + frontend on the host** so pyusb can see the printer.

### 1. Postgres only

```bash
docker compose up -d postgres
```

Wait until the container is healthy (`pg_isready`).

### 2. Backend

```bash
cd backend
cp .env.example .env
# Edit .env: DATABASE_URL should point at localhost:5432 (default in .env.example is correct for the compose Postgres)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# USB printing — pick one:
#   Raw pyusb only (minimal):
pip install -e ".[printer]"
#   Or pyusb + python-escpos (profiles, cut helpers) when PRINTER_PREFER_ESCPOS=true:
# pip install -e ".[printer_escpos]"

alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Enable and tune the printer in `backend/.env` (see [USB thermal printer](#usb-thermal-printer) below).

### 3. Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local` so the browser talks to your local API:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Then:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

## USB thermal printer

Printing runs **inside the API process** on the machine that has the USB cable. It is optional: if disabled or missing hardware, sales still persist; errors are logged only.

### Environment variables (`backend/.env` or `docker-compose.yml` `api.environment`)

| Variable | Purpose |
|----------|---------|
| `PRINTER_ENABLED` | `true` to print on checkout |
| `PRINTER_USB_VENDOR` | USB vendor id (hex string ok, e.g. `0x0483`) |
| `PRINTER_USB_PRODUCT` | USB product id (e.g. `0x070B`) |
| `PRINTER_PROFILE` | python-escpos capability profile name (e.g. `XP-58`); unknown names fall back to `default` |
| `PRINTER_PREFER_ESCPOS` | `true` to use python-escpos when installed; otherwise raw UTF-8 over pyusb |
| `RECEIPT_STORE_NAME` | Title line on the receipt |

The compose file defaults target a common XP-58-class USB id (`0x0483` / `0x070B`). **Confirm your device** on Linux with `lsusb` and adjust `PRINTER_USB_VENDOR` / `PRINTER_USB_PRODUCT`.

### Docker and USB

`docker-compose.yml` passes through **`/dev/bus/usb`** into the API container so libusb can scan the bus (**Linux hosts**, e.g. Raspberry Pi).

**Docker Desktop on macOS** usually does **not** expose a usable `/dev/bus/usb` tree like Linux. For development printing on a Mac, run **`uvicorn` on the host** (see [Local development](#local-development-recommended-for-usb-printing-on-macos)) instead of relying on USB inside the API container.

### Linux permissions

If you get permission errors accessing the device, add a **udev** rule for your vendor/product so the user running Docker or `uvicorn` can open the device, or run the API as root (not recommended for production).

---

## First admin (staff) user

`POST /auth/register` creates a normal user with `is_staff=false`. Admin product and inventory APIs require **staff**.

After registering, promote your user in PostgreSQL, for example:

```sql
UPDATE users SET is_staff = true WHERE email = 'you@example.com';
```

You can run this with `docker exec -it abasto-postgres psql -U abasto -d abasto` if you use the compose database.

---

## Product catalog

Large CSV exports can be imported via the **staff** admin API (`POST` product import — see OpenAPI at `/docs`). The repo may include a legacy `products.csv` for tooling; the live catalog lives in the database after import.

---

## Useful commands

```bash
# Backend tests (from backend/)
pip install -e ".[dev]"
pytest

# Frontend lint (from frontend/)
npm run lint
```

---

## Repository layout (short)

| Path | Contents |
|------|----------|
| `backend/` | FastAPI app, Alembic migrations, `pyproject.toml` |
| `frontend/` | Next.js 16 app |
| `docker-compose.yml` | Postgres + API + web |
| `docs/logo.webp` | Project logo (used above) |
