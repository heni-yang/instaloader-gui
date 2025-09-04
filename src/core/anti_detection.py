"""
Anti-Detection 모드 설정 관리 모듈

OFF/FAST/ON/SAFE 4단계 모드별 anti-detection 설정을 정의하고 관리합니다.
"""

def get_anti_detection_settings(mode):
    """
    Anti-Detection 모드별 설정 반환
    
    Args:
        mode (str): Anti-detection 모드 ("OFF", "FAST", "ON", "SAFE")
        
    Returns:
        dict: 모드별 설정 딕셔너리
    """
    settings = {
        "OFF": {
            "human_behavior_enabled": False,
            "additional_wait_time": 0.0,
            "description": "⚡ 즉시 실행 (위험도: 매우 높음)",
            "use_case": "소량 프로필, 빠른 테스트",
            "display_name": "🚫 OFF (즉시 실행)"
        },
        "FAST": {
            "human_behavior_enabled": True,
            "rate_config": "ultra_fast",  # ON 모드 대비 50% 더 완화
            "additional_wait_time": 0.0,
            "description": "🚀 고속 크롤링 (위험도: 높음)",
            "use_case": "빠른 크롤링, 중소량 프로필",
            "display_name": "🚀 FAST (고속)"
        },
        "ON": {
            "human_behavior_enabled": True,
            "rate_config": "balanced",  # instaloader_heni 완화된 설정
            "additional_wait_time": 0.0,
            "description": "⚖️ 균형잡힌 속도와 안전성 (권장)",
            "use_case": "일반적인 사용, 중간 규모",
            "display_name": "⚖️ ON (권장)"
        },
        "SAFE": {
            "human_behavior_enabled": True,
            "rate_config": "conservative",  # 수정 전 보수적 설정
            "additional_wait_time": 0.5,
            "description": "🛡️ 안전한 대량 다운로드",
            "use_case": "대량 프로필, 장시간 작업",
            "display_name": "🛡️ SAFE (대량/장시간)"
        }
    }
    return settings.get(mode, settings["ON"])  # 기본값은 ON


def get_mode_display_values():
    """GUI 드롭다운에 표시할 모드 리스트 반환"""
    modes = ["OFF", "FAST", "ON", "SAFE"]
    return [get_anti_detection_settings(mode)["display_name"] for mode in modes]


def get_mode_from_display_value(display_value):
    """표시 값에서 실제 모드 키 반환"""
    mode_map = {
        "🚫 OFF (즉시 실행)": "OFF",
        "🚀 FAST (고속)": "FAST",
        "⚖️ ON (권장)": "ON",
        "🛡️ SAFE (대량/장시간)": "SAFE"
    }
    return mode_map.get(display_value, "ON")


def get_display_value_from_mode(mode):
    """모드 키에서 표시 값 반환"""
    return get_anti_detection_settings(mode)["display_name"]


def migrate_old_config(config):
    """
    기존 REQUEST_WAIT_TIME을 ANTI_DETECTION_MODE로 변환
    
    Args:
        config (dict): 기존 설정 딕셔너리
        
    Returns:
        dict: 마이그레이션된 설정 딕셔너리
    """
    if 'ANTI_DETECTION_MODE' not in config and 'REQUEST_WAIT_TIME' in config:
        wait_time = config.get('REQUEST_WAIT_TIME', 0.0)
        
        # 더 세밀한 4단계 분류
        if wait_time == 0.0:
            # 기존 0.0초 사용자는 ON 모드 (균형)
            config['ANTI_DETECTION_MODE'] = 'ON'
        elif 0.0 < wait_time < 0.3:
            # 소량의 추가 대기시간은 FAST 모드
            config['ANTI_DETECTION_MODE'] = 'FAST'
        elif 0.3 <= wait_time < 1.0:
            # 중간 수준의 대기시간은 ON 모드
            config['ANTI_DETECTION_MODE'] = 'ON'
        else:
            # 1.0초 이상은 SAFE 모드
            config['ANTI_DETECTION_MODE'] = 'SAFE'
    
    # 기본값 설정 (신규 사용자는 ON 모드)
    if 'ANTI_DETECTION_MODE' not in config:
        config['ANTI_DETECTION_MODE'] = 'ON'
    
    return config