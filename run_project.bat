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
    echo   경로 후보: %%~I
    REM 버전 확인을 위해 "--version" 실행
    for /f "tokens=*" %%V in ('"%%~I" --version 2^>^1') do (
        REM 예: "Python 3.10.11"
        echo       버전: %%V
        echo %%V | findstr /i "3.10" >nul
        if !errorlevel! == 0 (
            REM 아직 PYTHON_310이 비어있다면, 이 경로를 할당
            if not defined PYTHON_310 (
                set "PYTHON_310=%%~I"
                echo       --> PYTHON_310 = %%~I
            )
        )

        echo %%V | findstr /i "3.13" >nul
        if !errorlevel! == 0 (
            REM 아직 PYTHON_313이 비어있다면, 이 경로를 할당
            if not defined PYTHON_313 (
                set "PYTHON_313=%%~I"
                echo       --> PYTHON_313 = %%~I
            )
        )
    )
)

if not defined PYTHON_310 (
    echo [WARN] Python 3.10을 찾지 못했습니다. 3.10 관련 기능은 사용할 수 없습니다.
)
if not defined PYTHON_313 (
    echo [WARN] Python 3.13을 찾지 못했습니다. 3.13 관련 기능은 사용할 수 없습니다.
)

REM -----------------------------------------------------------------
REM (B) 기존 스크립트 로직: insta_venv / classify_venv 생성/설치/실행
REM -----------------------------------------------------------------
REM insta_venv 경로
set INSTA_ENV_PATH=crawling\insta_venv

REM classify_venv 경로
set CLASSIFY_ENV_PATH=crawling\classification\classify_venv

REM requirements (사용자 환경에 맞게 파일명 수정)
set INSTA_REQ=requirements_insta.txt
set CLASSIFY_REQ=requirements_classify.txt

echo.
echo ==============================================================================
echo 2) [크롤링용] insta_venv 환경 확인
echo ==============================================================================
if exist "%INSTA_ENV_PATH%\Scripts\python.exe" (
    echo [INFO] insta_venv 이미 존재합니다.
) else (
    if not defined PYTHON_313 (
        echo [ERROR] Python 3.13 경로를 찾을 수 없어 insta_venv를 생성할 수 없습니다.
        pause
        exit /b 1
    )
    echo [INFO] insta_venv 가상환경이 없습니다. 새로 생성합니다...
    "%PYTHON_313%" -m venv "%INSTA_ENV_PATH%"
    if errorlevel 1 (
        echo [ERROR] insta_venv 생성 실패. Python 3.13 경로를 확인하세요.
        pause
        exit /b 1
    )
    echo [INFO] insta_venv 생성 완료.

    echo [INFO] requirements_insta.txt 설치...
    call "%INSTA_ENV_PATH%\Scripts\activate.bat"
    pip install --upgrade pip
    pip install -r %INSTA_REQ%
    if errorlevel 1 (
        echo [ERROR] insta_venv requirements 설치 실패.
        pause
        exit /b 1
    )
    call "%INSTA_ENV_PATH%\Scripts\deactivate.bat"
    echo [INFO] insta_venv 환경 세팅 완료.
)

echo.
echo ==============================================================================
echo 3) [분류용] classify_venv 환경 확인
echo ==============================================================================
if exist "%CLASSIFY_ENV_PATH%\Scripts\python.exe" (
    echo [INFO] classify_venv 이미 존재합니다.
) else (
    if not defined PYTHON_310 (
        echo [ERROR] Python 3.10 경로를 찾을 수 없어 classify_venv를 생성할 수 없습니다.
        pause
        exit /b 1
    )
    echo [INFO] classify_venv 가상환경이 없습니다. 새로 생성합니다...
    "%PYTHON_310%" -m venv "%CLASSIFY_ENV_PATH%"
    if errorlevel 1 (
        echo [ERROR] classify_venv 생성 실패. Python 3.10 경로를 확인하세요.
        pause
        exit /b 1
    )
    echo [INFO] classify_venv 생성 완료.

    echo [INFO] requirements_classify.txt 설치...
    call "%CLASSIFY_ENV_PATH%\Scripts\activate.bat"
    pip install --upgrade pip
    pip install -r %CLASSIFY_REQ%
    if errorlevel 1 (
        echo [ERROR] classify_venv requirements 설치 실패.
        pause
        exit /b 1
    )
    call "%CLASSIFY_ENV_PATH%\Scripts\deactivate.bat"
    echo [INFO] classify_venv 환경 세팅 완료.
)

echo.
echo ==============================================================================
echo 4) 인스타그램 이미지 크롤링 (GUI 실행)
echo ==============================================================================
call "%INSTA_ENV_PATH%\Scripts\activate.bat"
echo [INFO] insta_venv 활성화 완료. (Python 3.13)
python -m crawling.main
call "%INSTA_ENV_PATH%\Scripts\deactivate.bat"

echo.
echo ==============================================================================
echo 5) 분류는 GUI 내에서 옵션 선택 시 자동 실행
echo ==============================================================================
echo [INFO] 분류 단계는 GUI 내에서 실행 여부를 선택할 수 있습니다.

echo.
echo [INFO] === 전체 프로젝트 완료 ===
pause
exit /b 0
