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
    'SEARCH_TERMS': [],
    'INCLUDE_IMAGES': True,
    'INCLUDE_VIDEOS': False,
    'INCLUDE_REELS': False,
    'INCLUDE_HUMAN_CLASSIFY': False,
    'LOGIN_HISTORY': [],
    'LAST_DOWNLOAD_PATH': str(Environment.DOWNLOADS_DIR),
    'NON_EXISTENT_PROFILES': [],  # 존재하지 않는 프로필 목록 (username 기반, 하위 호환성)
    'NON_EXISTENT_PROFILE_IDS': [],  # 존재하지 않는 프로필 ID 목록 (profile-id 기반)
    'RATE_LIMIT_MIN_SLEEP': 3.0,  # 최소 대기 시간 (초)
    'RATE_LIMIT_MAX_SLEEP': 10.0,  # 최대 대기 시간 (초)
    'RATE_LIMIT_MULTIPLIER': 1.5   # 대기 시간 배수
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
