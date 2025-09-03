# src/utils/config.py
import json
import os
from pathlib import Path
from .environment import Environment

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
    
    반환:
        dict: 설정 딕셔너리.
    """
    print("설정 파일 로드 시도...")
    config = default_config.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            config.update(data)
            print("설정 파일 로드 완료.")
        except Exception as e:
            print(f"설정 파일 로드 중 오류: {e}")
    else:
        print("설정 파일이 없습니다.")
    return config

def save_config(config):
    """
    설정 딕셔너리를 JSON 파일에 저장합니다.
    
    매개변수:
        config (dict): 저장할 설정 값.
    """
    print("설정 파일 저장 시도...")
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        print(f"설정이 {CONFIG_FILE}에 저장되었습니다.")
    except Exception as e:
        print(f"설정 저장 중 오류: {e}")
