# RVM_code — 실시간 배경 분리·합성 파이프라인 (RobustVideoMatting 기반)

카메라·캡처카드·영상 파일에서 들어오는 영상에서 **사람만 실시간으로 분리**하고,
AI로 만든 배경 이미지와 **실시간 합성**하는 로컬 파이프라인입니다.
[RobustVideoMatting(RVM)](https://github.com/PeterL1n/RobustVideoMatting) 모델을
사용합니다.

- **그린스크린 불필요**
- **카메라 고정 불필요** — 카메라가 움직여도 됩니다
- **첫 프레임 마스크 지정 불필요** — 사람을 직접 칠해 줄 필요가 없습니다
- 인터넷 없이 오프라인으로 동작합니다 (설치·가중치 다운로드 때만 인터넷 필요)

> 이 저장소는 matanyone2, Part1, Part2, BiRefNet 저장소와 **공유하는 코드가 전혀
> 없는 독립 저장소**입니다. 서로의 코드를 가져오거나 import하지 않습니다.

### 진행 상황

| 단계 | 내용 | 파일 | 상태 |
|---|---|---|---|
| 1 | RVM 공식 저장소 설치 + 모델 불러오기 + 장치 자동 선택 | `rvm_loader.py` | ✅ |
| 2 | 사전학습 가중치 다운로드 + 설치 확인 | `scripts/download_weights.py`, `scripts/verify_install.py` | ✅ |
| 3 | 실시간 캡처·매팅 | `realtime_matte.py` | ⏳ 다음 단계 |
| 4 | AI 배경 플레이트와 실시간 합성 | `composite.py` | ⏳ 다음 단계 |
| 5 | 카메라 없이 테스트 영상으로 검증 | — | ⏳ 다음 단계 |

---

## ⚠️ 라이선스 (GPL-3.0) — 사용 전에 꼭 읽어 주세요

RVM은 **GNU GPL v3.0(GPL-3.0)** 라이선스입니다. 이 저장소의 스크립트는 RVM 코드를
불러와(import) 함께 실행되므로, 이 저장소도 같은 **GPL-3.0**으로 둡니다
([`LICENSE`](./LICENSE)).

### 회사 내부 제작용으로만 쓰는 경우

GPL-3.0에는 "비상업적 용도로만" 같은 제한이 **없습니다**. GPL-3.0의 의무(소스 공개
등)는 프로그램을 **외부에 배포(convey)할 때** 생깁니다. 따라서:

- **회사 내부 제작용으로만 사용하고 외부에 배포하지 않는 한, 상업적 이용(유료
  프로젝트 촬영·합성 등)에 제약이 없습니다.**
- 내부에서 코드를 자유롭게 수정해도 되고, 수정한 코드를 공개할 의무도 없습니다
  (GPL-3.0 제2조).
- 이 프로그램으로 만든 **결과물(합성된 영상·이미지)은 GPL 적용 대상이 아닙니다.**
  결과물에 프로그램 자체가 들어 있는 경우가 아니라면 자유롭게 납품·공개할 수
  있습니다 (GPL-3.0 제2조).
- 외주 인력이 **오로지 우리 회사를 위해, 우리 지시에 따라** 작업하는 용도로
  프로그램을 건네는 것은 배포로 보지 않는다는 조항이 있습니다 (GPL-3.0 제2조).
  다만 계약 형태에 따라 해석이 달라질 수 있습니다.
- GPL-3.0은 AGPL과 달리, 프로그램을 서버에서 돌리고 외부 사람이 네트워크로
  사용하게 하는 것만으로는 소스 공개 의무가 생기지 않습니다.

### 외부에 배포하는 경우 — 카피레프트 조건 적용

아래와 같은 경우는 "배포"에 해당할 수 있으며, 이때는 **카피레프트(copyleft)**
조건이 적용됩니다.

- 이 프로그램(또는 이를 포함한 프로그램)을 고객사·협력사·다른 법인(**계열사·
  자회사 포함**)에 전달하거나, 고객 PC/장비에 설치해 넘기는 경우
- 이 코드를 포함한 제품·앱·플러그인을 판매하거나 무료로 공개하는 경우

카피레프트 조건의 핵심:

1. 받는 사람에게 **전체 소스코드**(우리가 수정·추가한 부분 포함)를 함께
   제공하거나 제공을 약속해야 합니다.
2. 배포하는 프로그램 전체를 **GPL-3.0으로** 배포해야 합니다. 이 코드와 결합한 사내
   독점 코드도 공개 대상이 될 수 있습니다.
3. 받는 사람이 다시 수정·재배포하는 것을 막을 수 없습니다.
4. 저작권·라이선스 고지를 유지해야 합니다.

### 법무 검토 권장

> **본 안내는 법률 자문이 아니며, 개발 담당자가 이해한 GPL-3.0의 일반적인 해석을
> 정리한 것입니다.** 이 파이프라인을 외부 납품물·제품·서비스에 포함하거나, 고객사·
> 계열사·외주사에 프로그램 자체를 전달할 계획이 있다면 **사전에 반드시 사내 법무팀
> (또는 오픈소스 라이선스 전문 변호사)의 검토를 받으시기 바랍니다.** 특히 "배포"의
> 범위(계열사 간 전달, 외주 계약 형태, 장비 납품 시 설치 등)는 회사 상황에 따라
> 판단이 달라질 수 있습니다.

---

## 다른 매팅 모델과의 비교

| 항목 | **RVM** (이 저장소) | BackgroundMattingV2 | MatAnyone2 | BiRefNet |
|---|---|---|---|---|
| 카메라 고정 필요 | ❌ 불필요 | ✅ **필요** (깨끗한 배경 사진과 픽셀 단위로 비교) | ❌ 불필요 | ❌ 불필요 |
| 사전 입력 필요 | 없음 | 사람 없는 배경 사진 1장 | **첫 프레임 마스크 지정 필요** | 없음 |
| 시간적 일관성 | ✅ recurrent 구조로 자체 유지 | 프레임별 독립 처리 | ✅ 메모리 기반 전파 | ❌ 프레임별 독립 처리(깜빡임 가능) |
| 속도 | **매우 빠름** — HD 104FPS (GTX 1080 Ti, 공식 수치) | 빠름 — HD 60FPS (RTX 2080 Ti, 공식 수치) | 느림 — 실시간 용도 아님 | 느림 — 고해상도 이미지용 대형 모델 |
| 대상 | 사람 | 사람 | 사람(지정한 대상) | 범용 사물 |
| 라이선스 | **GPL-3.0** (상업 이용 가능, 배포 시 카피레프트) | MIT (제약 거의 없음) | **NTU S-Lab License 1.0** (**비상업 용도만** 허용) | MIT (제약 거의 없음) |

- 속도 수치는 각 공식 저장소가 밝힌 측정값(모델 추론만, 영상 입출력 제외)이며,
  실제 FPS는 PC 사양·해상도·입출력 방식에 따라 크게 달라집니다.
- 라이선스는 2026-10 기준 각 공식 저장소의 LICENSE/README를 확인한 내용입니다.
  MatAnyone2는 비상업 라이선스이므로 **회사 상업 제작에는 별도 허가 없이 쓸 수
  없다**는 점이 RVM과의 가장 큰 차이입니다.

---

## 설치 방법 (처음부터 순서대로)

프로그래밍을 몰라도 따라 할 수 있도록 순서대로 적었습니다. 회색 상자 안의 명령어를
복사해서 붙여넣고 Enter를 누르면 됩니다.

- **Windows**: 아래 2번에서 설치하는 **Miniforge Prompt**에 입력합니다.
- **macOS**: **터미널**(Spotlight에서 "터미널" 검색) 앱에 입력합니다.

### 1. Git 설치

Git은 코드를 내려받는 도구입니다.

- **Windows**
  1. https://git-scm.com/downloads 에서 Windows용 설치 파일을 받습니다.
  2. 설치 파일을 실행하고 옵션은 전부 기본값으로 "Next"만 눌러 설치를 끝냅니다.
- **macOS**
  1. 터미널을 열고 아래를 입력합니다.
     ```
     xcode-select --install
     ```
  2. 설치 창이 뜨면 "설치"를 누릅니다. (이미 설치되어 있다는 메시지가 나오면
     그대로 넘어가면 됩니다.)

설치 확인:
```
git --version
```
버전 번호가 나오면 성공입니다.

### 2. Miniforge 설치 (Python + 가상환경 도구)

Python과, 프로젝트 전용 실행 환경(가상환경)을 만들어 주는 도구를 함께 설치합니다.

- **Windows**
  1. https://github.com/conda-forge/miniforge/releases/latest 접속
  2. **`Miniforge3-Windows-x86_64.exe`**를 받아 실행합니다.
     - "Install for" 화면에서 **"Just Me"** 선택
     - **"Create start menu shortcuts"** 체크 유지
     - 나머지는 기본값으로 "Install" → "Finish"
  3. 시작 메뉴에서 **"Miniforge Prompt"**를 검색해 실행합니다. 앞으로 모든 명령은
     이 창에 입력합니다.
- **macOS**
  1. 터미널에서 아래 두 줄을 차례로 입력합니다.
     ```
     curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
     bash Miniforge3-$(uname)-$(uname -m).sh
     ```
  2. 안내문이 나오면 Enter/스페이스로 넘기고, 질문에는 모두 `yes`를 입력합니다.
  3. **터미널을 완전히 종료했다가 다시 엽니다.**

설치 확인:
```
conda --version
```

### 3. 이 저장소 내려받기

코드를 저장할 위치(예: 바탕화면)로 이동한 뒤 내려받습니다.

```
cd Desktop
git clone https://github.com/workseok/RVM_code.git
cd RVM_code
git checkout claude/elegant-einstein-ix03ih
```

> 마지막 줄은 현재 작업이 올라간 개발 브랜치로 이동하는 명령입니다. 이 내용이
> 메인 브랜치로 합쳐진 뒤에는 생략해도 됩니다.

### 4. 가상환경 만들기

```
conda create -n rvm python=3.11 -y
conda activate rvm
```

명령줄 맨 앞에 `(rvm)`이 보이면 성공입니다. **새 창을 열 때마다
`conda activate rvm`을 먼저 실행**해야 합니다.

### 5. 필요한 패키지 설치

`(rvm)`이 보이는 상태에서, `RVM_code` 폴더 안에서:

```
pip install -r requirements.txt
```

- `torch`, `torchvision`: AI 모델 실행 엔진(PyTorch)
- `opencv-python`: 카메라·영상 파일 읽기, 화면 출력
- `numpy`: 이미지 계산

> ⚠️ RVM 공식 저장소 안에 있는 `requirements_inference.txt`는 **설치하지 마세요.**
> 2021년 버전(torch 1.9)으로 고정되어 있어 Python 3.11에서는 설치가 실패합니다.
> 위 명령으로 설치하는 최신 버전에서 RVM이 정상 동작하는 것을 확인했습니다.

#### NVIDIA GPU가 있는 Windows PC라면 (선택, 강력 권장)

Windows에서 위 명령으로 설치한 PyTorch는 **GPU를 쓰지 않는 버전**입니다. NVIDIA
그래픽카드가 있다면 GPU 버전으로 바꿔야 실시간 속도가 나옵니다.

1. 그래픽카드 인식 확인:
   ```
   nvidia-smi
   ```
   표가 나오면 정상입니다. 오류가 나면 https://www.nvidia.com/Download/index.aspx
   에서 드라이버를 먼저 설치하세요.
2. GPU 버전 PyTorch로 다시 설치 (아래는 CUDA 12.6 예시입니다. 정확한 명령은
   https://pytorch.org/get-started/locally/ 에서 본인 환경을 선택해 확인하세요):
   ```
   pip uninstall torch torchvision -y
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
   ```
3. 확인:
   ```
   python -c "import torch; print(torch.cuda.is_available())"
   ```
   `True`가 나오면 성공입니다.

> **Mac(Apple Silicon, M1~M4)** 은 위 5번 명령만으로 Apple GPU(MPS)를 쓰는 버전이
> 설치됩니다. 따로 할 일이 없습니다.

### 6. RVM 공식 저장소 내려받기

RVM 모델 코드는 이 저장소에 복사해 넣지 않고, 공식 저장소를 `third_party` 폴더에
따로 내려받아 사용합니다. `RVM_code` 폴더 안에서:

```
git clone https://github.com/PeterL1n/RobustVideoMatting.git third_party/RobustVideoMatting
git -C third_party/RobustVideoMatting checkout 53d74c6
```

- 두 번째 줄은 동작 확인을 마친 버전(2023-03 최종 커밋 `53d74c6`)으로 고정하는
  명령입니다.
- `third_party` 폴더는 `.gitignore`에 등록되어 있어 이 저장소에 커밋되지 않습니다.
- 다른 위치에 내려받았다면, 환경변수 `RVM_REPO_PATH`나 각 스크립트의
  `--rvm-path` 옵션으로 경로를 알려주면 됩니다.

### 7. 사전학습 가중치(모델 파일) 다운로드

가중치는 AI가 학습한 결과가 담긴 파일입니다. 두 종류가 있습니다.

| 모델 | 파일 | 크기 | 특징 |
|---|---|---|---|
| **mobilenetv3** (권장, 기본값) | `rvm_mobilenetv3.pth` | 약 15MB | **속도 우선.** 실시간 용도에 적합 |
| resnet50 | `rvm_resnet50.pth` | 약 108MB | 품질 우선. 머리카락 등 경계가 조금 더 정확하지만 느림 |

`RVM_code` 폴더 안에서:

```
python scripts/download_weights.py
```

- `models/rvm_mobilenetv3.pth`가 저장되고, 파일이 손상되지 않았는지 자동으로
  검사합니다(SHA-256).
- resnet50도 쓰려면:
  ```
  python scripts/download_weights.py --variant resnet50
  ```
  둘 다 받으려면 `--variant all`.
- 회사 네트워크 등에서 다운로드가 막히면, 아래 주소를 브라우저로 열어 직접 받은 뒤
  `models` 폴더에 넣어도 됩니다. 넣은 뒤 위 명령을 다시 실행하면 파일이 정상인지
  확인해 줍니다.
  - https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3.pth
  - https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_resnet50.pth
- `.pth` 파일은 `.gitignore`에 등록되어 있어 커밋되지 않습니다.

> 이후 실행 스크립트에서는 `--variant resnet50` 옵션 하나로 모델을 바꿀 수 있게
> 만들 예정입니다.

### 8. 설치 확인

카메라 없이 실행됩니다.

```
python scripts/verify_install.py
```

아래처럼 4단계가 모두 통과하고 마지막에 `설치 확인 완료`가 나오면 준비 끝입니다.

```
[1/4] 패키지 확인
  torch 2.x / torchvision 0.x / opencv 4.x / numpy 2.x
[2/4] RVM 공식 저장소 확인
  OK
[3/4] 가중치 로드 + 장치 선택
  모델: mobilenetv3 / 장치: cuda
[4/4] 더미 프레임(1280x720) 추론 속도 측정
  95.3 FPS (알파 출력 크기 (1, 1, 720, 1280))

설치 확인 완료 — 모든 항목 정상입니다.
```

- `장치:`에는 사용 가능한 장치가 **cuda(NVIDIA GPU) → mps(Apple GPU) → cpu** 순서로
  자동 선택되어 표시됩니다. 앞 장치가 없거나 실행 중 오류가 나면 경고를 출력하고
  다음 장치로 넘어갑니다.
- 특정 장치를 강제로 쓰려면 `--device cuda`, `--device mps`, `--device cpu`.
- FPS 숫자는 PC 사양에 따라 다릅니다. 참고로 GPU 없는 클라우드 CPU 환경에서는
  mobilenetv3 기준 약 11 FPS가 나왔습니다. GPU가 있는데 `장치: cpu`로 나온다면
  5번의 GPU 설치 과정을 다시 확인하세요.

### 9. 실행

실시간 캡처·합성 스크립트(`realtime_matte.py`, `composite.py`)는 다음 단계에서
추가됩니다.

---

## 문제 해결

| 증상 | 해결 |
|---|---|
| `conda: command not found` | Windows는 **Miniforge Prompt**에서 실행했는지, macOS는 설치 후 터미널을 재시작했는지 확인 |
| `No module named 'torch'` 등 | 명령줄 앞에 `(rvm)`이 있는지 확인 → 없으면 `conda activate rvm` |
| `RVM 공식 저장소를 찾을 수 없습니다` | 6번을 `RVM_code` 폴더 안에서 실행했는지 확인 |
| `가중치 파일이 없습니다` | 7번 실행. `models` 폴더에 `.pth` 파일이 있는지 확인 |
| `해시가 맞지 않아 삭제했습니다` | 다운로드가 중간에 끊긴 경우. 다시 실행 |
| GPU가 있는데 `장치: cpu` | 5번의 "NVIDIA GPU가 있는 Windows PC라면" 과정 진행 |

## 파일 구성

```
RVM_code/
├── README.md
├── LICENSE                      GPL-3.0 전문
├── requirements.txt
├── rvm_loader.py                RVM 모델 불러오기 + 장치 자동 선택(cuda→mps→cpu)
├── scripts/
│   ├── download_weights.py      가중치 다운로드 + 무결성 검사
│   └── verify_install.py        설치 확인 (카메라 불필요)
├── models/                      가중치 저장 위치 (커밋 안 됨)
└── third_party/                 RVM 공식 저장소 clone 위치 (커밋 안 됨)
```

## 출처

- Lin, S., Yang, L., Saleemi, I., Sengupta, S. *Robust High-Resolution Video Matting
  with Temporal Guidance.* WACV 2022.
  https://github.com/PeterL1n/RobustVideoMatting (GPL-3.0)
