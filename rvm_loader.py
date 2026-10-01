"""
rvm_loader.py

RobustVideoMatting(RVM) 모델을 불러오고, 실행 장치(cuda → mps → cpu)를
자동으로 고르는 공용 모듈입니다.

RVM 모델 코드(model/ 폴더)는 이 저장소에 포함하지 않습니다. 공식 저장소를
third_party/RobustVideoMatting 에 clone해 두면 그 경로를 sys.path에 추가해
`from model import MattingNetwork`로 불러옵니다.

    git clone https://github.com/PeterL1n/RobustVideoMatting.git third_party/RobustVideoMatting

다른 위치에 clone했다면 load_model(rvm_path=...) 인자나 환경변수
RVM_REPO_PATH로 경로를 지정합니다.
"""

import os
import sys
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_RVM_PATH = REPO_ROOT / "third_party" / "RobustVideoMatting"
DEFAULT_MODEL_DIR = REPO_ROOT / "models"

VARIANTS = ("mobilenetv3", "resnet50")
DEVICE_CHOICES = ("auto", "cuda", "mps", "cpu")
AUTO_DEVICE_ORDER = ("cuda", "mps", "cpu")


def default_checkpoint(variant):
    return DEFAULT_MODEL_DIR / f"rvm_{variant}.pth"


def import_matting_network(rvm_path=None):
    """RVM 공식 저장소 경로를 sys.path에 추가하고 MattingNetwork 클래스를 반환합니다."""
    path = Path(rvm_path or os.environ.get("RVM_REPO_PATH") or DEFAULT_RVM_PATH).resolve()
    if not (path / "model" / "model.py").is_file():
        raise FileNotFoundError(
            f"RVM 공식 저장소를 찾을 수 없습니다: {path}\n"
            "저장소 폴더에서 아래 명령으로 clone한 뒤 다시 실행하세요.\n"
            "  git clone https://github.com/PeterL1n/RobustVideoMatting.git "
            "third_party/RobustVideoMatting"
        )
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    from model import MattingNetwork  # noqa: E402  (RVM 공식 저장소의 model 패키지)

    return MattingNetwork


def _device_available(name):
    if name == "cuda":
        return torch.cuda.is_available()
    if name == "mps":
        mps = getattr(torch.backends, "mps", None)
        return mps is not None and mps.is_available()
    return name == "cpu"


def _smoke_test(model, device):
    """작은 더미 프레임으로 forward를 한 번 돌려 장치에서 실제로 동작하는지 확인합니다."""
    with torch.no_grad():
        src = torch.zeros(1, 3, 64, 64, device=device)
        model(src, downsample_ratio=1)


def load_model(variant="mobilenetv3", checkpoint=None, device="auto", rvm_path=None):
    """
    RVM 모델을 만들고 가중치를 불러온 뒤, 사용 가능한 장치로 옮겨 반환합니다.

    device="auto"이면 cuda → mps → cpu 순으로 시도하며, 장치가 없거나 모델을
    올려 시험 실행하는 중 오류가 나면 다음 장치로 넘어갑니다. 장치를 직접
    지정하면 그 장치만 시도합니다.

    반환값: (model, torch.device)
    """
    if variant not in VARIANTS:
        raise ValueError(f"variant는 {VARIANTS} 중 하나여야 합니다: {variant}")
    if device not in DEVICE_CHOICES:
        raise ValueError(f"device는 {DEVICE_CHOICES} 중 하나여야 합니다: {device}")

    checkpoint = Path(checkpoint or default_checkpoint(variant))
    if not checkpoint.is_file():
        raise FileNotFoundError(
            f"가중치 파일이 없습니다: {checkpoint}\n"
            f"  python scripts/download_weights.py --variant {variant}"
        )

    MattingNetwork = import_matting_network(rvm_path)
    model = MattingNetwork(variant).eval()
    state_dict = torch.load(checkpoint, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)

    candidates = AUTO_DEVICE_ORDER if device == "auto" else (device,)
    errors = []
    for name in candidates:
        if not _device_available(name):
            errors.append(f"{name}: 사용할 수 없음")
            continue
        try:
            dev = torch.device(name)
            model = model.to(dev)
            _smoke_test(model, dev)
            return model, dev
        except Exception as exc:  # 드라이버/연산 미지원 등 → 다음 장치로
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
            print(f"[경고] {name} 장치 사용 실패, 다음 장치를 시도합니다. ({exc})")
            model = model.to("cpu")

    raise RuntimeError("사용 가능한 장치가 없습니다.\n  " + "\n  ".join(errors))
