"""
로깅 시스템 모듈
애플리케이션의 로깅을 관리합니다.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from .environment import Environment


def setup_logger(name: str, log_file: Path = None, level: int = logging.INFO) -> logging.Logger:
    """
    로거 설정
    
    Args:
        name: 로거 이름
        log_file: 로그 파일 경로 (None이면 콘솔만 출력)
        level: 로그 레벨
    
    Returns:
        설정된 로거 객체
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 이미 핸들러가 설정되어 있으면 추가하지 않음
    if logger.handlers:
        return logger
    
    # 로그 포맷 설정
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 파일 핸들러 (지정된 경우)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_app_logger(name: str = "app") -> logging.Logger:
    """
    애플리케이션 로거 반환
    
    Args:
        name: 로거 이름
    
    Returns:
        애플리케이션 로거
    """
    log_file = Environment.get_log_file(name)
    return setup_logger(name, log_file)


def get_gui_logger() -> logging.Logger:
    """GUI 관련 로거 반환"""
    return get_app_logger("gui")


def get_downloader_logger() -> logging.Logger:
    """다운로더 관련 로거 반환"""
    return get_app_logger("downloader")


def get_processing_logger() -> logging.Logger:
    """후처리 관련 로거 반환"""
    return get_app_logger("processing")


# 기본 로거 설정
app_logger = get_app_logger()
