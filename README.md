Instagram Crawling, Classification, and Upscaling Project
이 프로젝트는 인스타그램 이미지 크롤링, 이미지 분류(주로 인물 및 비인물 구분), 그리고 업스케일링(이미지 해상도 향상)을 위한 통합 솔루션입니다. 사용자 친화적인 GUI를 제공하여 계정 관리, 검색 옵션 설정, 다운로드 경로 지정 및 후처리(분류/업스케일링) 작업을 쉽게 수행할 수 있습니다.

프로젝트 개요
크롤링 기능:
인스타그램에서 해시태그나 사용자 ID 기반으로 이미지(및 영상)를 다운로드합니다. Instaloader 라이브러리를 활용하며, Firefox 쿠키 파일을 통한 세션 관리 및 로그인 기능을 지원합니다.
(자세한 내용은 downloader.py 참고)

이미지 분류:
YOLO 기반 모델을 사용하여 크롤링한 이미지에서 인물, 얼굴, 몸통 등을 검출하고 분류합니다. 분류 결과에 따라 이미지가 ‘인물’, ‘비인물’ 등으로 나뉩니다.
(classify_yolo.py, post_processing.py 참고)

업스케일링:
GFPGAN과 Real-ESRGAN 모델을 결합하여 이미지의 해상도를 향상시키며, 특히 얼굴 복원 기능을 통해 인물 사진의 디테일을 개선합니다.
(upscaler.py 참고)

GUI 제공:
Tkinter를 사용하여 직관적인 GUI를 제공, 계정 추가/삭제, 세션 관리, 검색 옵션 및 다운로드 경로 설정 등 작업을 시각적으로 제어할 수 있습니다.
(gui.py, main.py 참고)

설정 및 유틸리티:
config.py를 통해 JSON 파일에 설정을 저장/불러오며, utils.py는 디렉토리 생성, 이미지 변환, 병렬 이미지 로딩 등 여러 공통 유틸리티 함수를 제공합니다.
(config.py, utils.py 참고)

프로젝트 구조

<pre>
프로젝트 루트/
├── requirements_classify.txt         # 분류/업스케일링 의존성
├── requirements_insta.txt            # 인스타그램 크롤링 의존성
├── run_project.bat                   # 실행 배치 파일
├── venv/
│   ├── classify_venv/                # 분류/업스케일링 전용 venv (torch, gfpgan, realesrgan 등)
│   └── insta_venv/                   # 인스타그램 크롤링 전용 venv (Instaloader 등)
├── models/
│   ├── classification/               # YOLO 등 분류 관련 모델 파일
│   └── upscaling/                    # GFPGAN, RealESRGAN 등 업스케일링 관련 모델 파일
└── crawling/
    ├── config.py                     # 설정 파일 로드/저장
    ├── downloader.py                 # 인스타그램 크롤링 모듈
    ├── gui.py                        # Tkinter GUI
    ├── main.py                       # 진입점 (GUI 실행)
    ├── post_processing.py            # 분류 및 업스케일링 프로세스 제어 모듈
    ├── utils.py                      # 공통 유틸리티 (경로 생성, 이미지 로딩/변환 등)
    └── processing/                   # 분류/업스케일링 독립 실행형 스크립트 모음
         ├── classify_yolo.py         # (예시) YOLO 분류 스크립트
         └── upscaler.py              # GFPGAN+RealESRGAN 업스케일링 스크립트
</pre>

설치 및 설정
의존성 설치:

분류 및 업스케일링 관련 라이브러리는 requirements_classify.txt에,

인스타그램 크롤링 관련 라이브러리는 requirements_insta.txt에 명시되어 있습니다.
각 가상환경(venv)을 별도로 생성하여 필요한 의존성을 설치하세요.

모델 파일:

분류 모델 파일은 models/classification/ 폴더에 위치해야 하며,

업스케일링 모델 파일은 models/upscaling/ 폴더에 위치합니다.
업스케일링 스크립트는 파일이 없으면 자동으로 다운로드를 시도합니다.
(upscaler.py 참고)

설정 파일:

기본 설정은 crawling/config.py에 정의되어 있으며, 실행 시 config.json 파일을 생성 및 로드합니다.
(config.py 참고)

사용 방법
GUI 실행
진입점:
crawling/main.py 파일이 GUI 애플리케이션의 진입점입니다.
배치 파일(run_project.bat)이나 직접 Python 인터프리터를 통해 실행할 수 있습니다.

기능:

계정 추가/삭제 및 세션 파일 관리

해시태그 또는 사용자 ID로 검색 옵션 설정

다운로드 경로 선택 및 게시물 수 설정

분류(인물, 비인물) 및 업스케일링 옵션 선택

진행 상태 및 로그 메시지 실시간 확인
(gui.py, main.py 참고)

명령줄 모드 (독립 실행형 스크립트)
이미지 분류:
crawling/processing/classify_yolo.py 스크립트를 통해 대상 이미지 디렉토리 내 이미지를 YOLO 모델로 분류할 수 있습니다.
사용법 및 옵션은 스크립트 상단 주석을 참고하세요.
(classify_yolo.py 참고)

이미지 업스케일링:
crawling/processing/upscaler.py 스크립트는 GFPGAN과 RealESRGAN을 결합하여 이미지를 업스케일링합니다.
스크립트 내에서 모델 파일의 자동 다운로드 기능을 제공합니다.
(upscaler.py 참고)

후처리:
crawling/post_processing.py에서는 분류 및 업스케일링 프로세스를 서브프로세스로 실행하며, GUI와의 연동을 통해 진행 상태를 모니터링합니다.
(post_processing.py 참고)

코드 구성 세부 내용
설정 관리 (config.py):
JSON 파일로 설정을 저장/불러오며, 기본 설정값(계정 목록, 검색 타입, 검색어 등)을 정의합니다.
(config.py 참고)

Instagram 크롤링 (downloader.py):
Instaloader를 사용하여 인스타그램에 로그인(세션/쿠키 활용)하고, 해시태그 기반 게시물 다운로드 및 영상 파일 이동 등의 기능을 제공합니다.
(downloader.py 참고)

유틸리티 함수 (utils.py):
디렉토리 생성, 이미지 파일 변환(WebP → JPEG), 이미지 로딩 및 병렬 처리 기능을 포함합니다.
(utils.py 참고)

분류 및 업스케일링 스크립트:

YOLO 분류: 대상 이미지에서 사람(및 관련 부위)을 검출하고, 일정 임계값 이상의 경우 해당 이미지를 분류합니다.
(classify_yolo.py 참고)

업스케일링: 얼굴 복원(GFPGAN) 후 전체 이미지 업스케일링(RealESRGAN) 과정을 수행합니다.
(upscaler.py 참고)

개발 및 확장
가상환경 분리:
인스타그램 크롤링과 분류/업스케일링 작업을 별도의 가상환경(venv)에서 관리하여, 라이브러리 간 충돌을 방지합니다.

GUI 개선:
Tkinter 기반 인터페이스를 통해 사용자가 쉽게 계정을 관리하고, 다운로드 및 후처리 옵션을 조정할 수 있도록 설계되었습니다.

모듈화:
각 기능(설정 관리, 크롤링, 후처리, 업스케일링 등)을 모듈화하여 독립 실행형 스크립트 및 서브프로세스 호출 방식으로 확장 및 유지보수가 용이합니다.

참고 및 라이선스
본 프로젝트는 Instaloader 및 Ultralytics YOLO 등의 오픈소스 라이브러리를 활용합니다.

업스케일링 관련 모델은 GFPGAN, RealESRGAN을 사용하며, 각 모델의 라이선스 정책을 따릅니다.


