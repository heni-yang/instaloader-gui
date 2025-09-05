"""
환경 설정 및 경로 관리 모듈
애플리케이션의 기본 경로와 환경 설정을 관리합니다.
"""

import os
from pathlib import Path


class Environment:
    """애플리케이션 환경 설정 클래스"""
    
    # 프로젝트 루트 디렉토리
    BASE_DIR = Path(__file__).parent.parent.parent
    
    # 데이터 디렉토리들
    DATA_DIR = BASE_DIR / "data"
    CONFIG_DIR = DATA_DIR / "config"
    SESSIONS_DIR = DATA_DIR / "sessions"
    DOWNLOADS_DIR = DATA_DIR / "downloads"
    
    # 로그 디렉토리
    LOGS_DIR = BASE_DIR / "logs"
    
    # 모델 디렉토리
    MODELS_DIR = BASE_DIR / "models"
    
    # 설정 파일 경로들
    CONFIG_FILE = CONFIG_DIR / "config.json"
    STAMPS_FILE = CONFIG_DIR / "latest-stamps-images.ini"
    
    @classmethod
    def ensure_directories(cls):
        """필요한 디렉토리들이 존재하는지 확인하고 없으면 생성"""
        directories = [
            cls.DATA_DIR,
            cls.CONFIG_DIR,
            cls.SESSIONS_DIR,
            cls.DOWNLOADS_DIR,
            cls.LOGS_DIR,
            cls.MODELS_DIR
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def get_download_path(cls, username: str) -> Path:
        """사용자별 다운로드 경로 반환"""
        return cls.DOWNLOADS_DIR / username
    
    @classmethod
    def get_session_file(cls, username: str) -> Path:
        """사용자별 세션 파일 경로 반환"""
        return cls.SESSIONS_DIR / f"{username}.session"
    
    @classmethod
    def get_log_file(cls, name: str = "app") -> Path:
        """로그 파일 경로 반환"""
        return cls.LOGS_DIR / f"{name}.log"


# 환경 초기화
Environment.ensure_directories()
