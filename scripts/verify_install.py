"""
verify_install.py

설치가 제대로 되었는지 한 번에 확인합니다.
  1) 필수 패키지(torch, torchvision, opencv, numpy) import
  2) RVM 공식 저장소 clone 여부
  3) 가중치 파일 로드
  4) 장치 자동 선택(cuda → mps → cpu) 후 더미 프레임으로 추론 속도 측정

카메라나 영상 파일 없이 실행됩니다.

사용 예:
    python scripts/verify_install.py
    python scripts/verify_install.py --variant resnet50 --device cpu
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(description="RVM 설치 확인")
    parser.add_argument("--variant", choices=["mobilenetv3", "resnet50"], default="mobilenetv3")
    parser.add_argument("--checkpoint", type=Path, default=None,
                        help="가중치 경로 (기본: models/rvm_<variant>.pth)")
    parser.add_argument("--device", choices=["auto", "cuda", "mps", "cpu"], default="auto")
    parser.add_argument("--rvm-path", type=Path, default=None,
                        help="RVM 공식 저장소 경로 (기본: third_party/RobustVideoMatting)")
    args = parser.parse_args()

    print("[1/4] 패키지 확인")
    try:
        import cv2
        import numpy
        import torch
        import torchvision
    except ImportError as exc:
        print(f"  [실패] {exc}\n  pip install -r requirements.txt 를 먼저 실행하세요.")
        sys.exit(1)
    print(f"  torch {torch.__version__} / torchvision {torchvision.__version__} / "
          f"opencv {cv2.__version__} / numpy {numpy.__version__}")

    import rvm_loader

    print("[2/4] RVM 공식 저장소 확인")
    try:
        rvm_loader.import_matting_network(args.rvm_path)
    except (FileNotFoundError, ImportError) as exc:
        print(f"  [실패] {exc}")
        sys.exit(1)
    print("  OK")

    print("[3/4] 가중치 로드 + 장치 선택")
    try:
        model, device = rvm_loader.load_model(args.variant, args.checkpoint, args.device, args.rvm_path)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"  [실패] {exc}")
        sys.exit(1)
    print(f"  모델: {args.variant} / 장치: {device}")

    print("[4/4] 더미 프레임(1280x720) 추론 속도 측정")
    frames = 10
    rec = [None] * 4
    src = torch.rand(1, 3, 720, 1280, device=device)
    with torch.no_grad():
        model(src, *rec, downsample_ratio=0.25)  # 첫 실행(워밍업)은 측정에서 제외
        if device.type == "cuda":
            torch.cuda.synchronize()
        start = time.perf_counter()
        for _ in range(frames):
            fgr, pha, *rec = model(src, *rec, downsample_ratio=0.25)
        if device.type == "cuda":
            torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
    print(f"  {frames / elapsed:.1f} FPS (알파 출력 크기 {tuple(pha.shape)})")
    print("\n설치 확인 완료 — 모든 항목 정상입니다.")


if __name__ == "__main__":
    main()
