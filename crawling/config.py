import json
import os

# 현재 스크립트(config.py)가 위치한 디렉토리
script_dir = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(script_dir, 'config.json')

# 기본 설정 딕셔너리
default_config = {
    'ACCOUNTS': [],
    'LAST_SEARCH_TYPE': 'hashtag',
    'SEARCH_TERMS': [],
    'INCLUDE_IMAGES': True,
    'INCLUDE_VIDEOS': False,
    'INCLUDE_REELS': False,
    'INCLUDE_HUMAN_CLASSIFY': False,
    # 새 항목 추가
    'LOGIN_HISTORY': []
}


def load_config():
    print("설정 파일 로드 시도...")
    config = default_config.copy()  # 기본값 복사
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 기본값 위에 저장된 설정을 덮어씌웁니다.
            config.update(data)
            print("설정 파일 로드 완료.")
        except Exception as e:
            print(f"설정 파일을 불러오는 중 에러 발생: {e}")
    else:
        print("설정 파일이 없습니다.")
    return config

def save_config(config):
    print("설정 파일 저장 시도...")
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        print(f"설정이 {CONFIG_FILE}에 안전하게 저장되었습니다.")
    except Exception as e:
        print(f"설정을 저장하는 중 에러 발생: {e}")
