# Abasto ERP – Architecture

## Frontend

- Framework: Next.js version 16 or higher, use the App Router
- UI Library: Material UI (MUI)
- Forms: react-hook-form
- State: jotai
- i18n: required (Spanish + English)

### Requirements
- Minimal custom CSS
- Fully responsive
- POS optimized for speed and keyboard navigation

---

## Backend

- Language: Python
- Framework: FastAPI
- API Docs: Swagger (auto-generated)
- Validation: Pydantic

---

## Database

- PostgreSQL

---

## API

- RESTful
- JWT Authentication
- Public vs private endpoints must be clearly defined

---

## Infrastructure

- Fully Dockerized
- Runs on:
  - Linux
  - Mac
  - Windows

---

## CI/CD

- GitHub Actions:
  - Test
  - Build
  - Release

---

## Testing

- Minimum **90% coverage**
- Includes:
  - Unit tests
  - End-to-end tests

---

## Hardware Constraints

Target device:
- Raspberry Pi 4 (8GB RAM)

### Implications:
- Minimize disk writes (SD card longevity)
- Lightweight services
- Efficient queries
- Avoid heavy background jobs

---

## Boot Requirements

- Must start automatically on OS boot
- CLI startup support
