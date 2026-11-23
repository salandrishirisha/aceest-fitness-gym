#!/usr/bin/env bash
# Revert a strategy to the last stable version.
# Usage: scripts/rollback.sh <rolling|blue-green|canary|shadow|ab-testing|all>
set -euo pipefail
NS=aceest

rollback_rolling() {
  kubectl -n "$NS" rollout undo deployment/aceest-rolling
  kubectl -n "$NS" rollout status deployment/aceest-rolling --timeout=180s
}

rollback_blue_green() {
  local live previous
  live=$(kubectl -n "$NS" get service aceest-bg -o jsonpath='{.spec.selector.color}')
  previous=$([ "$live" = "blue" ] && echo green || echo blue)
  kubectl -n "$NS" patch service aceest-bg -p \
    "{\"spec\":{\"selector\":{\"app\":\"aceest-bg\",\"color\":\"${previous}\"}}}"
  echo "Traffic switched back from ${live} to ${previous}"
}

rollback_canary() {
  kubectl -n "$NS" scale deployment/aceest-canary-canary --replicas=0
}

rollback_shadow() {
  kubectl -n "$NS" annotate ingress aceest-shadow nginx.ingress.kubernetes.io/mirror-target-
  kubectl -n "$NS" scale deployment/aceest-shadow-shadow --replicas=0
}

rollback_ab() {
  kubectl -n "$NS" delete ingress aceest-ab-b --ignore-not-found
  echo "All A/B traffic now served by variant A"
}

case "${1:?strategy required}" in
  rolling) rollback_rolling ;;
  blue-green) rollback_blue_green ;;
  canary) rollback_canary ;;
  shadow) rollback_shadow ;;
  ab-testing) rollback_ab ;;
  all) rollback_rolling; rollback_blue_green; rollback_canary; rollback_shadow; rollback_ab ;;
  *) echo "Unknown strategy: $1" >&2; exit 2 ;;
esac
