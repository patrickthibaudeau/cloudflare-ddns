#!/usr/bin/env bash
set -euo pipefail

# Multi-arch Docker build helper for Cloudflare DDNS Updater.
# Builds linux/amd64 and linux/arm64 images (configurable) and tags both
# `:latest` and `:v<version>` (or custom) based on ddns/version.py unless overridden.
#
# Requirements:
# - Docker 20.10+ with buildx
# - (For multi-arch) binfmt/qemu automatically handled by buildx create --use (recent Docker)
#
# Usage:
#   ./build.sh                        # build (no push) current arch only, using detected version
#   ./build.sh --push                 # build & push multi-arch (amd64,arm64) with latest + v<version>
#   ./build.sh -n myrepo/cf-ddns --push
#   ./build.sh -v 1.2.3 --push        # explicit version (will tag v1.2.3 and latest)
#   ./build.sh -p linux/amd64,linux/arm64,linux/arm/v7 --push
#
# Options:
#   -n, --name <image>        Base image name (default: cf-ddns)
#   -v, --version <version>   Version (default: read from ddns/version.py)
#       --no-latest           Skip :latest tag
#   -p, --platforms <list>    Comma-separated platform list (default: linux/amd64,linux/arm64)
#       --builder <name>      Builder name to use/create (default: cf-ddns-builder)
#       --push                Push multi-arch image (required for multi-arch manifest)
#       --load                Load single-arch image into local Docker (implies current arch only)
#       --dry-run             Print build command(s) only
#       --help                Show help
#
# Notes:
# - Multi-arch manifests require --push (Docker cannot load multi-arch via --load).
# - Without --push or --load we perform a docker build for the host arch only.
# - If you specify --load with multiple platforms, only the first will be used.
# - If version already starts with 'v' we keep it; tag will still be v<version> (avoid double v).

IMAGE_NAME="cf-ddns"
PLATFORMS="linux/amd64,linux/arm64"
BUILDER="cf-ddns-builder"
PUSH=false
LOAD=false
NO_LATEST=false
DRY_RUN=false
USER_VERSION=""

print_help() { grep '^#' "$0" | sed 's/^# \{0,1\}//'; }

# Extract version from ddns/version.py
extract_version() {
  if [[ -n ${USER_VERSION} ]]; then
    echo "$USER_VERSION"
    return
  fi
  if [[ -f ddns/version.py ]]; then
    # Grep the __version__ string
    local v
    v=$(grep -Po '__version__\s*=\s*"\K[^"]+' ddns/version.py || true)
    if [[ -n $v ]]; then
      echo "$v"
      return
    fi
  fi
  echo "0.0.0-dev"
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--name) IMAGE_NAME="$2"; shift 2;;
    -v|--version) USER_VERSION="$2"; shift 2;;
    -p|--platforms) PLATFORMS="$2"; shift 2;;
    --builder) BUILDER="$2"; shift 2;;
    --push) PUSH=true; shift;;
    --load) LOAD=true; shift;;
    --no-latest) NO_LATEST=true; shift;;
    --dry-run) DRY_RUN=true; shift;;
    --help|-h) print_help; exit 0;;
    *) echo "Unknown argument: $1" >&2; exit 2;;
  esac
done

VERSION=$(extract_version)
# Ensure a clean numeric/semantic part for tag creation (retain user form otherwise)
RAW_VERSION="$VERSION"
TAG_VERSION="$RAW_VERSION"
[[ $TAG_VERSION == v* ]] || TAG_VERSION="v$TAG_VERSION"

if $LOAD && $PUSH; then
  echo "Cannot use --load and --push together" >&2
  exit 2
fi

if $LOAD && [[ "$PLATFORMS" == *","* ]]; then
  echo "--load with multiple platforms not supported; using first platform only" >&2
  PLATFORMS="${PLATFORMS%%,*}"
fi

# Create / use buildx builder if pushing or doing multi-platform
needs_builder=false
if $PUSH || [[ "$PLATFORMS" == *","* ]]; then
  needs_builder=true
fi

if $needs_builder; then
  if ! docker buildx inspect "$BUILDER" >/dev/null 2>&1; then
    echo "Creating buildx builder '$BUILDER' (this may enable qemu emulation)" >&2
    docker buildx create --name "$BUILDER" --use >/dev/null
  else
    docker buildx use "$BUILDER" >/dev/null
  fi
fi

# Assemble tag arguments
TAG_ARGS=( -t "${IMAGE_NAME}:${TAG_VERSION}" )
if ! $NO_LATEST; then
  TAG_ARGS+=( -t "${IMAGE_NAME}:latest" )
fi

# Build command logic
if $PUSH; then
  CMD=( docker buildx build --platform "$PLATFORMS" "${TAG_ARGS[@]}" --push . )
elif $LOAD; then
  CMD=( docker buildx build --platform "$PLATFORMS" "${TAG_ARGS[@]}" --load . )
elif [[ "$PLATFORMS" == *","* ]]; then
  echo "Multi-platform local build without --push will build only host arch via classic docker build." >&2
  echo "Use --push to publish a multi-arch manifest or specify a single platform." >&2
  CMD=( docker build "${TAG_ARGS[@]}" . )
else
  # Single platform classic build
  CMD=( docker build --platform "$PLATFORMS" "${TAG_ARGS[@]}" . )
fi

set -x
if $DRY_RUN; then
  printf 'DRY RUN: %q ' "${CMD[@]}"; echo
  exit 0
fi
"${CMD[@]}"
set +x

echo "\nBuilt image tags:" >&2
printf '  %s\n' "${IMAGE_NAME}:${TAG_VERSION}" >&2
if ! $NO_LATEST; then
  printf '  %s\n' "${IMAGE_NAME}:latest" >&2
fi

if $PUSH; then
  echo "Pushed multi-arch image for platforms: $PLATFORMS" >&2
else
  echo "Done (local build)." >&2
fi

