Instagram Crawler & YOLO Image Classifier
이 프로젝트는 Instaloader를 기반으로 인스타그램에서 이미지 및 동영상을 크롤링하고, YOLO 기반의 세그멘테이션 및 포즈 추론을 통해 이미지 내 인물(또는 인물 관련)을 분류하는 프로그램입니다. 또한 Tkinter 기반의 GUI를 제공하여 사용자가 계정 관리, 다운로드 경로 설정, 검색어 입력, 크롤링/분류 작업을 직관적으로 수행할 수 있도록 지원합니다.

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
    ├── classifier.py                 # GUI용 분류 모듈 (외부 스크립트 호출)
    ├── utils.py                      # 공통 유틸리티 (경로 생성, 이미지 로딩/변환 등)
    └── processing/                   # 분류/업스케일링 독립 실행형 스크립트 모음
         ├── classify_yolo.py         # (예시) YOLO 분류 스크립트
         └── upscaler.py              # GFPGAN+RealESRGAN 업스케일링 스크립트
</pre>
주요 기능
인스타그램 크롤링 및 다운로드

해시태그 또는 사용자 ID 기반으로 인스타그램 게시물을 다운로드합니다.

Instaloader를 활용해 로그인 세션 관리, 계정 전환 및 재로그인 등 안정적인 크롤링 기능을 제공합니다.

다운로드된 이미지, 영상, 릴스 등 다양한 미디어 파일은 지정한 디렉토리 구조에 저장됩니다.

이미지 분류

YOLO 기반의 세그멘테이션과 포즈 추론을 통해 이미지 내 인물 영역을 검출합니다.

GUI에서 호출되는 분류 모듈과 독립 실행형 분류 스크립트를 통해 인물, 인물(얼굴이 가려진 경우 혹은 몸통만 보이는 경우), 비인물로 분류합니다.

동적 배치 사이즈 조절 및 어노테이션 기능(테스트 모드)을 제공하여 분류 정확도와 처리 속도를 최적화합니다.

GUI 제공

Tkinter 기반의 직관적인 인터페이스를 통해 계정 관리, 검색어 입력, 다운로드 경로 설정, 진행 상황 모니터링 등의 작업을 지원합니다.

로그인 히스토리 관리 및 세션 파일 삭제 기능 등 사용자 편의 기능을 포함합니다.

설정 관리

config.py 모듈을 통해 JSON 형식의 설정 파일로 계정 정보, 마지막 검색 유형, 검색어, 인물 분류 옵션 등을 저장하고 불러옵니다.

주요 모듈 설명
config.py
설정 파일(config.json)을 사용하여 계정, 검색어, 분류 옵션 등을 관리합니다.

classifier.py
GUI에서 호출 가능한 YOLO 기반 분류 모듈로, 외부 분류 스크립트를 실행하여 지정된 이미지 디렉토리를 대상으로 분류 작업을 수행합니다.

downloader.py
Instaloader 라이브러리를 활용하여 인스타그램 로그인 및 게시물 다운로드를 수행합니다.
에러 처리, 계정 전환, 재로그인 등 안정적인 크롤링을 위한 기능을 포함합니다.

gui.py
Tkinter를 이용한 GUI 인터페이스를 제공하며, 계정 관리, 검색 설정, 진행 상황 모니터링, 다운로드 경로 관리 등을 지원합니다.

main.py
프로그램의 진입점으로, GUI를 실행합니다.

classification/classify_yolo.py
독립 실행형 YOLO 이미지 분류 스크립트입니다.
세그멘테이션, 포즈 추론, 키포인트 추출 및 어노테이션 기능을 포함하며,
테스트 모드에서는 어노테이션 이미지 저장, 생산 모드에서는 분류 결과에 따라 파일 이동 또는 복사를 수행합니다.

설치 및 실행
의존성 설치

분류 관련 의존성:
pip install -r requirements_classify.txt

인스타그램 크롤링 관련 의존성:
pip install -r requirements_insta.txt

프로젝트 실행 (GUI)

터미널에서:
python crawling/main.py
또는 Windows의 경우 run_project.bat 파일을 실행합니다.


독립 실행형 이미지 분류 (classify_yolo.py)

테스트 모드 (어노테이션 포함):
python crawling/classification/classify_yolo.py <target_image_dir>

테스트 모드 (원본만 복사):
python crawling/classification/classify_yolo.py <target_image_dir> --raw

생산 모드 (검색 유형, 검색어, 다운로드 경로 지정):
python crawling/classification/classify_yolo.py <target_image_dir> <search_type> <search_term> <download_path>

스크립트 실행 시 출력되는 Usage 정보를 참고하세요.

사용법
인스타그램 크롤링

프로그램 실행 후 GUI 창에서 "계정 추가" 버튼을 눌러 인스타그램 로그인 정보를 입력합니다.

해시태그 또는 사용자 ID 검색 옵션을 선택하고, 검색어를 입력합니다.

다운로드 경로를 지정한 후 "크롤링 시작" 버튼을 클릭하면 조건에 맞는 게시물이 다운로드됩니다.

진행 상황과 에러 메시지는 GUI의 상태창에 실시간으로 출력됩니다.

이미지 분류

크롤링이 완료되면 미분류 이미지가 저장된 디렉토리를 대상으로 분류 작업이 수행됩니다.

GUI 내에서 분류 작업을 실행하거나, 독립 실행형 분류 스크립트를 통해 결과를 확인할 수 있습니다.

분류 결과에 따라 이미지 파일은 "인물", "비인물", 또는 "비인물/body" 폴더로 이동 또는 복사됩니다.

결과 확인

테스트 모드에서는 어노테이션 이미지(검출 영역, 키포인트, 스켈레톤 등)를 별도의 파일로 저장하여 분류 결과를 시각적으로 확인할 수 있습니다.

주의사항
인스타그램 크롤링 시 Instaloader의 로그인 제한 및 인스타그램의 API 정책에 따라 계정 차단 등의 이슈가 발생할 수 있으므로, 여러 계정을 등록하거나 적절한 시간 간격을 두고 사용하시기 바랍니다.

이미지 분류 기능은 외부 YOLO 모델 파일(예: yolo11l-seg.pt, yolo11x-pose.pt)에 의존하므로, 해당 모델 파일들이 올바른 경로(예: crawling/yolo_model/)에 존재해야 합니다.

크롤링 및 분류 작업 중 발생하는 에러 및 로그는 터미널 또는 GUI의 상태창에서 확인할 수 있으며, 문제 발생 시 참고하시기 바랍니다.

라이선스 및 기여
본 프로젝트의 라이선스 및 기여 방법은 추후 업데이트 예정입니다.
