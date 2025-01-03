===============================================================================
                           Instagram Crawling & Classification
===============================================================================

개요
-------------------------------------------------------------------------------
이 프로젝트는 Instaloader 라이브러리를 사용하여 인스타그램 게시물을
크롤링(다운로드)하고, YOLO + Detectron2 모델로 이미지를 "인물 / 비인물"로
자동 분류하는 GUI 기반 프로그램입니다.

===============================================================================
1. 디렉토리 구조
===============================================================================
test/
  ├─ crawling/
  │   ├─ classification/
  │   │   ├─ classify_venv/
  │   │   ├─ detectron2/
  │   │   ├─ yolo_model/
  │   │   ├─ classify_yolo_v16.py    (실사용 YOLO + Detectron2 분류)
  │   │   └─ [기타 classify_yolo_* 및 테스트 파일들]
  │   ├─ insta_venv/                (크롤링용 가상환경)
  │   ├─ sessions/                  (Instaloader 세션파일 저장)
  │   ├─ __pycache__/
  │   ├─ classifier.py              (실사용: 분류 스크립트 호출/관리)
  │   ├─ config.py                  (실사용: 설정 로드/저장)
  │   ├─ downloader.py              (실사용: Instaloader로 게시물 다운로드)
  │   ├─ gui.py                     (실사용: Tkinter GUI)
  │   ├─ main.py                    (실사용: GUI 실행 런처)
  │   └─ __init__.py
  ├─ download/
  │   ├─ hashtag/
  │   └─ ID/
  └─ classify.py                    (다른 분류 방법 사용 시, "실사용 코드" 표기)

===============================================================================
2. 주요 파일별 설명
===============================================================================
[1] main.py
  - 프로그램 진입점. "python main.py" 로 실행 시,
    gui.py 의 main_gui() 함수를 불러와 GUI를 시작합니다.

[2] gui.py
  - Tkinter 기반의 메인 GUI.
  - 계정 추가/삭제, 해시태그/사용자 ID 입력, 다운로드 옵션 설정, 로그/진행도 표시 등
    전체 기능을 사용자 친화적으로 제공합니다.
  - 크롤링: downloader.py 의 crawl_and_download() 호출
  - 분류: classifier.py 의 classify_images() (또는 버튼 클릭으로 직접 실행)

[3] config.py
  - config.json 파일을 통해 계정 정보, 검색어 목록, 다운로드 옵션 등을
    로드/저장하는 기능 담당.

[4] downloader.py
  - Instaloader 라이브러리를 사용해 인스타그램 게시물을 실제로 다운로드.
  - 해시태그 기반 (download_posts) 또는 사용자 프로필 기반(user_download_with_profiles) 다운로드를
    실행하며, 필요한 경우 각 계정 세션을 로딩/저장, 중복을 방지하기 위해
    latest-stamps 파일을 사용 가능합니다.
  - 다운로드 후 설정(인물 분류)이 되어 있으면 즉시 classifier.py 를 호출하여
    분류를 수행.

[5] classifier.py
  - 분류 스크립트(`classify_yolo_v16.py`)를 서브프로세스(subprocess)로 실행,
    다운로드된 이미지 디렉토리를 "인물" / "비인물" 폴더로 분류합니다.
  - run_classification_process(): 서브프로세스 생성 및 실행 관리
  - classify_images(): GUI 등에서 호출 시, 실제 target_image_dir 찾고
    run_classification_process() 통해 YOLO+Detectron2 스크립트 수행

[6] classify_yolo_v16.py
  - YOLO + Detectron2(Instance & Keypoint) 앙상블로 이미지를 분석.
  - 인물/얼굴/몸 키포인트를 검출 후, 임계값에 따라 "인물" 폴더 이동,
    그렇지 않으면 "비인물" 폴더 이동.
  - 스크립트 단독 실행 시: python classify_yolo_v16.py [이미지_디렉토리]
  - 프로젝트 내부 실행 시: classifier.py에서 subprocess 호출

[7] classify.py
  - Mediapipe 등을 이용한 또 다른 분류 방식을 포함하는 "실사용 코드"라고 표기됨.
  - 현재는 classify_yolo_v16.py가 주로 사용되나, 필요 시 대체/보완 용도로 추정.

===============================================================================
3. 주요 실행 흐름
===============================================================================
1) "python main.py" 혹은 "python crawling/main.py" 실행
2) Tkinter GUI 창(gui.py) 오픈
3) - 계정 추가/제거 (Instaloader 로그인 정보)
   - 해시태그 or 사용자 ID 입력
   - 이미지/영상/릴스, 중복 허용 여부 등 옵션 설정
   - "크롤링 시작" 버튼 → downloader.py 실행
4) Instaloader로 인스타 게시물 다운로드 (download/ 폴더에 저장)
5) 다운로드 완료 후 "인물 분류" 옵션 시,
   classifier.py → classify_yolo_v16.py (subprocess) → 
   YOLO+Detectron2 분류 수행 → "인물" / "비인물" 폴더 분류
6) GUI에 진행 상태/로그 표시, "중지" 버튼으로 언제든 프로세스 종료 가능

===============================================================================
4. 기타 참고
===============================================================================
- 세션 파일: sessions/username.session 에 저장 (자동 로그인)
- 중복 방지: latest-stamps-images.ini, latest-stamps-reels.ini
- config.json: ACCOUNTS, SEARCH_TERMS, INCLUDE_IMAGES 등 설정 유지
- 가상환경: insta_venv(크롤링용), classify_venv(분류용)

===============================================================================
(끝)
===============================================================================
