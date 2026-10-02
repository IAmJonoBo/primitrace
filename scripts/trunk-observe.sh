#!/usr/bin/env bash
set -euo pipefail

# Trunk failure dossiers include their execution environment. Run the
# observational check with an explicit allow-list so host credentials and
# unrelated service configuration cannot enter diagnostics or CI logs.
env -i \
	CI=true \
	HOME="$HOME" \
	PATH="$PATH" \
	TMPDIR="${TMPDIR:-/tmp}" \
	trunk check --ci
