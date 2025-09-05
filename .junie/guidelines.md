# 프로젝트 가이드라인

## Junie 응답 가이드라인

**중요**: Junie는 항상 한국어로 응답하고 모든 진행과정 설명도 한국어로 제공해야 합니다. 이는 모든 세션에서 지켜져야 하는 필수 요구사항입니다.

## 프로젝트 개요

이 프로젝트는 **Instagram 크롤링, 이미지 분류, 업스케일링을 위한 통합 GUI 솔루션**입니다. 사용자 친화적인 인터페이스를 통해 Instagram 이미지/영상 다운로드, YOLO 기반 인물 분류, GFPGAN/Real-ESRGAN을 활용한 이미지 업스케일링 기능을 제공합니다.

## 프로젝트 구조

```
프로젝트 루트/
├── run_project.bat                   # 메인 실행 파일
├── src/                              # 소스 코드
│   ├── main.py                       # GUI 진입점
│   ├── core/                         # 크롤링 핵심 로직
│   ├── gui/                          # GUI 컴포넌트 (Tkinter 기반)
│   ├── processing/                   # 이미지 분류/업스케일링 모듈
│   └── utils/                        # 유틸리티 함수
├── models/                           # YOLO, GFPGAN, Real-ESRGAN 모델
├── data/                             # 설정, 다운로드, 로그 파일
├── requirements/                     # 의존성 파일
└── venv/                             # 가상환경 (2개: insta_venv, classify_venv)
```

## 개발 가이드라인

### 실행 방법
- **권장**: `run_project.bat` 사용 (자동 환경 설정 및 실행)
- **직접 실행**: `python -m src.main`

### 가상환경 구조
- **insta_venv**: Instagram 크롤링 전용 (Instaloader 등)
- **classify_venv**: 이미지 처리 전용 (PyTorch, OpenCV 등)

### 테스트 접근법
- 테스트 자동화 없음 (GUI 기반 프로젝트 특성상)
- **수동 테스트 권장**:
  1. GUI 실행 후 각 기능 테스트
  2. 크롤링 → 분류 → 업스케일링 전체 워크플로우 검증
  3. 로그 파일(`data/logs/`) 확인

### 빌드 및 배포
- 별도 빌드 과정 불필요
- 의존성 설치 후 바로 실행 가능
- 모델 파일은 런타임 시 자동 다운로드

### 코딩 스타일
- **Python PEP 8** 준수
- **모듈화된 GUI 구조** 유지 (components/, controllers/, handlers/)
- **한국어 주석 및 로그 메시지** 사용
- **예외 처리** 필수 (네트워크 오류, 파일 I/O 오류 등)

### 주의사항
- Instagram API 정책 준수
- 요청 간 대기시간 설정으로 차단 방지
- GPU 메모리 부족 시 CPU 모드 자동 전환
- Firefox 쿠키 기반 세션 관리 필요
