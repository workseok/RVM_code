"""
selftest.py

카메라·모니터 없이 전체 파이프라인(입력 → RVM 매팅 → 배경 합성 → 저장)을
검증합니다. 각 항목을 [통과]/[실패]로 출력하고, 결과 영상과 미리보기 이미지를
outputs/ 에 저장합니다.

  1) 매팅: 알파·전경의 크기와 값 범위(0~1), NaN 여부, 사람 검출 여부
  2) 합성: 알파=0인 곳은 배경, 알파=1인 곳은 전경과 같은지 (수식 검증)
  3) 배경 맞춤: cover/contain/stretch 결과 크기
  4) 시간적 일관성: 같은 장면에 카메라 노이즈를 섞어 반복 입력했을 때, recurrent
     state를 넘기는 쪽이 매 프레임 초기화하는 쪽보다 알파 깜빡임이 적은지
  5) 처리 속도(FPS) — 참고용, 통과 기준 없음

먼저 python scripts/download_samples.py 로 샘플을 준비하세요.

사용 예:
    python scripts/selftest.py
    python scripts/selftest.py --source 내영상.mp4 --background 내배경.png
"""

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import composite as cp  # noqa: E402
import realtime_matte as rm  # noqa: E402
import rvm_loader  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  [{'통과' if ok else '실패'}] {name}" + (f" — {detail}" if detail else ""))


def flicker(matter, frames, reset_every_frame, warmup=10):
    """연속 프레임 간 알파 변화량을 알파 면적으로 나눈 값 (낮을수록 안정)."""
    matter.reset()
    alphas = []
    for f in frames:
        if reset_every_frame:
            matter.reset()
        alphas.append(matter.process(f)[2][0, 0].cpu().numpy())
    a = np.array(alphas[warmup:])
    return float(np.abs(np.diff(a, axis=0)).mean() / max(a.mean(), 1e-6))


def main():
    parser = argparse.ArgumentParser(description="카메라 없이 파이프라인 전체 검증")
    parser.add_argument("--source", type=Path, default=REPO_ROOT / "samples" / "vtest.avi")
    parser.add_argument("--background", type=Path, default=REPO_ROOT / "samples" / "sample_bg.png")
    parser.add_argument("--frames", type=int, default=60, help="처리할 프레임 수 (기본 60)")
    parser.add_argument("--variant", choices=rvm_loader.VARIANTS, default="mobilenetv3")
    parser.add_argument("--device", choices=rvm_loader.DEVICE_CHOICES, default="auto")
    parser.add_argument("--downsample-ratio", type=float, default=None)
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "outputs")
    args = parser.parse_args()

    for path in (args.source, args.background):
        if not path.is_file():
            raise SystemExit(f"[오류] 파일이 없습니다: {path}\n"
                             "  python scripts/download_samples.py 를 먼저 실행하세요.")

    model, device = rvm_loader.load_model(args.variant, device=args.device)
    matter = rm.Matter(model, device, args.downsample_ratio)
    plate = cp.BackgroundPlate(args.background, "cover", device)
    print(f"모델 {args.variant} / 장치 {device} / 입력 {args.source.name} / 배경 {args.background.name}\n")

    source = rm.FrameSource(str(args.source))
    frames = []
    while len(frames) < args.frames:
        f = source.read()
        if f is None:
            break
        frames.append(f)
    source.release()
    if not frames:
        raise SystemExit(f"[오류] 입력 영상에서 프레임을 읽지 못했습니다: {args.source}")
    h, w = frames[0].shape[:2]

    # 1) 매팅 + 2) 합성 — 결과 영상 저장
    print(f"[1/5] 매팅 ({len(frames)} 프레임, {w}x{h})")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    video_path = args.out_dir / "selftest_composite.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (w * 2, h))
    shapes_ok = range_ok = True
    alpha_mass = []
    comp_err = 0.0
    start = time.perf_counter()
    with torch.no_grad():
        for f in frames:
            src, fgr, pha = matter.process(f)
            shapes_ok &= tuple(fgr.shape) == (1, 3, h, w) and tuple(pha.shape) == (1, 1, h, w)
            range_ok &= bool(torch.isfinite(pha).all() and pha.min() >= 0 and pha.max() <= 1)
            bg = plate.get(w, h)
            com = cp.composite(fgr, pha, bg)
            # 2) 합성 수식 검증: 알파 0 → 배경, 알파 1 → 전경
            ref = torch.where(pha == 0, bg, torch.where(pha == 1, fgr, com))
            comp_err = max(comp_err, float((com - ref).abs().max()))
            alpha_mass.append(float(pha.mean()))
            writer.write(np.hstack([rm.tensor_to_bgr(src), rm.tensor_to_bgr(com)]))
    elapsed = time.perf_counter() - start
    writer.release()

    check("알파·전경 크기가 입력과 같음", shapes_ok)
    check("알파 값이 0~1 범위이고 NaN 없음", range_ok)
    detected = float(np.mean(alpha_mass[5:] or alpha_mass))
    check("사람(전경) 검출", detected > 0.001, f"평균 알파 면적 {detected * 100:.2f}%")

    print("[2/5] 합성")
    check("알파=0 → 배경, 알파=1 → 전경", comp_err < 1e-6, f"최대 오차 {comp_err:.2e}")
    preview = args.out_dir / "selftest_preview.png"
    cv2.imwrite(str(preview), np.hstack([rm.tensor_to_bgr(src), rm.tensor_to_bgr(pha),
                                         rm.tensor_to_bgr(com)]))

    print("[3/5] 배경 맞춤")
    bg_img = cv2.imread(str(args.background))
    for mode in cp.FIT_MODES:
        out = cp.fit_image(bg_img, w, h, mode)
        check(f"--fit {mode}", out.shape == (h, w, 3), f"{bg_img.shape[1]}x{bg_img.shape[0]} → {w}x{h}")

    print("[4/5] 시간적 일관성 (같은 장면 + 카메라 노이즈 30프레임)")
    rng = np.random.default_rng(0)
    base = frames[len(frames) // 2]
    noisy = [np.clip(base.astype(np.int16) + rng.normal(0, 6, base.shape), 0, 255).astype(np.uint8)
             for _ in range(30)]
    with torch.no_grad():
        with_state = flicker(matter, noisy, reset_every_frame=False)
        without_state = flicker(matter, noisy, reset_every_frame=True)
    check("state 전달 시 깜빡임이 더 적음", with_state < without_state,
          f"state 전달 {with_state:.3f} / 매 프레임 초기화 {without_state:.3f} (낮을수록 안정)")

    print("[5/5] 처리 속도 (참고)")
    print(f"  매팅+합성+저장 {len(frames) / elapsed:.1f} FPS ({w}x{h}, ratio {matter.downsample_ratio:.3f}, {device})")

    print(f"\n결과 영상: {video_path}  (왼쪽 원본 | 오른쪽 합성)")
    print(f"미리보기:  {preview}  (원본 | 알파 | 합성)")
    passed = sum(results)
    print(f"\n{passed}/{len(results)} 항목 통과" + ("" if all(results) else " — 실패 항목을 확인하세요."))
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
