# src/utils/config.py
import json
import os
import logging
from pathlib import Path
from .environment import Environment
from .security import get_password_manager, SecurityError

logger = logging.getLogger(__name__)

# 설정 파일 경로
CONFIG_FILE = Environment.CONFIG_FILE
Environment.ensure_directories()

# 기본 설정 값
default_config = {
    'ACCOUNTS': [],
    'LAST_SEARCH_TYPE': 'hashtag',
    'LAST_DOWNLOAD_PATH': '',
    'REQUEST_WAIT_TIME': 0.0,
    'HASHTAG_OPTIONS': {
        'include_images': True,
        'include_videos': False,
        'include_human_classify': False,
        'include_upscale': False
    },
    'USER_ID_OPTIONS': {
        'include_images': True,
        'include_reels': False,
        'include_human_classify': False,
        'include_upscale': False
    },
    'ALLOW_DUPLICATE': False,
    'SEARCH_TERMS': [],
    'INCLUDE_IMAGES': True,
    'INCLUDE_VIDEOS': False,
    'INCLUDE_REELS': False,
    'INCLUDE_HUMAN_CLASSIFY': False,
    'INCLUDE_UPSCALE': False,
    'LOGIN_HISTORY': [],
    'LAST_ACCOUNT_USED': None,
    'NON_EXISTENT_PROFILES': [],
    'NON_EXISTENT_PROFILE_IDS': [],
    'DOWNLOAD_HISTORY': [],
    'ERROR_LOG': [],
    'SETTINGS': {
        'max_retries': 3,
        'timeout': 30,
        'max_concurrent_downloads': 1
    }
}

def load_config():
    """
    설정 파일을 로드하여 기본 설정과 병합한 후 반환합니다.
    비밀번호는 자동으로 복호화됩니다.
    
    반환:
        dict: 설정 딕셔너리.
    """
    logger.info("설정 파일 로드 시도...")
    config = default_config.copy()
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            config.update(data)
            
            # 비밀번호 복호화
            config = _decrypt_passwords_in_config(config)
            
            logger.info("설정 파일 로드 완료.")
        except Exception as e:
            logger.error(f"설정 파일 로드 중 오류: {e}")
            print(f"설정 파일 로드 중 오류: {e}")
    else:
        logger.info("설정 파일이 없습니다.")
        print("설정 파일이 없습니다.")
    
    return config

def save_config(config):
    """
    설정 딕셔너리를 JSON 파일에 저장합니다.
    비밀번호는 자동으로 암호화됩니다.
    
    매개변수:
        config (dict): 저장할 설정 값.
    """
    logger.info("설정 파일 저장 시도...")
    try:
        # 비밀번호 암호화
        encrypted_config = _encrypt_passwords_in_config(config.copy())
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(encrypted_config, f, ensure_ascii=False, indent=4)
        
        logger.info(f"설정이 {CONFIG_FILE}에 저장되었습니다.")
        print(f"설정이 {CONFIG_FILE}에 저장되었습니다.")
    except Exception as e:
        logger.error(f"설정 파일 저장 중 오류: {e}")
        print(f"설정 파일 저장 중 오류: {e}")


def _encrypt_passwords_in_config(config):
    """설정 딕셔너리 내의 모든 비밀번호를 암호화합니다."""
    try:
        password_manager = get_password_manager()
        
        # LOGIN_HISTORY의 비밀번호 암호화
        if 'LOGIN_HISTORY' in config:
            for history_item in config['LOGIN_HISTORY']:
                if 'password' in history_item:
                    password = history_item['password']
                    if password and not password_manager.is_encrypted(password):
                        history_item['password'] = password_manager.encrypt_password(password)
        
        # ACCOUNTS의 비밀번호 암호화
        if 'ACCOUNTS' in config:
            for account in config['ACCOUNTS']:
                if isinstance(account, dict) and 'INSTAGRAM_PASSWORD' in account:
                    password = account['INSTAGRAM_PASSWORD']
                    if password and not password_manager.is_encrypted(password):
                        account['INSTAGRAM_PASSWORD'] = password_manager.encrypt_password(password)
        
        logger.debug("설정 내 비밀번호 암호화 완료")
        return config
    except SecurityError as e:
        logger.error(f"비밀번호 암호화 실패: {e}")
        # 암호화 실패 시 원본 반환 (하위 호환성)
        return config
    except Exception as e:
        logger.error(f"설정 암호화 중 예외: {e}")
        return config


def _decrypt_passwords_in_config(config):
    """설정 딕셔너리 내의 모든 비밀번호를 복호화합니다."""
    try:
        password_manager = get_password_manager()
        
        # LOGIN_HISTORY의 비밀번호 복호화
        if 'LOGIN_HISTORY' in config:
            for history_item in config['LOGIN_HISTORY']:
                if 'password' in history_item:
                    encrypted_password = history_item['password']
                    if encrypted_password:
                        history_item['password'] = password_manager.decrypt_password(encrypted_password)
        
        # ACCOUNTS의 비밀번호 복호화
        if 'ACCOUNTS' in config:
            for account in config['ACCOUNTS']:
                if isinstance(account, dict) and 'INSTAGRAM_PASSWORD' in account:
                    encrypted_password = account['INSTAGRAM_PASSWORD']
                    if encrypted_password:
                        account['INSTAGRAM_PASSWORD'] = password_manager.decrypt_password(encrypted_password)
        
        logger.debug("설정 내 비밀번호 복호화 완료")
        return config
    except SecurityError as e:
        logger.error(f"비밀번호 복호화 실패: {e}")
        # 복호화 실패 시 원본 반환 (하위 호환성)
        return config
    except Exception as e:
        logger.error(f"설정 복호화 중 예외: {e}")
        return config


def migrate_config_passwords():
    """기존 설정 파일의 평문 비밀번호를 암호화된 형태로 마이그레이션합니다."""
    try:
        logger.info("비밀번호 마이그레이션 시작...")
        
        if not os.path.exists(CONFIG_FILE):
            logger.info("설정 파일이 없어 마이그레이션을 건너뜁니다.")
            return True
        
        # 원본 설정 파일 백업
        backup_file = f"{CONFIG_FILE}.backup"
        if not os.path.exists(backup_file):
            import shutil
            shutil.copy2(CONFIG_FILE, backup_file)
            logger.info(f"설정 파일 백업 생성: {backup_file}")
        
        # 설정 로드 (이미 복호화된 상태)
        config = load_config()
        
        # 설정 저장 (자동으로 암호화됨)
        save_config(config)
        
        logger.info("비밀번호 마이그레이션 완료")
        print("기존 비밀번호가 안전하게 암호화되었습니다.")
        return True
        
    except Exception as e:
        logger.error(f"비밀번호 마이그레이션 실패: {e}")
        print(f"비밀번호 마이그레이션 실패: {e}")
        return False
