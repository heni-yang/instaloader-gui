@echo off
chcp 65001 >nul

REM ==============================================================================
REM 1) 현재 배치 파일이 있는 경로(프로젝트 루트)로 이동
REM ==============================================================================
cd /d "%~dp0"
echo [INFO] 프로젝트 루트 디렉토리: %cd%

REM -----------------------------------------------------------------
REM (A) where.exe python 결과를 순회하여 3.10 / 3.13 경로 식별
REM -----------------------------------------------------------------
setlocal enabledelayedexpansion

set "PYTHON_310="
set "PYTHON_313="

echo [INFO] "where.exe python" 결과로부터 Python 3.10 / 3.13 경로 검색...
for /f "usebackq delims=" %%I in (`where.exe python`) do (
REM    echo   경로 후보: %%~I
    for /f "tokens=*" %%V in ('"%%~I" --version 2^>^&1') do (
        echo       버전: %%V
        echo %%V | findstr /i "3.10" >nul
        if !errorlevel! == 0 (
            if not defined PYTHON_310 (
                set "PYTHON_310=%%~I"
                echo       PYTHON_310 = %%~I
            )
        )
        echo %%V | findstr /i "3.13" >nul
        if !errorlevel! == 0 (
            if not defined PYTHON_313 (
                set "PYTHON_313=%%~I"
                echo       PYTHON_313 = %%~I
            )
        )
    )
)

if not defined PYTHON_310 (
    echo [WARN] Python 3.10을 찾지 못했습니다. 분류 기능은 사용할 수 없습니다.
    echo.
)
if not defined PYTHON_313 (
    echo [WARN] Python 3.13을 찾지 못했습니다. insta_venv 생성이 불가능할 수 있습니다.
    echo.
)

REM -----------------------------------------------------------------
REM (B) insta_venv / classify_venv 생성/설치/실행
REM -----------------------------------------------------------------
REM 새 구조: venv 디렉토리 아래에 insta_venv와 classify_venv를 둡니다.
set "INSTA_ENV_PATH=venv\insta_venv"
set "CLASSIFY_ENV_PATH=venv\classify_venv"

REM requirements (사용자 환경에 맞게 파일명 수정)
set "INSTA_REQ=requirements\requirements_insta.txt"
set "CLASSIFY_REQ=requirements\requirements_classify.txt"
set "TORCH_REQ=requirements\requirements_torch.txt"

echo.
echo ==============================================================================
echo 2) [크롤링용] insta_venv 환경 확인
echo ==============================================================================
if exist "%INSTA_ENV_PATH%\Scripts\python.exe" (
    echo [INFO] insta_venv 이미 존재합니다.
    
    REM requirements 파일이 변경되었는지 확인
    set "REQ_CHECK_FILE=%INSTA_ENV_PATH%\requirements_check.txt"
    set "UPDATE_NEEDED=0"
    
    if not exist "!REQ_CHECK_FILE!" (
        set "UPDATE_NEEDED=1"
        echo [INFO] 첫 실행이거나 requirements 체크 파일이 없습니다.
    ) else (
        fc /b "%INSTA_REQ%" "!REQ_CHECK_FILE!" >nul 2>&1
        if errorlevel 1 (
            set "UPDATE_NEEDED=1"
            echo [INFO] requirements 파일이 변경되었습니다.
        )
    )
    
    if !UPDATE_NEEDED! == 1 (
        echo [INFO] requirements 업데이트 중...
        call "%INSTA_ENV_PATH%\Scripts\activate.bat"
        
        REM 변경된 패키지만 재설치 (git 저장소의 경우)
        for /f "usebackq delims=" %%i in ("%INSTA_REQ%") do (
            set "line=%%i"
            echo "!line!" | findstr /i "git+" >nul
            if !errorlevel! == 0 (
                echo [INFO] 재설치: !line!
                pip install "!line!" --force-reinstall --no-deps >nul 2>&1
            ) else (
                echo [INFO] 업데이트: !line!
                pip install "!line!" --upgrade >nul 2>&1
            )
        )
        
        if errorlevel 1 (
            echo [WARN] requirements 업데이트 중 일부 오류가 발생했습니다.
        ) else (
            echo [INFO] requirements 업데이트 완료.
            copy "%INSTA_REQ%" "!REQ_CHECK_FILE!" >nul
        )
        call "%INSTA_ENV_PATH%\Scripts\deactivate.bat"
    ) else (
        echo [INFO] requirements 변경사항 없음. 업데이트를 건너뜁니다.
    )
) else (
    if not defined PYTHON_313 (
        echo [ERROR] Python 3.13 경로를 찾지 못했습니다. insta_venv를 생성할 수 없습니다.
        echo [INFO] 크롤링 기능을 사용할 수 없습니다. 스크립트를 계속 진행합니다.
    ) else (
        echo [INFO] insta_venv 가상환경이 없습니다. 새로 생성합니다...
        "%PYTHON_313%" -m venv "%INSTA_ENV_PATH%"
        if errorlevel 1 (
            echo [ERROR] insta_venv 생성 실패. Python 3.13 경로를 확인하세요.
            echo [INFO] 크롤링 기능을 사용할 수 없습니다. 스크립트를 계속 진행합니다.
        ) else (
            echo [INFO] insta_venv 생성 완료.

            echo [INFO] requirements_insta.txt 설치...
            call "%INSTA_ENV_PATH%\Scripts\activate.bat"
            "%INSTA_ENV_PATH%\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
            pip install -r %INSTA_REQ% >nul 2>&1
            if errorlevel 1 (
                echo [ERROR] insta_venv requirements 설치 실패.
                echo [INFO] 크롤링 기능을 사용할 수 없습니다. 스크립트를 계속 진행합니다.
            )
            call "%INSTA_ENV_PATH%\Scripts\deactivate.bat"
            echo [INFO] insta_venv 환경 세팅 완료.
        )
    )
)

echo.
echo ==============================================================================
echo 3) [분류용] classify_venv 환경 확인
echo ==============================================================================
if exist "%CLASSIFY_ENV_PATH%\Scripts\python.exe" (
    echo [INFO] classify_venv 이미 존재합니다.
    
    REM requirements 파일이 변경되었는지 확인
    set "CLASSIFY_REQ_CHECK_FILE=%CLASSIFY_ENV_PATH%\requirements_check.txt"
    set "CLASSIFY_UPDATE_NEEDED=0"
    
    if not exist "!CLASSIFY_REQ_CHECK_FILE!" (
        set "CLASSIFY_UPDATE_NEEDED=1"
        echo [INFO] 첫 실행이거나 requirements 체크 파일이 없습니다.
    ) else (
        fc /b "%CLASSIFY_REQ%" "!CLASSIFY_REQ_CHECK_FILE!" >nul 2>&1
        if errorlevel 1 (
            set "CLASSIFY_UPDATE_NEEDED=1"
            echo [INFO] requirements 파일이 변경되었습니다.
        )
    )
    
    if !CLASSIFY_UPDATE_NEEDED! == 1 (
        echo [INFO] requirements 업데이트 중...
        call "%CLASSIFY_ENV_PATH%\Scripts\activate.bat"
        
        REM 변경된 패키지만 재설치 (git 저장소의 경우)
        for /f "usebackq delims=" %%i in ("%CLASSIFY_REQ%") do (
            set "line=%%i"
            echo "!line!" | findstr /i "git+" >nul
            if !errorlevel! == 0 (
                echo [INFO] 재설치: !line!
                pip install "!line!" --force-reinstall --no-deps >nul 2>&1
            ) else (
                echo [INFO] 업데이트: !line!
                pip install "!line!" --upgrade >nul 2>&1
            )
        )
        
        if errorlevel 1 (
            echo [WARN] requirements 업데이트 중 일부 오류가 발생했습니다.
        ) else (
            echo [INFO] requirements 업데이트 완료.
            copy "%CLASSIFY_REQ%" "!CLASSIFY_REQ_CHECK_FILE!" >nul
        )
        call "%CLASSIFY_ENV_PATH%\Scripts\deactivate.bat"
    ) else (
        echo [INFO] requirements 변경사항 없음. 업데이트를 건너뜁니다.
    )
) else (
    if not defined PYTHON_310 (
        echo [WARN] Python 3.10 경로를 찾지 못했습니다. classify_venv를 생성할 수 없습니다.
        echo [INFO] 분류 기능은 사용할 수 없습니다.
    ) else (
        echo [INFO] classify_venv 가상환경이 없습니다. 새로 생성합니다...
        "%PYTHON_310%" -m venv "%CLASSIFY_ENV_PATH%"
        if errorlevel 1 (
            echo [ERROR] classify_venv 생성 실패. Python 3.10 경로를 확인하세요.
            echo [INFO] 분류 기능을 사용할 수 없습니다.
        ) else (
            echo [INFO] classify_venv 생성 완료.

            echo [INFO] requirements_classify.txt 설치...
            call "%CLASSIFY_ENV_PATH%\Scripts\activate.bat"
            "%CLASSIFY_ENV_PATH%\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
            pip install torch==2.0.1+cu118 torchvision==0.15.2+cu118 torchaudio==2.0.2+cu118 --index-url https://download.pytorch.org/whl/cu118 >nul 2>&1
            pip install -r %CLASSIFY_REQ% >nul 2>&1
            if errorlevel 1 (
                echo [ERROR] classify_venv requirements 설치 실패.
                echo [INFO] 분류 기능을 사용할 수 없습니다.
            )
            call "%CLASSIFY_ENV_PATH%\Scripts\deactivate.bat"
            echo [INFO] classify_venv 환경 세팅 완료.
        )
    )
)

echo.
echo ==============================================================================
echo 4) 인스타그램 이미지 크롤링 (GUI 실행)
echo ==============================================================================
if exist "%INSTA_ENV_PATH%\Scripts\python.exe" (
    echo [INFO] insta_venv 활성화 후 GUI 실행...
    call "%INSTA_ENV_PATH%\Scripts\activate.bat"
    python -m src.main
    call "%INSTA_ENV_PATH%\Scripts\deactivate.bat"
    echo [INFO] GUI가 정상적으로 종료되었습니다.
) else (
    echo [WARN] insta_venv가 없거나 생성 실패. 크롤링 기능을 사용할 수 없습니다.
    echo [ERROR] GUI를 실행할 수 없습니다.
    pause
    exit /b 1
)

echo.
echo ==============================================================================
echo 5) 분류는 GUI 내에서 옵션 선택 시 자동 실행
echo ==============================================================================
echo [INFO] 분류 단계는 classify_venv가 있어야 동작합니다. 
echo [INFO] 없는 경우, 분류 기능은 비활성화됩니다.

echo.
echo [INFO] === 전체 프로젝트 완료 ===
echo [INFO] GUI가 종료되었습니다. CMD 창도 자동으로 종료됩니다.
exit /b 0