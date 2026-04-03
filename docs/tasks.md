# Abasto ERP – Implementation Plan

Tasks are **atomic** (one clear deliverable) and **executable** (a developer can complete them without resolving unspecified design forks). Order within each section is roughly dependency-aware; parallel work is possible where dependencies do not block.

---

## Backend tasks

### Foundation

1. Initialize Python project with FastAPI, Pydantic v2, and `pyproject.toml` / lockfile; expose a `/health` route and auto-generated OpenAPI at `/docs`.
2. Add configuration via environment variables (e.g. `pydantic-settings`): database URL, JWT secret, token TTL, CORS origins, and log level.
3. Integrate PostgreSQL with an async driver and SQLAlchemy 2.x (or equivalent); implement session/dependency injection for request-scoped DB access.
4. Add Alembic with async migrations; document the workflow (`alembic revision`, `upgrade`).
5. Define API route modules and a clear split between **public** (unauthenticated) and **private** (JWT) routers; document the rule in code (e.g. router prefixes + dependencies).

### Identity & access

6. Implement `User` model (id, email or username, hashed password, timestamps, optional flags for staff/admin).
7. Implement password hashing (argon2 or bcrypt) and verification helpers; never store plaintext passwords.
8. Implement JWT creation and validation (access token); add FastAPI dependencies `get_current_user` and optional `require_role`.
9. Implement `POST /auth/register`, `POST /auth/login`, and `GET /auth/me` (or equivalent) with Pydantic request/response models.
10. Add seed or migration path for an initial admin user in non-production environments (document only; no hardcoded secrets in repo).

### Products & inventory

11. Implement `Product` model: name, price, cost, computed or stored margin, barcode (unique where set), weight, optional expiration date, optional image URL or blob reference.
12. Implement inventory model(s) supporting **bulk and unit** stock and **fractional quantities** (e.g. decimal weight); link to `Product`.
13. Implement product CRUD API (create, read, update, soft-delete or hard-delete per chosen policy) with pagination and search (name, barcode).
14. Implement inventory adjustment endpoints (increase/decrease/set) with validation and idempotency key or audit reference where needed.
15. Implement queries for **low stock** (threshold per product or global default) and **expiring soon** (configurable window).
16. Implement CSV **export** of products (and inventory snapshot columns as specified in export contract).
17. Implement CSV **import** with column mapping validation, row-level errors in response, and optional dry-run mode.

### POS support (server-side)

18. Implement a **price check** endpoint (barcode or product id → price, availability) usable by POS “dry mode” without creating a sale.
19. Implement **checkout** or **sale** domain: persist completed sales with line items, quantities, unit prices, taxes breakdown, and timestamps (supports receipt data and audit).
20. Implement tax calculation rules as configuration (single rate or simple table) so receipt totals match stored lines.

### Orders (customer & vendor)

21. Implement **customer order** model and states (e.g. pending, paid, fulfilled, cancelled); line items referencing products and quantities.
22. Implement **guest checkout** API: create order without persisted user, with guest contact fields as required.
23. Implement **registered user** order APIs: list/create tied to `User`.
24. Implement **vendor / purchase order** model and CRUD APIs for restocking workflows.

### Ecommerce-facing API

25. Implement read-only **catalog** endpoints: list products, product detail, price, availability (no auth).
26. Implement cart/session strategy for web checkout (server-side cart id or client-held payload with server validation on submit—pick one and document).

### Admin & operations

27. Implement admin-only **bulk price update** (by id list or filter) with audit entries per change.
28. Implement **inventory audit** export or report endpoint (snapshot + deltas as per product spec).
29. Implement **user management** APIs for admin (list, disable, role assignment).

### Notifications

30. Implement `Notification` model (type, payload, user or broadcast, read flag, created_at).
31. Implement APIs to list notifications, mark read, and create notifications from domain events (low stock, expiration, order updates).

### Analytics

32. Implement aggregated queries (or materialized views) for sales, revenue, ROI inputs, inventory value, and order counts.
33. Implement analytics API with **time buckets**: daily, weekly, monthly, yearly (query params + validated date ranges).

### Audit

34. Implement append-only **audit log** table (actor, action, entity type/id, before/after JSON or diff, timestamp).
35. Implement a small internal service or dependency to record audit entries from product, price, inventory, and order mutations.

### Receipts & printing integration

36. Implement a **receipt DTO** endpoint or include receipt block in sale response: date/time, items, quantities, line totals, taxes, grand total (matches product spec).
37. Document ESC/POS payload strategy: either return structured JSON for a local print agent, or integrate a thin print queue model—choose one and implement the API contract.

### Quality & API polish

38. Add global exception handlers and consistent error JSON; add security headers middleware.
39. Configure `pytest`, async test client, and test database; add factories/fixtures for users and products.
40. Add tests until **≥90% coverage** on backend code; prioritize auth, checkout, inventory, and CSV paths.
41. Add optional rate limiting for public endpoints if exposed beyond LAN.

---

## Frontend tasks

### Foundation

1. Initialize **Next.js** (App Router) with TypeScript; strict mode; path aliases.
2. Add **Material UI** with a theme (light/dark); central theme tokens for **large typography** and **high contrast** for POS surfaces.
3. Add **jotai** and define atoms for auth token, user profile, and locale.
4. Add **react-hook-form** and shared form field wrappers aligned with MUI.
5. Configure **i18n** (Spanish + English): routing or dictionary loading; ensure all user-facing strings use translations.
6. Add API client layer (fetch/axios) with base URL from env, JWT attachment, and typed error handling.
7. Define layout groups: `(marketing)`, `(app)`, `(pos)`, `(admin)` with appropriate shells and navigation.

### POS (highest priority)

8. Build POS shell: minimal chrome, focus management, **keyboard-only** navigation map documented in README or in-app help.
9. Implement hidden or focused input for **barcode scanner** (keyboard wedge) with debounce and Enter handling.
10. Implement cart: add/remove lines, edit quantity **without rescanning**, support **fractional quantities** where product is weight-based.
11. Implement **manual price override** UI with confirmation and permission guard (admin or PIN—align with backend).
12. Implement **product search** (keyboard-first): modal or side panel with arrow-key navigation.
13. Implement **dry mode** (price check only): calls backend price-check; no sale persisted.
14. Implement **embedded calculator** (numpad-oriented) usable without mouse.
15. Implement checkout flow: confirm total, taxes display, complete sale; minimal steps/clicks.
16. Implement **receipt** preview (structured) and **print** action: browser print and/or integration point for ESC/POS (per backend contract).
17. Add POS-specific responsive rules: optional fullscreen; touch optional.

### Inventory

18. Build product list with search, filters, and pagination.
19. Build product create/edit forms (all attributes from product spec including optional image upload).
20. Build inventory adjustment UI (stock changes, fractional input).
21. Build expiration visibility (list/filter expiring soon).
22. Wire CSV **import** (file picker, progress, error report) and **export** (download).

### Orders

23. Build customer order list and detail (status, lines) for staff/admin.
24. Build vendor order (purchase) list and create/edit flows.

### Ecommerce (web)

25. Build public **product catalog** and product detail pages (price, availability).
26. Build cart and **guest checkout** flow (forms with react-hook-form).
27. Build **user registration** and **login** pages; persist session via JWT.
28. Build **order tracking** page (token in URL or logged-in list—match backend).

### Admin panel

29. Build admin login gate and dashboard shell.
30. Build product management views (reuse inventory components where possible).
31. Build **inventory audit** UI (read-only report + filters).
32. Build **bulk price/margin** editing UI.
33. Build **user management** UI.
34. Build **order management** and **delivery planning** placeholder or MVP (list + status updates).

### Notifications & analytics

35. Build notifications inbox (list, mark read) and header/bell indicator.
36. Build **analytics dashboard**: sales, revenue, ROI, inventory value, orders; **period selector** (day/week/month/year).

### Audit

37. Build admin **activity log** viewer with filters (entity, user, date range).

### Testing & UX constraints

38. Add **Playwright** (or Cypress) E2E tests for critical flows: login, add to cart, checkout, one admin path.
39. Verify **keyboard-only** POS path in E2E or manual test checklist; document shortcuts.
40. Ensure **fully responsive** layouts for non-POS areas; POS may fix minimum width with scroll as needed.

---

## Infra tasks

### Containerization

1. Author **`Dockerfile`** for the backend (multi-stage, non-root user, slim base image).
2. Author **`Dockerfile`** for the frontend (Next.js standalone output where applicable).
3. Add **`docker-compose.yml`** (or Compose v2 equivalent) with services: PostgreSQL (volume for data), backend, frontend; healthchecks and dependency order.
4. Add **`.env.example`** at repo root documenting all required variables for compose and local dev (no secrets).
5. Document **one-command** local bring-up (`docker compose up`) and teardown.

### CI/CD

6. Add **GitHub Actions** workflow: install deps, lint, **test**, **build** images on pull request.
7. Add workflow for **tagged releases** (build + push images to registry or attach artifacts—choose one strategy and document).
8. Document recommended GitHub branch protection (require CI green before merge) for maintainers.

### Runtime on target hardware (Raspberry Pi / low resource)

9. Configure logging to **stdout** primarily; avoid verbose file logging on SD card; document **log rotation** if files are used.
10. Document PostgreSQL tuning for Pi: shared_buffers, effective_cache_size, and connection limits; optional `docker-compose` overrides.
11. Add **restart policies** (`unless-stopped`) for compose services; document **boot order** (Docker daemon starts stack).

### Boot & CLI

12. Provide **CLI or script** to start the stack (documented in README section—implementation: e.g. `scripts/start.sh` invoking compose).
13. Add example **systemd** unit(s) to start Docker Compose stack on OS boot (Linux/Pi); document path and user.

### Offline-first & no cloud

14. Document **LAN-only** deployment: bind services to appropriate interfaces, firewall notes, and optional local DNS/hostname.
15. Ensure build and runtime **do not call external cloud APIs** for core paths (audit dependencies in lockfiles periodically).

### Security & backups

16. Document **backup** procedure for PostgreSQL volume (dump + restore commands).
17. Document **HTTPS** termination options for LAN (reverse proxy vs none) without mandating cloud certs.

---

## Suggested execution order (cross-cutting)

1. Infra tasks 1–5 (compose + env) to give everyone a shared runtime.
2. Backend foundation + auth (backend 1–10).
3. Frontend foundation + auth UI (frontend 1–7, 27–28).
4. POS vertical slice: backend 18–20 + frontend POS 8–17.
5. Inventory + CSV (backend 11–17 + frontend 18–22).
6. Orders + ecommerce API/UI (backend 21–26 + frontend 23–28).
7. Admin, notifications, analytics, audit (remaining backend + frontend sections).
8. CI (infra 6–7), Pi hardening (infra 9–13), offline docs (infra 14–17).
9. Coverage push (backend 40, frontend 38–39) until **≥90%** global test bar from architecture.

This plan satisfies **constraints**: offline-capable deployment, keyboard-first POS, Pi-friendly services, minimal disk writes (logging/DB practices), no cloud dependency, CSV and ESC/POS support via APIs and client integration points.
