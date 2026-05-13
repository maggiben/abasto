#!/bin/bash

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

(

cd "$REPO_ROOT" || {
  echo "# ERROR: cannot cd to $REPO_ROOT"
  echo "100"
  exit 1
}

echo "# Starting database"
docker compose up -d postgres &

echo "10"
sleep 2

echo "# Starting backend..."
nohup bash -c "cd \"$REPO_ROOT/backend\" && exec ./start.sh" >>/tmp/abasto-backend.log 2>&1 &

echo "40"
sleep 5

echo "# Installing frontend..."
cd "$REPO_ROOT/frontend" || {
  echo "# ERROR: missing $REPO_ROOT/frontend"
  echo "100"
  exit 1
}
npm install >>/tmp/abasto-frontend-install.log 2>&1

echo "60"
echo "# Building frontend..."
npm run build >>/tmp/abasto-frontend-build.log 2>&1

echo "70"
sleep 5

echo "# Starting frontend..."
nohup npm run standalone >>/tmp/abasto-frontend-standalone.log 2>&1 &

echo "90"
sleep 5

echo "# Opening browser..."
nohup firefox --kiosk http://localhost:3000/es >/dev/null 2>&1 &

echo "100"
) | zenity --progress \
  --title="Starting Abasto" \
  --text="Initializing..." \
  --percentage=0 \
  --auto-close \
  --width=400
