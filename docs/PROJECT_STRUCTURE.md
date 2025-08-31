# 프로젝트 구조

## 📁 디렉토리 구조

```
instaloader-gui/
├── run_project.bat              # 🚀 애플리케이션 실행 스크립트
├── src/                         # 📦 소스 코드 메인 디렉토리
│   ├── gui/                     # 🖥️ GUI 관련 모듈
│   │   ├── main_window.py       # 메인 GUI 창
│   │   ├── dialogs/             # 다이얼로그 관련
│   │   │   ├── account_management.py
│   │   │   ├── non_existent_profiles.py
│   │   │   └── settings.py
│   │   ├── handlers/            # 이벤트 핸들러
│   │   │   └── queue_handler.py
│   │   └── widgets/             # 커스텀 위젯
│   ├── core/                    # 🔧 핵심 기능
│   │   ├── downloader.py        # Instagram 크롤링
│   │   └── profile_manager.py   # 프로필 관리
│   ├── processing/              # 🖼️ 후처리 관련
│   │   ├── classifier.py        # 이미지 분류
│   │   ├── post_processing.py   # 후처리
│   │   ├── yolo/                # YOLO 모델
│   │   │   └── classify_yolo.py
│   │   └── upscaler/            # 업스케일링
│   │       └── upscaler.py
│   ├── utils/                   # 🛠️ 유틸리티
│   │   ├── config.py            # 설정 관리
│   │   ├── environment.py       # 환경 설정
│   │   ├── file_utils.py        # 파일 유틸리티
│   │   └── logger.py            # 로깅 시스템
│   └── main.py                  # 애플리케이션 진입점
├── data/                        # 📊 데이터 디렉토리
│   ├── config/                  # 설정 파일들
│   │   ├── config.json
│   │   └── latest-stamps-images.ini
│   ├── sessions/                # 세션 파일들
│   └── downloads/               # 다운로드된 파일들
├── models/                      # 🤖 AI 모델들
├── logs/                        # 📝 로그 파일들
├── tests/                       # 🧪 테스트 코드
├── docs/                        # 📚 문서
├── requirements/                # 📋 의존성 파일들
│   ├── requirements_insta.txt
│   └── requirements_classify.txt
├── .gitignore
└── README.md
```

## 🔄 주요 변경사항

### 1. 모듈 분리 및 구조화
- **기존**: `crawling/` 디렉토리에 모든 파일이 혼재
- **개선**: 기능별로 명확하게 분리된 디렉토리 구조

### 2. 데이터 관리 개선
- **설정 파일**: `data/config/`로 이동하여 관리 용이성 향상
- **세션 파일**: `data/sessions/`로 이동
- **다운로드**: `data/downloads/`로 통일

### 3. 환경 설정 중앙화
- **Environment 클래스**: 모든 경로를 중앙에서 관리
- **로깅 시스템**: 체계적인 로그 관리
- **설정 관리**: 개선된 설정 파일 관리

### 4. 실행 스크립트 유지
- **`run_project.bat`**: 최상위에 유지하여 사용자 편의성 보장

## 🚀 실행 방법

```bash
# Windows
run_project.bat

# 또는 직접 실행
python -m src.main
```

## 📝 주요 모듈 설명

### GUI 모듈 (`src/gui/`)
- **main_window.py**: 메인 GUI 창
- **dialogs/**: 각종 다이얼로그 (계정 관리, 설정 등)
- **handlers/**: 이벤트 처리 로직
- **widgets/**: 재사용 가능한 커스텀 위젯

### 핵심 기능 (`src/core/`)
- **downloader.py**: Instagram 크롤링 및 다운로드
- **profile_manager.py**: 프로필 ID 기반 관리

### 후처리 (`src/processing/`)
- **classifier.py**: 이미지 분류
- **yolo/**: YOLO 모델 기반 분류
- **upscaler/**: 이미지 해상도 향상

### 유틸리티 (`src/utils/`)
- **config.py**: 설정 파일 관리
- **environment.py**: 환경 설정 및 경로 관리
- **logger.py**: 로깅 시스템
- **file_utils.py**: 파일 관련 유틸리티

## 🔧 개발 가이드

### 새 모듈 추가
1. 적절한 디렉토리에 파일 생성
2. `__init__.py` 파일에 모듈 정보 추가
3. import 경로 업데이트

### 설정 변경
1. `src/utils/config.py`에서 기본값 수정
2. `src/utils/environment.py`에서 경로 수정

### 로깅 사용
```python
from src.utils.logger import get_app_logger

logger = get_app_logger("module_name")
logger.info("로그 메시지")
```
