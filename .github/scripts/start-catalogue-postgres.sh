#!/usr/bin/env bash
set -euo pipefail

container="catalogue-benchmark-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
secret_file="$RUNNER_TEMP/catalogue-benchmark.secret"
pgpass="$RUNNER_TEMP/catalogue-benchmark.pgpass"
printf 'CATALOG_DB_CONTAINER=%s\n' "$container" >> "$GITHUB_ENV"

umask 077
db_secret="$(openssl rand -hex 24)"
printf '::add-mask::%s\n' "$db_secret"
printf '%s\n' "$db_secret" > "$secret_file"

docker run --detach --name "$container" --publish 127.0.0.1::5432 \
  --mount "type=bind,source=$secret_file,target=/run/secrets/catalogue-db,readonly" \
  --env POSTGRES_DB=catalogue_benchmark \
  --env POSTGRES_USER=catalogue_benchmark \
  --env POSTGRES_PASSWORD_FILE=/run/secrets/catalogue-db \
  postgres:16-alpine

binding="$(docker port "$container" 5432/tcp)"
port="${binding##*:}"
printf '127.0.0.1:%s:catalogue_benchmark:catalogue_benchmark:%s\n' \
  "$port" "$db_secret" > "$pgpass"
unset db_secret
printf 'PGPASSFILE=%s\n' "$pgpass" >> "$GITHUB_ENV"
printf 'DATABASE_URL=postgresql+psycopg2://catalogue_benchmark@127.0.0.1:%s/catalogue_benchmark\n' \
  "$port" >> "$GITHUB_ENV"

for attempt in {1..30}; do
  if docker exec "$container" pg_isready -h 127.0.0.1 -U catalogue_benchmark -d catalogue_benchmark; then
    exit 0
  fi
  sleep 1
done
exit 1
