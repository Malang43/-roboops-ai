#!/usr/bin/env bash

set -o pipefail

echo "Waiting for RoboOps PostgreSQL on 127.0.0.1:5433..."

for attempt in $(seq 1 60); do
  container_ready=false
  host_port_ready=false

  if docker exec roboops-postgres \
    pg_isready \
    -U roboops_app \
    -d roboops \
    >/dev/null 2>&1; then
    container_ready=true
  fi

  if timeout 2 bash -c \
    '</dev/tcp/127.0.0.1/5433' \
    >/dev/null 2>&1; then
    host_port_ready=true
  fi

  if [ "$container_ready" = true ] &&
     [ "$host_port_ready" = true ]; then
    echo "PostgreSQL container and host port are ready."
    exit 0
  fi

  echo "PostgreSQL not ready: attempt ${attempt}/60"
  sleep 2
done

echo "PostgreSQL did not become accessible."
exit 1
