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
        # 로그 디렉토리 생성
        log_file.parent.mkdir(parents=True, exist_ok=True)
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


def get_daily_logger(name: str = "daily") -> logging.Logger:
    """
    날짜별 로그 파일을 생성하는 로거 반환
    
    Args:
        name: 로거 이름
    
    Returns:
        날짜별 로그 파일 로거
    """
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = Environment.LOGS_DIR / f"{name}_{today}.log"
    return setup_logger(f"{name}_{today}", log_file)


def log_download_failure(username: str, search_term: str, error_type: str, error_message: str, 
                        search_type: str = "unknown", account_used: str = None) -> None:
    """
    다운로드 실패 로그를 기록합니다.
    
    Args:
        username: 실패한 사용자 ID
        search_term: 검색어/대상
        error_type: 오류 유형 (예: "로그인 실패", "프로필 없음", "비공개 프로필", "네트워크 오류" 등)
        error_message: 상세 오류 메시지
        search_type: 검색 유형 (hashtag, user, location 등)
        account_used: 사용된 계정 (마스킹됨)
    """
    logger = get_daily_logger("download_failures")
    
    # 계정 정보 마스킹
    if account_used:
        from .secure_logging import mask_username
        masked_account = mask_username(account_used)
    else:
        masked_account = "unknown"
    
    # 간결한 로그 메시지
    log_message = f"FAILURE | User: {username} | Term: {search_term} | Type: {search_type} | Error: {error_type} | Account: {masked_account} | Details: {error_message}"
    
    logger.error(log_message)


def log_download_success(username: str, search_term: str, search_type: str = "unknown", 
                        account_used: str = None, download_count: int = 0) -> None:
    """
    다운로드 성공 로그를 기록합니다.
    
    Args:
        username: 성공한 사용자 ID
        search_term: 검색어/대상
        search_type: 검색 유형 (hashtag, user, location 등)
        account_used: 사용된 계정 (마스킹됨)
        download_count: 다운로드된 게시물 수
    """
    logger = get_daily_logger("download_success")
    
    # 계정 정보 마스킹
    if account_used:
        from .secure_logging import mask_username
        masked_account = mask_username(account_used)
    else:
        masked_account = "unknown"
    
    # 간결한 로그 메시지
    log_message = f"SUCCESS | User: {username} | Term: {search_term} | Type: {search_type} | Account: {masked_account} | Count: {download_count}"
    
    logger.info(log_message)


def log_account_switch(from_account: str, to_account: str, reason: str = "unknown") -> None:
    """
    계정 전환 로그를 기록합니다.
    
    Args:
        from_account: 이전 계정 (마스킹됨)
        to_account: 새 계정 (마스킹됨)
        reason: 전환 이유
    """
    logger = get_daily_logger("account_switches")
    
    # 계정 정보 마스킹
    from .secure_logging import mask_username
    masked_from = mask_username(from_account)
    masked_to = mask_username(to_account)
    
    # 간결한 로그 메시지
    log_message = f"SWITCH | From: {masked_from} | To: {masked_to} | Reason: {reason}"
    
    logger.warning(log_message)


# 기본 로거 설정
app_logger = get_app_logger()
