# 프로젝트 구조

## 📁 디렉토리 구조

```
instaloader-gui/
├── run_project.bat              # 🚀 애플리케이션 실행 스크립트
├── src/                         # 📦 소스 코드 메인 디렉토리
│   ├── gui/                     # 🖥️ GUI 관련 모듈 (모듈화된 구조)
│   │   ├── main_window.py       # 메인 GUI 창 (모듈화된 구조)
│   │   ├── components/          # GUI 컴포넌트들
│   │   │   ├── account_panel.py      # 계정 관리 패널
│   │   │   ├── search_panel.py       # 검색 설정 패널
│   │   │   ├── progress_panel.py     # 진행률 표시 패널
│   │   │   └── status_panel.py       # 상태 로그 패널
│   │   ├── controllers/         # GUI 컨트롤러
│   │   │   └── gui_controller.py     # 메인 GUI 컨트롤러
│   │   ├── dialogs/             # 다이얼로그 관련
│   │   │   ├── account_management.py # 계정 관리 다이얼로그
│   │   │   ├── profile_manager.py    # 프로필 관리 다이얼로그
│   │   │   └── settings.py           # 설정 다이얼로그
│   │   └── handlers/            # 이벤트 핸들러
│   │       └── queue_handler.py      # 큐 기반 이벤트 처리
│   ├── core/                    # 🔧 핵심 기능
│   │   ├── downloader.py        # Instagram 크롤링 및 다운로드
│   │   ├── profile_manager.py   # 프로필 관리 (존재하지 않는/비공개 프로필)
│   │   └── anti_detection.py    # Anti-Detection 4단계 시스템
│   ├── processing/              # 🖼️ 후처리 관련
│   │   ├── classifier.py        # 이미지 분류 래퍼
│   │   ├── post_processing.py   # 후처리 제어 (분류 + 업스케일링)
│   │   ├── yolo/                # YOLO 모델 기반 분류
│   │   │   └── classify_yolo.py      # YOLO 분류 모듈
│   │   └── upscaler/            # 업스케일링
│   │       └── upscaler.py           # GFPGAN + RealESRGAN 업스케일링
│   ├── utils/                   # 🛠️ 유틸리티
│   │   ├── config.py            # 설정 파일 관리 (JSON 기반)
│   │   ├── environment.py       # 환경 설정 및 경로 관리
│   │   ├── security.py          # Fernet 암호화 및 보안 관리
│   │   ├── secure_logging.py    # 보안 로깅 (민감정보 마스킹)
│   │   ├── file_utils.py        # 파일 관련 유틸리티
│   │   └── logger.py            # 로깅 시스템
│   └── main.py                  # 애플리케이션 진입점
├── data/                        # 📊 데이터 디렉토리
│   ├── config/                  # 설정 파일들
│   │   ├── config.json          # 메인 설정 파일
│   │   └── latest-stamps-images.ini  # 다운로드 타임스탬프
│   ├── sessions/                # 세션 파일들 (Firefox 쿠키 기반)
│   └── downloads/               # 다운로드된 파일들
├── models/                      # 🤖 AI 모델들
│   ├── classification/          # YOLO 분류 모델
│   │   ├── yolo11l-seg.pt       # 세그멘테이션 모델 (53MB)
│   │   └── yolo11x-pose.pt      # 포즈 추정 모델 (113MB)
│   └── upscaling/               # 업스케일링 모델 (자동 다운로드)
├── logs/                        # 📝 로그 파일들
├── docs/                        # 📚 문서
├── requirements/                # 📋 의존성 파일들
│   ├── requirements_insta.txt   # Instagram 크롤링 의존성
│   └── requirements_classify.txt # 분류/업스케일링 의존성
├── venv/                        # 🐍 가상환경
│   ├── insta_venv/              # Instagram 크롤링 가상환경
│   └── classify_venv/           # 분류/업스케일링 가상환경
├── .gitignore
└── README.md
```

## 🚀 실행 방법

```bash
# Windows (권장)
run_project.bat

# 또는 직접 실행
python -m src.main
```

## 📝 주요 모듈 설명

### GUI 모듈 (`src/gui/`)
- **main_window.py**: 모듈화된 메인 GUI 창
- **components/**: 재사용 가능한 GUI 컴포넌트
  - `account_panel.py`: 계정 관리 패널
  - `search_panel.py`: 검색 설정 패널 (드롭다운 정렬 포함)
  - `progress_panel.py`: 진행률 표시 패널
  - `status_panel.py`: 상태 로그 패널 (스크롤바 포함)
- **controllers/**: GUI 로직 제어
  - `gui_controller.py`: 메인 GUI 컨트롤러 (큐 기반 메시지 처리)
- **handlers/**: 이벤트 처리
  - `queue_handler.py`: 큐 기반 이벤트 핸들러
- **dialogs/**: 다이얼로그 창들
  - `account_management.py`: 계정 관리 (세션 삭제 기능)
  - `profile_manager.py`: 프로필 관리 (존재하지 않는/비공개 프로필)
  - `settings.py`: 설정 다이얼로그

### 핵심 기능 (`src/core/`)
- **downloader.py**: Instagram 크롤링 및 다운로드
  - Firefox 쿠키 기반 세션 관리
  - 자동 검색 목록 정리
  - 진행률 및 ETA 업데이트
- **profile_manager.py**: 프로필 관리
  - 존재하지 않는 프로필 관리
  - 비공개 프로필 관리
- **anti_detection.py**: Anti-Detection 4단계 시스템
  - OFF/FAST/ON/SAFE 모드 설정
  - 모드별 Rate Controller 최적화
  - 기존 설정 자동 마이그레이션

### 후처리 (`src/processing/`)
- **classifier.py**: 이미지 분류 래퍼
- **post_processing.py**: 후처리 제어 (분류 + 업스케일링)
- **yolo/**: YOLO 모델 기반 분류
  - `classify_yolo.py`: YOLO 분류 모듈 (세그멘테이션 + 포즈 추정)
- **upscaler/**: 업스케일링
  - `upscaler.py`: GFPGAN + RealESRGAN 업스케일링

### 유틸리티 (`src/utils/`)
- **config.py**: JSON 기반 설정 파일 관리
- **environment.py**: 환경 설정 및 경로 관리
- **security.py**: Fernet 암호화 및 보안 관리
  - 머신 지문 기반 암호화 키 생성
  - 계정 비밀번호 안전 저장/복호화
- **secure_logging.py**: 보안 로깅 시스템
  - 민감정보 자동 마스킹 (사용자명, 비밀번호)
  - 안전한 로그 출력 함수들
- **logger.py**: 로깅 시스템
- **file_utils.py**: 파일 관련 유틸리티

## 🔧 개발 가이드

### 새 컴포넌트 추가
1. `src/gui/components/` 디렉토리에 새 컴포넌트 생성
2. `__init__.py` 파일에 모듈 정보 추가
3. `main_window.py`에서 컴포넌트 통합

### 새 컨트롤러 추가
1. `src/gui/controllers/` 디렉토리에 새 컨트롤러 생성
2. 큐 기반 메시지 처리 구조 활용
3. `gui_controller.py`에서 컨트롤러 통합

### 설정 변경
1. `src/utils/config.py`에서 기본값 수정
2. `src/utils/environment.py`에서 경로 수정
3. 설정 파일 구조 변경 시 `data/config/config.json` 업데이트

### 로깅 사용
```python
from src.utils.logger import get_app_logger

logger = get_app_logger("module_name")
logger.info("로그 메시지")
```

### 큐 기반 메시지 처리
```python
# 메시지 전송
progress_queue.put(("message_type", data))

# 메시지 수신 (gui_controller.py의 _progress_worker에서 처리)
if message_type == "term_complete":
    self.status_panel.append_status(f"{term} 완료")
```

## 🎯 주요 기능 흐름

### 크롤링 프로세스
1. **GUI 설정** → `search_panel.py`
2. **크롤링 시작** → `gui_controller.py`
3. **다운로드 실행** → `downloader.py`
4. **진행률 업데이트** → `progress_panel.py`
5. **상태 로그** → `status_panel.py`
6. **자동 정리** → 완료된 항목 검색 목록에서 제거

### 분류 프로세스
1. **분류 시작** → `post_processing.py`
2. **YOLO 분류** → `classify_yolo.py`
3. **업스케일링** → `upscaler.py` (선택적)
4. **완료 알림** → 큐를 통한 상태 업데이트
