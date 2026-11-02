#!/usr/bin/env bash
# netd ifupdown integratsiya sinovi — FAQAT izolyatsiyalangan konteynerda
# (debian:trixie + dummy eth1), host tarmog'iga HECH QACHON tegilmaydi.
# Har bir stsenariy (a-e) o'z-alohida, toza konteynerda ishlaydi.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$(cd "$HERE/../.." && pwd)"
IMAGE="innova-netd-itest:local"

echo "== obraz qurilmoqda (keshlanadi): $IMAGE =="
docker build -q -t "$IMAGE" -f "$HERE/Dockerfile.netd-itest" "$HERE" >/dev/null

run_scenario() {
    local letter="$1"
    echo
    echo "=== stsenariy $letter ==="
    docker run --rm \
        --cap-add NET_ADMIN \
        --cap-drop ALL --cap-add NET_ADMIN \
        --network none \
        -v "$API_DIR/app/__init__.py:/src/app/__init__.py:ro" \
        -v "$API_DIR/app/netd:/src/app/netd:ro" \
        -v "$HERE/netd_ifupdown_driver.py:/src/netd_ifupdown_driver.py:ro" \
        "$IMAGE" \
        bash -c "ip link add eth1 type dummy && python3 /src/netd_ifupdown_driver.py $letter"
}

for s in a b c d e; do
    run_scenario "$s"
done

echo
echo "=== BARCHA STSENARIYLAR (a-e) MUVAFFAQIYATLI ==="
