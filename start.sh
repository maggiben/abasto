#!/bin/bash

(

echo "# Starting database"
docker compose up -d postgres &

echo "10"
sleep 2

echo "# Starting backend..."
cd backend
./start.sh &

echo "40"
sleep 5

echo "# Installing and Building frontend..."
cd frontend
npm install >>/tmp/abasto-frontend-install.log 2>&1 && npm run build >>/tmp/abasto-frontend-build.log 2>&1

echo "70"

sleep 5

echo "# Starting frontend..."
npm run standalone >>/tmp/abasto-frontend-standalone.log 2>&1 &

echo "90"
sleep 5

echo "# Opening browser..."
firefox --kiosk http://localhost:3000/es &

echo "100"
) | zenity --progress \
  --title="Starting Abasto" \
  --text="Initializing..." \
  --percentage=0 \
  --auto-close \
  --width=400
