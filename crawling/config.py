import json
import os

# 현재 스크립트(config.py)가 위치한 디렉토리
script_dir = os.path.dirname(os.path.abspath(__file__))

# config.json 파일의 절대 경로
CONFIG_FILE = os.path.join(script_dir, 'config.json')

def load_config():
    print("설정 파일 로드 시도...")
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                accounts = data.get('ACCOUNTS', [])
                last_search_type = data.get('LAST_SEARCH_TYPE', 'hashtag')
                search_terms = data.get('SEARCH_TERMS', [])
                include_images = data.get('INCLUDE_IMAGES', True)
                include_videos = data.get('INCLUDE_VIDEOS', False)
                include_reels = data.get('INCLUDE_REELS', False)
                print("설정 파일 로드 완료.")
                return accounts, last_search_type, search_terms, include_images, include_videos, include_reels
        except Exception as e:
            print(f"설정 파일을 불러오는 중 에러 발생: {e}")
            return [], 'hashtag', [], True, False, False
    print("설정 파일이 없습니다.")
    return [], 'hashtag', [], True, False, False

def save_config(accounts, search_type, search_terms, include_images, include_videos, include_reels):
    print("설정 파일 저장 시도...")
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'ACCOUNTS': accounts,
                'LAST_SEARCH_TYPE': search_type,
                'SEARCH_TERMS': search_terms,
                'INCLUDE_IMAGES': include_images,
                'INCLUDE_VIDEOS': include_videos,
                'INCLUDE_REELS': include_reels
            }, f, ensure_ascii=False, indent=4)
        print(f"설정이 {CONFIG_FILE}에 안전하게 저장되었습니다.")
    except Exception as e:
        print(f"설정을 저장하는 중 에러 발생: {e}")