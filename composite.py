"""
composite.py

realtime_matte.py로 추출한 알파·전경을 AI 생성 배경 플레이트와 실시간
합성해 화면에 출력합니다.

    합성 = 전경 × 알파 + 배경 × (1 − 알파)

전경은 RVM이 따로 예측한 전경(fgr)을 사용합니다. 원본 프레임을 그대로 쓰는
것보다 머리카락 경계 등에 남는 원래 배경색 번짐이 적습니다.

- 배경: 이미지(png/jpg 등) 또는 영상 파일. 여러 개를 주면 b 키로 전환합니다.
- 배경과 입력 영상의 비율이 다르면 --fit으로 맞추는 방식을 고릅니다.
    cover   화면을 꽉 채우고 넘치는 부분은 잘라냄 (기본, 왜곡 없음)
    contain 배경 전체가 보이도록 줄이고 남는 부분은 검은 여백
    stretch 비율 무시하고 늘려 맞춤 (왜곡 가능)
- 합성은 모델과 같은 장치(GPU 등)에서 수행하고, 결과만 CPU로 옮깁니다.

사용 예:
    python composite.py --source 0 --background ai_background.png
    python composite.py --source samples/vtest.avi --background bg1.png bg2.mp4 --loop
    python composite.py --source samples/vtest.avi --background bg.png \\
        --no-display --max-frames 100 --output outputs/composite.mp4

미리보기 창 단축키:
    1  합성 결과    2  알파 매트    3  원본 | 합성 나란히
    b  다음 배경    r  recurrent state 초기화    f  전체화면 전환    q / ESC  종료
"""

import argparse
from pathlib import Path

import cv2
import numpy as np
import torch

import realtime_matte as rm

FIT_MODES = ("cover", "contain", "stretch")
COMPOSITE_VIEWS = ("composite", "alpha", "side")
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}


def fit_image(img, width, height, mode):
    """배경 이미지(BGR)를 (width, height)에 맞춥니다."""
    bh, bw = img.shape[:2]
    if mode == "stretch" or (bw, bh) == (width, height):
        return cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)

    scale = max(width / bw, height / bh) if mode == "cover" else min(width / bw, height / bh)
    nw, nh = max(1, round(bw * scale)), max(1, round(bh * scale))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    resized = cv2.resize(img, (nw, nh), interpolation=interp)

    if mode == "cover":
        x, y = (nw - width) // 2, (nh - height) // 2
        return resized[y:y + height, x:x + width]

    canvas = np.zeros((height, width, 3), np.uint8)
    x, y = (width - nw) // 2, (height - nh) // 2
    canvas[y:y + nh, x:x + nw] = resized[:height, :width]
    return canvas


class BackgroundPlate:
    """
    배경 이미지 1장 또는 배경 영상 하나를 나타냅니다.

    이미지는 출력 크기에 맞춘 텐서를 한 번 만들어 재사용하고, 영상은 매
    호출마다 다음 프레임을 읽어(끝나면 처음부터) 맞춥니다.
    """

    def __init__(self, path, fit, device):
        self.path = Path(path)
        self.fit = fit
        self.device = device
        if not self.path.is_file():
            raise FileNotFoundError(f"배경 파일이 없습니다: {self.path}")

        self.is_image = self.path.suffix.lower() in IMAGE_EXTS
        self._cache = None  # (width, height, tensor)
        if self.is_image:
            self.image = cv2.imread(str(self.path), cv2.IMREAD_COLOR)
            if self.image is None:
                raise RuntimeError(f"배경 이미지를 읽을 수 없습니다: {self.path}")
        else:
            self.cap = cv2.VideoCapture(str(self.path))
            if not self.cap.isOpened():
                raise RuntimeError(f"배경 영상을 열 수 없습니다: {self.path}")

    def _to_tensor(self, img):
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return torch.from_numpy(rgb).to(self.device).permute(2, 0, 1).unsqueeze(0).float().div_(255)

    def get(self, width, height):
        """(1,3,height,width) RGB [0,1] 장치 텐서."""
        if self.is_image:
            if self._cache is None or self._cache[:2] != (width, height):
                self._cache = (width, height,
                               self._to_tensor(fit_image(self.image, width, height, self.fit)))
            return self._cache[2]

        ok, frame = self.cap.read()
        if not ok:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.cap.read()
            if not ok:
                raise RuntimeError(f"배경 영상에서 프레임을 읽을 수 없습니다: {self.path}")
        return self._to_tensor(fit_image(frame, width, height, self.fit))

    def release(self):
        if not self.is_image:
            self.cap.release()


def composite(fgr, pha, bg):
    """전경 × 알파 + 배경 × (1 − 알파). 모든 입력은 같은 장치의 [0,1] 텐서."""
    return fgr * pha + bg * (1 - pha)


def main():
    parser = argparse.ArgumentParser(description="RVM 실시간 매팅 + AI 배경 합성")
    rm.add_common_args(parser)
    parser.add_argument("--background", type=Path, nargs="+", required=True,
                        help="배경 이미지/영상 경로. 여러 개를 주면 실행 중 b 키로 전환")
    parser.add_argument("--fit", choices=FIT_MODES, default="cover",
                        help="배경 비율 맞춤: cover(꽉 채우고 자르기, 기본) / "
                             "contain(전체 보이기, 여백) / stretch(늘리기)")
    parser.add_argument("--view", choices=COMPOSITE_VIEWS, default="composite",
                        help="composite: 합성 결과(기본) / alpha: 알파 매트 / side: 원본|합성")
    args = parser.parse_args()

    plates = []
    source = None
    try:
        # 모델을 불러오기 전에 입력·배경 경로부터 확인
        source = rm.open_source(args)
        plates = [BackgroundPlate(p, args.fit, torch.device("cpu")) for p in args.background]
        matter = rm.build_matter(args)
        for plate in plates:
            plate.device = matter.device

        state = {"view": args.view, "bg": 0}
        print(f"[정보] 배경 {len(plates)}개, 현재: {plates[0].path.name} (fit={args.fit})")

        def render(src, fgr, pha):
            h, w = src.shape[2:]
            com = composite(fgr, pha, plates[state["bg"]].get(w, h))
            if state["view"] == "alpha":
                return rm.tensor_to_bgr(pha)
            if state["view"] == "side":
                return np.hstack([rm.tensor_to_bgr(src), rm.tensor_to_bgr(com)])
            return rm.tensor_to_bgr(com)

        def on_key(key):
            if key in (ord("1"), ord("2"), ord("3")):
                state["view"] = COMPOSITE_VIEWS[key - ord("1")]
            elif key == ord("b"):
                state["bg"] = (state["bg"] + 1) % len(plates)
                print(f"[정보] 배경 전환: {plates[state['bg']].path.name}")

        rm.run_loop(args, source, matter, render, on_key)
        source = None  # run_loop가 닫음
    except (FileNotFoundError, RuntimeError) as exc:
        raise SystemExit(f"[오류] {exc}")
    finally:
        if source is not None:
            source.release()
        for plate in plates:
            plate.release()


if __name__ == "__main__":
    main()
