"""
download_samples.py

카메라 없이 테스트하기 위한 샘플을 samples/ 폴더에 준비합니다.

  samples/vtest.avi            사람이 걸어 다니는 테스트 영상 (OpenCV 공식 샘플, 768x576)
  samples/sample_bg.png        배경 플레이트 대용 이미지 (코드로 생성, 1920x1080)
  samples/sample_bg_motion.mp4 움직이는 배경 플레이트 대용 영상 (코드로 생성, 3초)

생성 이미지·영상은 실제 AI 배경이 아니라 합성 동작 확인용 자리표시입니다.
실제 촬영에서는 AI로 만든 배경 플레이트로 바꿔 쓰면 됩니다.

사용 예:
    python scripts/download_samples.py
"""

import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES = REPO_ROOT / "samples"

# OpenCV 저장소 samples/data (Apache-2.0). 고정 태그 경로를 사용합니다.
TEST_VIDEO_URL = "https://raw.githubusercontent.com/opencv/opencv/4.10.0/samples/data/vtest.avi"
TEST_VIDEO_SIZE = 8_131_690


def download_test_video():
    dest = SAMPLES / "vtest.avi"
    if dest.is_file() and dest.stat().st_size == TEST_VIDEO_SIZE:
        print(f"[건너뜀] {dest} — 이미 있습니다.")
        return True
    print(f"[다운로드] {TEST_VIDEO_URL}")
    tmp = dest.with_suffix(".part")
    try:
        urllib.request.urlretrieve(TEST_VIDEO_URL, tmp)
    except Exception as exc:
        print(f"[실패] {exc}\n  브라우저로 위 주소를 열어 직접 받은 뒤 {dest} 에 저장해도 됩니다.")
        return False
    if tmp.stat().st_size != TEST_VIDEO_SIZE:
        tmp.unlink()
        print("[실패] 파일 크기가 예상과 다릅니다. 다시 실행해 주세요.")
        return False
    tmp.replace(dest)
    print(f"[완료] {dest}")
    return True


def make_plate(width, height, t=0.0):
    """하늘색 그라데이션 + 지평선 + 원형 조명이 있는 단순한 배경 플레이트."""
    y = np.linspace(0, 1, height, dtype=np.float32)[:, None, None]
    top = np.array([235, 170, 90], np.float32)     # BGR: 하늘
    bottom = np.array([200, 225, 245], np.float32)
    img = (top * (1 - y) + bottom * y) * np.ones((1, width, 1), np.float32)

    horizon = int(height * 0.68)
    img[horizon:] = np.array([95, 120, 105], np.float32)  # 바닥
    img = img.astype(np.uint8)

    cx = int(width * (0.2 + 0.6 * (0.5 + 0.5 * np.sin(t * 2 * np.pi))))
    for r, c in ((int(height * 0.12), (180, 230, 255)), (int(height * 0.08), (210, 245, 255))):
        cv2.circle(img, (cx, int(height * 0.25)), r, c, -1, cv2.LINE_AA)
    for i in range(6):
        x = int(width * (0.08 + i * 0.17))
        cv2.rectangle(img, (x, horizon - int(height * (0.15 + 0.05 * (i % 3)))),
                      (x + int(width * 0.09), horizon), (120, 110, 100), -1)
    cv2.putText(img, "SAMPLE BACKGROUND PLATE", (int(width * 0.03), int(height * 0.95)),
                cv2.FONT_HERSHEY_SIMPLEX, height / 900, (255, 255, 255), max(1, height // 400),
                cv2.LINE_AA)
    return img


def make_backgrounds():
    still = SAMPLES / "sample_bg.png"
    cv2.imwrite(str(still), make_plate(1920, 1080))
    print(f"[생성] {still}")

    motion = SAMPLES / "sample_bg_motion.mp4"
    fps, seconds = 30, 3
    writer = cv2.VideoWriter(str(motion), cv2.VideoWriter_fourcc(*"mp4v"), fps, (1280, 720))
    for i in range(fps * seconds):
        writer.write(make_plate(1280, 720, t=i / (fps * seconds)))
    writer.release()
    print(f"[생성] {motion}")


def main():
    SAMPLES.mkdir(exist_ok=True)
    ok = download_test_video()
    make_backgrounds()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
