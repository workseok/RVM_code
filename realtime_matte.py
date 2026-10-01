"""
realtime_matte.py

카메라·HDMI 캡처카드·영상 파일에서 프레임을 읽어 RobustVideoMatting(RVM)으로
알파 매트(사람 영역)와 전경을 실시간 추출하고 화면에 보여줍니다.

- 입력: --source 0  (장치 인덱스: 내장캠/캡처카드)
        --source path/to/video.mp4  (영상 파일 — 카메라 없이 테스트)
- RVM의 recurrent state(r1~r4)를 매 프레임 다음 프레임으로 넘겨 시간적
  일관성을 유지합니다. 영상이 처음으로 돌아가거나 해상도가 바뀌면 초기화합니다.
- 장치는 cuda → mps → cpu 순으로 자동 선택합니다 (rvm_loader.py).

AI 배경 플레이트와의 합성은 composite.py에서 이 파일의 Matter 클래스를
불러와 수행합니다.

사용 예:
    python realtime_matte.py --source 0
    python realtime_matte.py --source samples/test.mp4 --loop
    python realtime_matte.py --source samples/test.mp4 --no-display --output outputs/alpha.mp4

미리보기 창 단축키:
    1  초록 배경 위 전경      2  알파 매트      3  원본 | 알파 나란히
    r  recurrent state 초기화    q / ESC  종료
"""

import argparse
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import torch

import rvm_loader

VIEWS = ("green", "alpha", "side")
WINDOW_NAME = "RVM realtime matte"


# ---------------------------------------------------------------------------
# 입력
# ---------------------------------------------------------------------------

def parse_source(value):
    """'0', '1' 같은 숫자는 장치 인덱스, 그 외는 파일 경로로 해석합니다."""
    return int(value) if value.isdigit() else value


class FrameSource:
    """
    장치 인덱스와 파일 경로를 같은 방식으로 읽는 래퍼입니다.

    카메라/캡처카드는 별도 스레드가 계속 읽어 가장 최근 프레임만 들고 있습니다.
    추론이 입력보다 느릴 때 OpenCV 내부 버퍼에 프레임이 쌓여 화면이 점점
    늦어지는 현상을 막기 위해서입니다. 영상 파일은 프레임을 건너뛰지 않고
    순서대로 읽습니다.
    """

    def __init__(self, source, width=None, height=None, loop=False):
        self.is_camera = isinstance(source, int)
        if not self.is_camera and not Path(source).is_file():
            raise FileNotFoundError(f"영상 파일이 없습니다: {source}")

        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            kind = "장치 인덱스" if self.is_camera else "영상 파일"
            raise RuntimeError(f"{kind}를 열 수 없습니다: {source}")
        if self.is_camera:
            if width:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            if height:
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        self.loop = loop
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.rewound = False  # 파일을 처음으로 되감았는지 (state 초기화 신호)

        self._latest = None
        self._seq = 0
        self._read_seq = 0
        self._failed = False
        self._lock = threading.Lock()
        self._running = self.is_camera
        if self.is_camera:
            self._thread = threading.Thread(target=self._grab_loop, daemon=True)
            self._thread.start()

    def _grab_loop(self):
        failures = 0
        while self._running:
            ok, frame = self.cap.read()
            if not ok:
                failures += 1
                if failures >= 30:  # 연속 실패 → 장치 분리 등으로 판단
                    self._failed = True
                    return
                time.sleep(0.01)
                continue
            failures = 0
            with self._lock:
                self._latest = frame
                self._seq += 1

    def read(self):
        """다음 프레임(BGR uint8)을 반환합니다. 더 이상 없으면 None."""
        self.rewound = False
        if self.is_camera:
            while True:
                with self._lock:
                    if self._seq != self._read_seq:
                        self._read_seq = self._seq
                        return self._latest
                if self._failed:
                    return None
                time.sleep(0.002)

        ok, frame = self.cap.read()
        if not ok and self.loop:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.rewound = True
            ok, frame = self.cap.read()
        return frame if ok else None

    def release(self):
        self._running = False
        if self.is_camera:
            self._thread.join(timeout=1)
        self.cap.release()


# ---------------------------------------------------------------------------
# 매팅
# ---------------------------------------------------------------------------

def auto_downsample_ratio(height, width):
    """RVM 공식 권장 방식: 모델 내부 처리 해상도의 긴 변이 512px가 되도록 맞춥니다."""
    return min(512 / max(height, width), 1.0)


class Matter:
    """
    RVM 모델과 recurrent state를 들고 프레임을 하나씩 처리합니다.

    process()는 장치(GPU 등) 위의 텐서를 그대로 반환합니다. 합성까지 같은
    장치에서 끝낸 뒤 한 번만 CPU로 옮기면 복사 비용을 줄일 수 있기 때문입니다.
    """

    def __init__(self, model, device, downsample_ratio=None):
        self.model = model
        self.device = device
        self.fixed_ratio = downsample_ratio  # None이면 해상도에 따라 자동
        self.downsample_ratio = downsample_ratio
        self.rec = [None] * 4
        self._shape = None

    def reset(self):
        """recurrent state를 비웁니다. 장면이 완전히 바뀌었을 때 사용합니다."""
        self.rec = [None] * 4

    def to_tensor(self, frame_bgr):
        """BGR uint8 (H,W,3) → RGB float [0,1] (1,3,H,W) 장치 텐서."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        src = torch.from_numpy(rgb).to(self.device, non_blocking=True)
        return src.permute(2, 0, 1).unsqueeze(0).float().div_(255)

    @torch.no_grad()
    def process(self, frame_bgr):
        """
        반환: (src, fgr, pha) — 모두 장치 위 텐서, 값 범위 [0,1]
          src: 입력 RGB (1,3,H,W) / fgr: 전경 RGB (1,3,H,W) / pha: 알파 (1,1,H,W)
        """
        h, w = frame_bgr.shape[:2]
        if self._shape != (h, w):
            # 해상도가 바뀌면 이전 state는 크기가 맞지 않으므로 초기화
            self._shape = (h, w)
            self.reset()
            self.downsample_ratio = self.fixed_ratio or auto_downsample_ratio(h, w)

        src = self.to_tensor(frame_bgr)
        fgr, pha, *self.rec = self.model(src, *self.rec, downsample_ratio=self.downsample_ratio)
        return src, fgr, pha


def tensor_to_bgr(img):
    """(1,C,H,W) [0,1] 장치 텐서 → BGR uint8 (H,W,3) numpy. C=1이면 회색으로 확장."""
    img = img[0].clamp(0, 1).mul(255).byte().permute(1, 2, 0).cpu().numpy()
    if img.shape[2] == 1:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def render_view(view, src, fgr, pha):
    """미리보기용 화면을 만듭니다 (AI 배경 합성은 composite.py 담당)."""
    if view == "alpha":
        return tensor_to_bgr(pha)
    if view == "side":
        return np.hstack([tensor_to_bgr(src), tensor_to_bgr(pha)])
    green = torch.tensor([120 / 255, 1.0, 155 / 255], device=fgr.device).view(1, 3, 1, 1)
    return tensor_to_bgr(fgr * pha + green * (1 - pha))


def draw_fps(img, fps, extra=""):
    text = f"{fps:5.1f} FPS {extra}".rstrip()
    cv2.putText(img, text, (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, text, (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# 실행 루프 (composite.py와 공유)
# ---------------------------------------------------------------------------

def add_common_args(parser):
    """realtime_matte.py와 composite.py가 함께 쓰는 옵션."""
    parser.add_argument("--source", type=parse_source, default=0,
                        help="장치 인덱스(0, 1, ...) 또는 영상 파일 경로 (기본: 0)")
    parser.add_argument("--variant", choices=rvm_loader.VARIANTS, default="mobilenetv3",
                        help="mobilenetv3: 속도 우선(기본) / resnet50: 품질 우선")
    parser.add_argument("--checkpoint", type=Path, default=None,
                        help="가중치 경로 (기본: models/rvm_<variant>.pth)")
    parser.add_argument("--device", choices=rvm_loader.DEVICE_CHOICES, default="auto",
                        help="auto: cuda → mps → cpu 순으로 자동 선택 (기본)")
    parser.add_argument("--rvm-path", type=Path, default=None,
                        help="RVM 공식 저장소 경로 (기본: third_party/RobustVideoMatting)")
    parser.add_argument("--downsample-ratio", type=float, default=None,
                        help="모델 내부 축소 비율 (기본: 자동 = 512 / 긴 변). "
                             "권장: HD 0.25, 4K 0.125. 상반신 위주면 낮게, 전신이면 높게")
    parser.add_argument("--width", type=int, default=None, help="카메라 요청 가로 해상도")
    parser.add_argument("--height", type=int, default=None, help="카메라 요청 세로 해상도")
    parser.add_argument("--loop", action="store_true", help="영상 파일이 끝나면 처음부터 반복")
    parser.add_argument("--no-display", action="store_true",
                        help="미리보기 창 없이 실행 (원격/서버 환경 테스트용)")
    parser.add_argument("--output", type=Path, default=None,
                        help="출력 화면을 mp4로 저장할 경로 (선택)")
    parser.add_argument("--max-frames", type=int, default=None,
                        help="이 개수만큼 처리하고 종료 (테스트용)")


def build_matter(args):
    if args.downsample_ratio is not None and not 0 < args.downsample_ratio <= 1:
        raise SystemExit("--downsample-ratio는 0보다 크고 1 이하여야 합니다.")
    model, device = rvm_loader.load_model(args.variant, args.checkpoint, args.device, args.rvm_path)
    print(f"[정보] 모델 {args.variant} / 장치 {device}")
    return Matter(model, device, args.downsample_ratio)


def run_loop(args, matter, render, on_key=None):
    """
    입력을 읽어 matter.process → render(src, fgr, pha) → 화면/파일 출력을 반복합니다.

    render는 BGR uint8 이미지를 반환하는 함수이고, on_key(key)는 처리하지 않은
    키 입력을 받아 추가 동작을 하고 싶을 때 넘깁니다.
    """
    source = FrameSource(args.source, args.width, args.height, args.loop)
    writer = None
    frames = 0
    fps = 0.0
    last = time.perf_counter()
    try:
        while args.max_frames is None or frames < args.max_frames:
            frame = source.read()
            if frame is None:
                print("[정보] 입력이 끝났습니다." if not source.is_camera
                      else "[오류] 카메라에서 프레임을 받지 못했습니다.")
                break
            if source.rewound:
                matter.reset()

            src, fgr, pha = matter.process(frame)
            out = render(src, fgr, pha)

            now = time.perf_counter()
            fps = 0.9 * fps + 0.1 * (1 / max(now - last, 1e-6)) if frames else 0.0
            last = now
            frames += 1

            if writer is None and args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                writer_size = (out.shape[1], out.shape[0])
                writer = cv2.VideoWriter(str(args.output), cv2.VideoWriter_fourcc(*"mp4v"),
                                         source.fps, writer_size)
            if writer is not None:
                # 실행 중 화면 모드를 바꿔 크기가 달라져도 저장 크기는 처음 크기로 유지
                if (out.shape[1], out.shape[0]) != writer_size:
                    out = cv2.resize(out, writer_size)
                writer.write(out)

            if args.no_display:
                if frames % 30 == 0:
                    print(f"  {frames} 프레임 처리, {fps:.1f} FPS")
                continue

            draw_fps(out, fps, f"ratio {matter.downsample_ratio:.3f}")
            cv2.imshow(WINDOW_NAME, out)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            if key == ord("r"):
                matter.reset()
                print("[정보] recurrent state 초기화")
            elif on_key is not None and key != 255:
                on_key(key)
    finally:
        source.release()
        if writer is not None:
            writer.release()
            print(f"[정보] 저장 완료: {args.output}")
        if not args.no_display:
            cv2.destroyAllWindows()
    print(f"[정보] 총 {frames} 프레임 처리 (마지막 FPS {fps:.1f})")
    return frames


def main():
    parser = argparse.ArgumentParser(description="RVM 실시간 매팅 미리보기")
    add_common_args(parser)
    parser.add_argument("--view", choices=VIEWS, default="green",
                        help="green: 초록 배경 위 전경(기본) / alpha: 알파 매트 / side: 원본|알파")
    args = parser.parse_args()

    state = {"view": args.view}

    def on_key(key):
        if key in (ord("1"), ord("2"), ord("3")):
            state["view"] = VIEWS[key - ord("1")]

    try:
        matter = build_matter(args)
        run_loop(args, matter, lambda s, f, p: render_view(state["view"], s, f, p), on_key)
    except (FileNotFoundError, RuntimeError) as exc:
        raise SystemExit(f"[오류] {exc}")


if __name__ == "__main__":
    main()
