"""
download_weights.py

RVM 공식 사전학습 가중치(.pth)를 models/ 폴더에 내려받고 SHA-256으로
무결성을 확인합니다. 이미 받아 둔 파일은 해시가 맞으면 건너뜁니다.

사용 예:
    python scripts/download_weights.py                       # mobilenetv3 (기본, 속도 우선)
    python scripts/download_weights.py --variant resnet50    # 품질 우선
    python scripts/download_weights.py --variant all         # 둘 다
"""

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RELEASE_URL = "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0"

# 공식 v1.0.0 릴리스 파일 기준 (2026-10 확인)
WEIGHTS = {
    "mobilenetv3": {
        "file": "rvm_mobilenetv3.pth",
        "size": 15_217_721,
        "sha256": "3c7c1d92033f7c38d6577c481d13a195d7d80a159b960f4f3119ac7b534cf4f8",
    },
    "resnet50": {
        "file": "rvm_resnet50.pth",
        "size": 107_905_875,
        "sha256": "c191a807251164c073dce5fa408e7a816070d539b882b2a3150330a9fec112ce",
    },
}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, dest, expected_size):
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as resp, open(tmp, "wb") as out:
        total = int(resp.headers.get("Content-Length") or expected_size)
        done = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            print(f"\r  {done / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", flush=True)
    print()
    tmp.replace(dest)


def fetch(variant, out_dir):
    info = WEIGHTS[variant]
    dest = out_dir / info["file"]

    if dest.is_file() and sha256_of(dest) == info["sha256"]:
        print(f"[건너뜀] {dest} — 이미 받아 둔 파일이 정상입니다.")
        return True

    url = f"{RELEASE_URL}/{info['file']}"
    print(f"[다운로드] {url}")
    try:
        download(url, dest, info["size"])
    except Exception as exc:
        print(f"[실패] 다운로드 중 오류: {exc}")
        print(f"  브라우저로 위 주소를 열어 직접 받은 뒤 {dest} 에 저장해도 됩니다.")
        return False

    if sha256_of(dest) != info["sha256"]:
        dest.unlink()
        print(f"[실패] {info['file']} 해시가 맞지 않아 삭제했습니다. 다시 실행해 주세요.")
        return False

    print(f"[완료] {dest}")
    return True


def main():
    parser = argparse.ArgumentParser(description="RVM 사전학습 가중치 다운로드")
    parser.add_argument("--variant", choices=[*WEIGHTS, "all"], default="mobilenetv3",
                        help="mobilenetv3: 속도 우선(기본) / resnet50: 품질 우선 / all: 둘 다")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "models",
                        help="저장 폴더 (기본: models/)")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    variants = list(WEIGHTS) if args.variant == "all" else [args.variant]
    ok = all([fetch(v, args.out) for v in variants])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
