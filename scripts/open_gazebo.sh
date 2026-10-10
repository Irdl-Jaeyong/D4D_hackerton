#!/usr/bin/env bash
set -euo pipefail
exec docker exec -e IGN_PARTITION=navis-d4d-prep d4d-navis-prep ign gazebo -g
