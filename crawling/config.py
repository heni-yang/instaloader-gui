# crawling/config.py
import json
import os
from crawling.utils import create_dir_if_not_exists, logging

# 현재 스크립트 디렉토리 기준 설정 파일 경로
script_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(script_dir, 'config.json')
create_dir_if_not_exists(script_dir)

# 기본 설정 값
default_config = {
    'ACCOUNTS': [],
    'LAST_SEARCH_TYPE': 'hashtag',
    'SEARCH_TERMS': [],
    'INCLUDE_IMAGES': True,
    'INCLUDE_VIDEOS': False,
    'INCLUDE_REELS': False,
    'INCLUDE_HUMAN_CLASSIFY': False,
    'LOGIN_HISTORY': []
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
