# crawling/profile_manager.py
"""
Profile ID 기반으로 존재하지 않는 프로필을 관리하는 모듈
"""
import os
import configparser
from crawling.config import load_config, save_config

# latest-stamps-images.ini 파일 경로
STAMPS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "latest-stamps-images.ini")

def load_profile_ids_from_stamps():
    """
    latest-stamps-images.ini 파일에서 username과 profile-id 매핑을 로드합니다.
    
    반환:
        dict: {username: profile_id} 형태의 딕셔너리
    """
    profile_ids = {}
    
    if not os.path.exists(STAMPS_FILE):
        return profile_ids
    
    try:
        config = configparser.ConfigParser()
        config.read(STAMPS_FILE, encoding='utf-8')
        
        for section in config.sections():
            if config.has_option(section, 'profile-id'):
                profile_id = config.get(section, 'profile-id')
                profile_ids[section] = profile_id
                
    except Exception as e:
        print(f"Profile ID 로드 중 오류: {e}")
    
    return profile_ids

def get_profile_id_for_username(username):
    """
    특정 username의 profile-id를 반환합니다.
    
    매개변수:
        username (str): 사용자명
        
    반환:
        str: profile-id 또는 None
    """
    profile_ids = load_profile_ids_from_stamps()
    return profile_ids.get(username)

def add_non_existent_profile_id(profile_id, username=None):
    """
    존재하지 않는 profile-id를 설정에 추가합니다.
    
    매개변수:
        profile_id (str): 존재하지 않는 profile-id
        username (str, optional): 해당 profile-id의 username (참고용)
    """
    config = load_config()
    
    if 'NON_EXISTENT_PROFILE_IDS' not in config:
        config['NON_EXISTENT_PROFILE_IDS'] = []
    
    if profile_id not in config['NON_EXISTENT_PROFILE_IDS']:
        config['NON_EXISTENT_PROFILE_IDS'].append(profile_id)
        save_config(config)
        print(f"존재하지 않는 Profile ID '{profile_id}' (username: {username})을 설정에 저장했습니다.")

def is_profile_id_non_existent(profile_id):
    """
    특정 profile-id가 존재하지 않는 프로필 목록에 있는지 확인합니다.
    
    매개변수:
        profile_id (str): 확인할 profile-id
        
    반환:
        bool: 존재하지 않는 프로필이면 True
    """
    config = load_config()
    non_existent_ids = config.get('NON_EXISTENT_PROFILE_IDS', [])
    return profile_id in non_existent_ids

def get_non_existent_profile_ids():
    """
    존재하지 않는 profile-id 목록을 반환합니다.
    
    반환:
        list: 존재하지 않는 profile-id 목록
    """
    config = load_config()
    return config.get('NON_EXISTENT_PROFILE_IDS', [])

def remove_non_existent_profile_id(profile_id):
    """
    존재하지 않는 profile-id를 목록에서 제거합니다.
    
    매개변수:
        profile_id (str): 제거할 profile-id
    """
    config = load_config()
    
    if 'NON_EXISTENT_PROFILE_IDS' in config:
        if profile_id in config['NON_EXISTENT_PROFILE_IDS']:
            config['NON_EXISTENT_PROFILE_IDS'].remove(profile_id)
            save_config(config)
            print(f"Profile ID '{profile_id}'를 존재하지 않는 프로필 목록에서 제거했습니다.")

def clear_non_existent_profile_ids():
    """
    존재하지 않는 profile-id 목록을 모두 제거합니다.
    """
    config = load_config()
    config['NON_EXISTENT_PROFILE_IDS'] = []
    save_config(config)
    print("모든 존재하지 않는 Profile ID 목록을 제거했습니다.")

def get_username_by_profile_id(profile_id):
    """
    profile-id로 username을 찾습니다.
    
    매개변수:
        profile_id (str): 찾을 profile-id
        
    반환:
        str: username 또는 None
    """
    profile_ids = load_profile_ids_from_stamps()
    
    for username, pid in profile_ids.items():
        if pid == profile_id:
            return username
    
    return None
