#!/usr/bin/env bash
# Build (and optionally push) a Docker image for every tagged release.
# Usage: scripts/build_all_versions.sh <dockerhub-user> [--push]
set -euo pipefail
USER_NAME=${1:?Docker Hub username required}
REPO="docker.io/${USER_NAME}/aceest-fitness"

for tag in v1.0.0 v2.0.0 v3.0.0 v4.0.0; do
  version=${tag#v}
  echo "==> Building ${REPO}:${version} from ${tag}"
  git archive --format=tar "$tag" | docker build -t "${REPO}:${version}" -
  if [ "${2:-}" = "--push" ]; then
    docker push "${REPO}:${version}"
  fi
done
docker tag "${REPO}:4.0.0" "${REPO}:latest"
if [ "${2:-}" = "--push" ]; then
  docker push "${REPO}:latest"
fi
docker images "${REPO}"
