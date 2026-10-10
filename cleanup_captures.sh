#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/sysop/projects/kenneth"
AGE_DAYS=30
DRY_RUN=0

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--dry-run|-n] [--days N]

Deletes RF capture files older than N days (default: 30):
  - *.raw
  - *.wav

Search root: ${PROJECT_DIR}
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run|-n)
      DRY_RUN=1
      shift
      ;;
    --days)
      AGE_DAYS="${2:-}"
      if [[ -z "${AGE_DAYS}" || ! "${AGE_DAYS}" =~ ^[0-9]+$ ]]; then
        echo "Invalid value for --days: ${2:-<empty>}" >&2
        exit 2
      fi
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! -d "${PROJECT_DIR}" ]]; then
  echo "Project directory not found: ${PROJECT_DIR}" >&2
  exit 1
fi

mapfile -d '' FILES < <(
  find "${PROJECT_DIR}" \
    \( -path "${PROJECT_DIR}/.git" -o -path "${PROJECT_DIR}/venv" -o -path "${PROJECT_DIR}/venv_enhance" -o -path "${PROJECT_DIR}/stress-venv" -o -path "${PROJECT_DIR}/node_modules" \) -prune -o \
    -type f \( -name "*.raw" -o -name "*.wav" \) -mtime +"${AGE_DAYS}" -print0
)

count=${#FILES[@]}
if (( count == 0 )); then
  echo "No capture files older than ${AGE_DAYS} days found."
  exit 0
fi

total_bytes=0
for file in "${FILES[@]}"; do
  size=$(stat -c '%s' "$file" 2>/dev/null || echo 0)
  total_bytes=$((total_bytes + size))
done

human_size=$(numfmt --to=iec --suffix=B "${total_bytes}")

echo "Found ${count} file(s) older than ${AGE_DAYS} days (${human_size})."

if (( DRY_RUN == 1 )); then
  echo "Dry run enabled. Files that would be deleted:"
  printf '%s\n' "${FILES[@]}"
  exit 0
fi

printf '%s\0' "${FILES[@]}" | xargs -0 --no-run-if-empty rm -f

echo "Deleted ${count} file(s), freed ${human_size}."
