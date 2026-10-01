#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_BIN_DIR="/home/kali/.local/bin"

install -d "$USER_BIN_DIR"
ln -sfn "$ROOT_DIR/scripts/cfcbot" "$USER_BIN_DIR/CFCbot"
ln -sfn "$ROOT_DIR/scripts/cfcbot" "$USER_BIN_DIR/cfcbot"

printf 'Installed:\n'
printf '  %s\n' "$USER_BIN_DIR/CFCbot"
printf '  %s\n' "$USER_BIN_DIR/cfcbot"
printf 'Run: CFCbot doctor\n'

