#!/bin/bash

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# zenity / .desktop / cron often get a tiny PATH; Node is frequently under $HOME (nvm, fnm, volta).
ensure_node_on_path() {
  if command -v npm >/dev/null 2>&1; then
    return 0
  fi
  export PATH="${HOME:-}/.local/bin:${HOME:-}/.volta/bin:${PATH:-/usr/local/bin:/usr/bin:/bin}"
  if [ -s "${HOME:-}/.nvm/nvm.sh" ]; then
    NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
    export NVM_DIR
    # shellcheck disable=SC1090
    . "$NVM_DIR/nvm.sh" --no-use
    nvm use default >/dev/null 2>&1 || nvm use node >/dev/null 2>&1 || true
  fi
  if command -v fnm >/dev/null 2>&1; then
    eval "$(fnm env 2>/dev/null)" || true
  fi
  if ! command -v npm >/dev/null 2>&1; then
    echo "# ERROR: npm not in PATH (non-interactive / GUI). Add Node to PATH or install system node/npm."
    return 1
  fi
}

wait_postgres() {
  local start=$SECONDS
  echo "# Waiting for PostgreSQL to accept connections..."
  while true; do
    if (
      cd "$REPO_ROOT" && docker compose exec -T postgres pg_isready -U abasto -d abasto
    ) >/dev/null 2>&1; then
      return 0
    fi
    if ((SECONDS - start >= 180)); then
      echo "# ERROR: PostgreSQL not ready after 180s (see: docker compose logs postgres)"
      return 1
    fi
    sleep 2
  done
}

# Wait until an HTTP endpoint responds (curl or wget).
wait_http() {
  local url=$1 desc=$2 max=${3:-600}
  local start=$SECONDS
  echo "# Waiting for $desc..."
  while true; do
    if command -v curl >/dev/null 2>&1; then
      if curl -fsS --connect-timeout 2 --max-time 8 "$url" >/dev/null 2>&1; then
        return 0
      fi
    elif command -v wget >/dev/null 2>&1; then
      if wget -q --spider --timeout=10 "$url" >/dev/null 2>&1; then
        return 0
      fi
    else
      echo "# ERROR: need curl or wget to probe $desc"
      return 1
    fi
    if ((SECONDS - start >= max)); then
      echo "# ERROR: timeout waiting for $desc (${max}s)"
      return 1
    fi
    sleep 2
  done
}

# Free ports and containers from a prior run so this script can start cleanly (avoids double binds / restarts).
stop_existing_abasto_services() {
  echo "# Stopping any previous Abasto services..."
  (cd "$REPO_ROOT" && docker compose stop) >/dev/null 2>&1 || true
  if [ -x "$REPO_ROOT/backend/stop.sh" ]; then
    (cd "$REPO_ROOT/backend" && bash ./stop.sh) >/dev/null 2>&1 || true
  fi
  local pids
  pids="$(lsof -ti :3000 2>/dev/null || true)"
  if [ -n "${pids}" ]; then
    echo "# Stopping process(es) on port 3000..."
    kill ${pids} 2>/dev/null || true
    sleep 1
    pids="$(lsof -ti :3000 2>/dev/null || true)"
    if [ -n "${pids}" ]; then
      kill -9 ${pids} 2>/dev/null || true
    fi
  fi
  sleep 1
}

(

cd "$REPO_ROOT" || {
  echo "# ERROR: cannot cd to $REPO_ROOT"
  echo "100"
  exit 1
}

ensure_node_on_path || {
  echo "100"
  exit 1
}

stop_existing_abasto_services

echo "# Starting database"
docker compose up -d postgres || {
  echo "# ERROR: docker compose up postgres failed"
  echo "100"
  exit 1
}
wait_postgres || {
  echo "100"
  exit 1
}

echo "10"

echo "# Starting backend..."
nohup bash -c "cd \"$REPO_ROOT/backend\" && exec ./start.sh" >>/tmp/abasto-backend.log 2>&1 &

echo "25"

echo "# Installing frontend..."
cd "$REPO_ROOT/frontend" || {
  echo "# ERROR: missing $REPO_ROOT/frontend"
  echo "100"
  exit 1
}
npm install >>/tmp/abasto-frontend-install.log 2>&1 || {
  echo "# ERROR: npm install failed (see /tmp/abasto-frontend-install.log)"
  echo "100"
  exit 1
}

echo "45"
echo "# Building frontend..."
npm run build >>/tmp/abasto-frontend-build.log 2>&1 || {
  echo "# ERROR: npm run build failed (see /tmp/abasto-frontend-build.log)"
  echo "100"
  exit 1
}

echo "60"
wait_http "http://127.0.0.1:8000/health" "API (backend finished starting)" 600 || {
  echo "# ERROR: API did not come up (see /tmp/abasto-backend.log)"
  echo "100"
  exit 1
}

echo "75"
echo "# Starting frontend..."
nohup bash -lc "cd \"$REPO_ROOT/frontend\" && npm run standalone" >>/tmp/abasto-frontend-standalone.log 2>&1 &

wait_http "http://127.0.0.1:3000/es" "Next.js standalone" 180 || {
  echo "# ERROR: frontend did not listen on :3000 (see /tmp/abasto-frontend-standalone.log)"
  echo "100"
  exit 1
}

echo "90"
echo "# Opening browser..."
nohup firefox --kiosk http://localhost:3000/es >/dev/null 2>&1 &

echo "100"
) | zenity --progress \
  --title="Starting Abasto" \
  --text="Initializing..." \
  --percentage=0 \
  --auto-close \
  --width=400
