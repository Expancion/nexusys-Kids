#!/bin/sh
set -e

caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
CADDY_PID=$!

echo "[caddy] Waiting for internal CA to be generated..."
until [ -f /data/caddy/pki/authorities/local/root.crt ]; do
  sleep 1
done

cp /data/caddy/pki/authorities/local/root.crt /certs/caddy-root-ca.crt
echo "[caddy] Root CA exported to /certs/caddy-root-ca.crt"

wait $CADDY_PID
