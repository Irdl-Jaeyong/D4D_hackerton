#!/usr/bin/env bash
set -euo pipefail
case "$(uname -sm)" in
  "Linux x86_64") arch=amd64 ;;
  "Linux aarch64") arch=arm64 ;;
  *) echo "지원하지 않는 운영체제/아키텍처" >&2; exit 1 ;;
esac
runtime="${XDG_DATA_HOME:-$HOME/.local/share}/ollama-runtime"
mkdir -p "$runtime"
archive=$(mktemp)
trap 'rm -f "$archive"' EXIT
version="${OLLAMA_VERSION:-0.40.1}"
if [[ -n "$version" ]]; then
  url="https://github.com/ollama/ollama/releases/download/v${version#v}/ollama-linux-$arch.tar.zst"
else
  url="https://ollama.com/download/ollama-linux-$arch.tar.zst"
fi
curl -fL --connect-timeout 15 --retry 3 "$url" -o "$archive"
tar --zstd -xf "$archive" -C "$runtime"
echo "설치 완료: $runtime/bin/ollama"
echo "실행: ./scripts/ollama.sh serve"
