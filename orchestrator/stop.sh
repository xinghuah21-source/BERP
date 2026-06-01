#!/bin/bash
set -e

cd "$(dirname "$0")"

docker compose -f docker-compose.full.yml down -v
