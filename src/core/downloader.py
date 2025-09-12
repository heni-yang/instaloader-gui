# src/core/downloader.py
import os
import instaloader
from instaloader import Profile, LatestStamps, RateController, exceptions
import time
from itertools import islice
from ..utils.secure_logging import (
    safe_print, safe_error, safe_debug,
    print_login_success, print_login_failure, print_session_loaded,
    print_account_switch, print_debug_rate_controller
)
from ..utils.logger import log_download_failure, log_download_success, log_account_switch

# 커스텀 RateController 클래스 (모드별 anti-detection 제어)
class CustomRateController(RateController):
    def __init__(self, context, additional_wait_time=0.0, anti_detection_mode="ON"):
        from .anti_detection import get_anti_detection_settings
        from ..utils.config import load_config
        
        super().__init__(context)
        self.additional_wait_time = additional_wait_time
        self.anti_detection_mode = anti_detection_mode
        
        # 모드별 설정 가져오기
        settings = get_anti_detection_settings(anti_detection_mode)
        self._human_behavior_enabled = settings['human_behavior_enabled']
        
        # 리셋시간 설정 로드 (GUI에서 설정한 값)
        config = load_config()
        self.reset_interval = config.get('ANTI_DETECTION_RESET_INTERVAL', 6) * 3600  # 시간을 초로 변환
        self.start_time = time.time()  # 크롤링 시작 시간
        self.last_reset_time = self.start_time  # 마지막 리셋 시간
        self.reset_count = 0  # 리셋 횟수 추적
        
        # 동적 조절 시스템 초기화
        self.dynamic_adjustment_enabled = True
        self.last_adjustment_time = time.time()
        self.adjustment_interval = 60  # 1분마다 조절 (더 빠른 대응)
        self.original_additional_wait_time = additional_wait_time
        self.current_adjustment_factor = 1.0
        
        # 모드별 설정 적용
        if anti_detection_mode == "FAST":
            self._apply_ultra_fast_settings()
        elif anti_detection_mode == "SAFE":
            self._apply_conservative_settings()
        elif anti_detection_mode == "ON":
            self._apply_on_mode_settings()
        # OFF 모드는 기본 설정 사용
        
        safe_debug(f"[ANTI-DETECTION] 모드: {anti_detection_mode}")
        safe_debug(f"[ANTI-DETECTION] Human behavior: {self._human_behavior_enabled}")
        safe_debug(f"[ANTI-DETECTION] 추가 대기: {self.additional_wait_time}초")
        safe_debug(f"[ANTI-DETECTION] 리셋 주기: {self.reset_interval/3600}시간")
        safe_debug(f"[ANTI-DETECTION] 시작시간: {datetime.fromtimestamp(self.start_time)}")
        
        # 요청 추적을 위한 타임스탬프 리스트 초기화
        self._request_timestamps = []
        
        # 이전 요청 수 정보 복원 (크롤링 재시작 시)
        self._restore_request_history()
        
        # 보안모드가 활성화된 경우에만 초기화 주기 정보 표시
        if self._human_behavior_enabled:
            print(f"🛡️  [ANTI-DETECTION] 설정 초기화 주기: {self.reset_interval/3600}시간")
            print(f"⏰ [ANTI-DETECTION] 다음 초기화까지: {self.reset_interval/3600}시간")
            print(f"⚡ [DYNAMIC] 동적 대기시간 조절 활성화됨")
    
    def _apply_ultra_fast_settings(self):
        """FAST 모드를 위한 초고속 설정 적용 (ON 모드(기본값) 대비 50% 더 완화)"""
        # ON 모드(instaloader_heni 기본값) 대비 50% 더 완화
        self._consecutive_penalty_factor = 0.05     # 0.1 → 0.05 (50% 감소)
        self._peak_hours_multiplier = 1.05         # 1.1 → 1.05 (더 완화)
        self._break_threshold_time = 18000         # 120분 → 180분 (50% 증가)
        self._break_threshold_requests = 300       # 200 → 300 (50% 증가)
        self._min_break_time = 5                   # 10초 → 5초 (50% 감소)
        self._max_break_time = 30                  # 60초 → 30초 (50% 감소)
        
        # FAST 모드 기본 추가 대기시간 설정 (동적 조절의 기준점)
        if self.original_additional_wait_time == 0.0:
            self.original_additional_wait_time = 1.0  # 1.0초 기본값 (가장 빠른 속도)
            self.additional_wait_time = self.original_additional_wait_time
        
        safe_debug("[ANTI-DETECTION] FAST 모드: 초고속 설정 적용됨")
    
    def _apply_conservative_settings(self):
        """SAFE 모드를 위한 보수적 설정 적용 (ON 모드(기본값) 대비 보수적)"""
        # ON 모드(instaloader_heni 기본값) 대비 보수적 설정
        self._consecutive_penalty_factor = 0.2   # 0.1 → 0.2 (2배 증가)
        self._peak_hours_multiplier = 1.3       # 1.1 → 1.3 (더 보수적)
        self._break_threshold_time = 3600       # 120분 → 60분 (50% 감소)
        self._break_threshold_requests = 100    # 200 → 100 (50% 감소)
        self._min_break_time = 20               # 10초 → 20초 (2배 증가)
        self._max_break_time = 120              # 60초 → 120초 (2배 증가)
        
        # SAFE 모드 기본 추가 대기시간 설정 (동적 조절의 기준점)
        if self.original_additional_wait_time == 0.0:
            self.original_additional_wait_time = 1.5  # 1.5초 기본값 (가장 보수적)
            self.additional_wait_time = self.original_additional_wait_time
        
        safe_debug("[ANTI-DETECTION] SAFE 모드: 보수적 설정 적용됨")
    
    def _apply_on_mode_settings(self):
        """ON 모드를 위한 설정 적용 (기본값 + 동적 조절)"""
        # ON 모드는 기본 설정 유지하되 동적 조절 기능 추가
        # 기본 추가 대기시간 설정 (동적 조절의 기준점)
        if self.original_additional_wait_time == 0.0:
            self.original_additional_wait_time = 1.25  # 1.25초 기본값 (중간 속도)
            self.additional_wait_time = self.original_additional_wait_time
        
        safe_debug("[ANTI-DETECTION] ON 모드: 기본 설정 + 동적 조절 활성화")
    
    def _restore_request_history(self):
        """이전 요청 수 정보를 config에서 복원"""
        try:
            from ..utils.config import load_config, save_config
            config = load_config()
            
            # 요청 수 정보가 저장되어 있는지 확인
            if 'REQUEST_HISTORY' in config:
                request_history = config['REQUEST_HISTORY']
                current_time = time.time()
                
                # 저장된 타임스탬프들을 복원 (2시간 이내의 것만)
                cutoff_time = current_time - 7200  # 2시간
                restored_timestamps = []
                
                for timestamp in request_history.get('timestamps', []):
                    if timestamp >= cutoff_time:
                        restored_timestamps.append(timestamp)
                
                self._request_timestamps = restored_timestamps
                
                # 복원된 요청 수 로그
                if restored_timestamps:
                    recent_10min = len([ts for ts in restored_timestamps if ts >= current_time - 600])
                    recent_60min = len([ts for ts in restored_timestamps if ts >= current_time - 3600])
                    print(f"🔄 [RESTORE] 이전 요청 수 복원: 최근 10분 {recent_10min}회, 최근 60분 {recent_60min}회")
                else:
                    print(f"🔄 [RESTORE] 복원할 요청 수 정보 없음 (2시간 이내 데이터 없음)")
                    
        except Exception as e:
            safe_debug(f"[RESTORE] 요청 수 복원 실패: {e}")
    
    def _save_request_history(self):
        """현재 요청 수 정보를 config에 저장"""
        try:
            from ..utils.config import load_config, save_config
            config = load_config()
            
            # 현재 타임스탬프들을 저장 (2시간 이내의 것만)
            current_time = time.time()
            cutoff_time = current_time - 7200  # 2시간
            recent_timestamps = [ts for ts in self._request_timestamps if ts >= cutoff_time]
            
            config['REQUEST_HISTORY'] = {
                'timestamps': recent_timestamps,
                'last_save_time': current_time
            }
            
            save_config(config)
            safe_debug(f"[SAVE] 요청 수 정보 저장: {len(recent_timestamps)}개 타임스탬프")
            
        except Exception as e:
            safe_debug(f"[SAVE] 요청 수 저장 실패: {e}")
    
    def _save_request_history_silent(self):
        """현재 요청 수 정보를 config에 저장 (로그 없이)"""
        try:
            from ..utils.config import load_config, save_config
            config = load_config()
            
            # 현재 타임스탬프들을 저장 (2시간 이내의 것만)
            current_time = time.time()
            cutoff_time = current_time - 7200  # 2시간
            recent_timestamps = [ts for ts in self._request_timestamps if ts >= cutoff_time]
            
            config['REQUEST_HISTORY'] = {
                'timestamps': recent_timestamps,
                'last_save_time': current_time
            }
            
            save_config(config)
            # 저장 로그는 출력하지 않음
            
        except Exception as e:
            safe_debug(f"[SAVE] 요청 수 저장 실패: {e}")
    
    def count_per_sliding_window(self, query_type: str) -> int:
        """모드별 rate limiting 적용"""
        if self.anti_detection_mode == "FAST":
            return 150 if query_type == 'other' else 400  # ON 모드 대비 50% 증가
        elif self.anti_detection_mode == "SAFE":
            return 75 if query_type == 'other' else 200   # 보수적 설정
        else:
            return super().count_per_sliding_window(query_type)  # ON 모드는 instaloader_heni 기본값 사용
    
    def _check_and_reset_if_needed(self):
        """설정된 시간마다 설정 초기화 확인"""
        current_time = time.time()
        time_since_last_reset = current_time - self.last_reset_time
        
        # 보안모드가 활성화된 경우에만 초기화까지 남은 시간 계산 및 표시
        if self._human_behavior_enabled:
            remaining_time = self.reset_interval - time_since_last_reset
            if remaining_time > 0:
                remaining_hours = int(remaining_time // 3600)
                remaining_minutes = int((remaining_time % 3600) // 60)
                print(f"⏰ [ANTI-DETECTION] 초기화까지 {remaining_hours}시간 {remaining_minutes}분 남음")
                
                # 요청 수 모니터링 로그 추가 및 저장
                recent_10min_requests = self._calculate_recent_requests(600)  # 10분
                recent_60min_requests = self._calculate_recent_requests(3600)  # 60분
                print(f"📊 [MONITOR] 최근 10분 요청: {recent_10min_requests}회, 최근 60분 요청: {recent_60min_requests}회")
                
                # 모니터링 로그 표시 시마다 요청 수 정보 저장 (저장 로그는 숨김)
                self._save_request_history_silent()
        
        if time_since_last_reset >= self.reset_interval:
            self._reset_anti_detection_settings()
            self.last_reset_time = current_time
            self.reset_count += 1
            
            # 보안모드가 활성화된 경우에만 리셋 로깅 표시
            if self._human_behavior_enabled:
                elapsed_hours = int(time_since_last_reset // 3600)
                elapsed_minutes = int((time_since_last_reset % 3600) // 60)
                reset_interval_hours = int(self.reset_interval // 3600)
                print(f"🔄 [ANTI-DETECTION] {reset_interval_hours}시간 경과로 설정 초기화됨")
                print(f"⏱️  [ANTI-DETECTION] 경과시간: {elapsed_hours}시간 {elapsed_minutes}분")
                print(f"🔢 [ANTI-DETECTION] 리셋 횟수: {self.reset_count}회")
    
    def _reset_anti_detection_settings(self):
        """anti-detection 설정을 초기 상태로 리셋"""
        
        # 1. 모드별 설정 재적용
        if self.anti_detection_mode == "FAST":
            self._apply_ultra_fast_settings()
        elif self.anti_detection_mode == "SAFE":
            self._apply_conservative_settings()
        # ON/OFF 모드는 기본 설정 유지
        
        # 2. RateController 내부 상태 완전 초기화
        self._reset_internal_state()
        
        # 3. 시간 기반 카운터 리셋
        self._reset_time_based_counters()
        
        # 4. 동적 조절 시스템 초기화
        self._reset_dynamic_adjustment()
        
        safe_debug(f"[ANTI-DETECTION] 설정 초기화 완료 - 모드: {self.anti_detection_mode}")
    
    def _reset_internal_state(self):
        """RateController 내부 상태 초기화"""
        
        # 연속 요청 관련 상태 리셋
        self._consecutive_requests = 0
        self._consecutive_penalty = 0
        
        # 시간 기반 카운터 리셋
        self._request_timestamps = []
        self._hourly_request_count = {}
        
        # 패널티 상태 리셋
        self._current_penalty = 0
        self._peak_hours_penalty = 0
        
        # 브레이크 관련 상태 리셋
        self._last_break_time = 0
        self._break_duration = 0
        
        safe_debug("[ANTI-DETECTION] 내부 상태 초기화 완료")
    
    def _reset_time_based_counters(self):
        """시간 기반 카운터 리셋"""
        # 시간 기반 카운터들을 초기화
        if hasattr(self, '_hourly_request_count'):
            self._hourly_request_count.clear()
        if hasattr(self, '_request_timestamps'):
            self._request_timestamps.clear()
        
        safe_debug("[ANTI-DETECTION] 시간 기반 카운터 초기화 완료")
    

    def _reset_dynamic_adjustment(self):
        """동적 조절 시스템 초기화"""
        self.current_adjustment_factor = 1.0
        self.additional_wait_time = self.original_additional_wait_time
        self.last_adjustment_time = time.time()
        safe_debug("[DYNAMIC] 동적 조절 시스템 초기화 완료")
    
    def _get_request_thresholds(self):
        """모드별 요청 수 임계값 반환"""
        thresholds = {
            "FAST": {
                "high": 100,    # 1시간에 100회 이상 시 대기시간 크게 증가 (더 관대함)
                "medium": 70,   # 1시간에 70회 이상 시 대기시간 증가
                "low": 40,      # 1시간에 40회 미만 시 대기시간 감소
                "very_low": 20  # 1시간에 20회 미만 시 대기시간 크게 감소
            },
            "ON": {
                "high": 80,     # 1시간에 80회 이상 시 대기시간 크게 증가
                "medium": 50,   # 1시간에 50회 이상 시 대기시간 증가
                "low": 30,      # 1시간에 30회 미만 시 대기시간 감소
                "very_low": 15  # 1시간에 15회 미만 시 대기시간 크게 감소
            },
            "SAFE": {
                "high": 50,     # 1시간에 50회 이상 시 대기시간 크게 증가 (가장 보수적)
                "medium": 30,   # 1시간에 30회 이상 시 대기시간 증가
                "low": 20,      # 1시간에 20회 미만 시 대기시간 감소
                "very_low": 10  # 1시간에 10회 미만 시 대기시간 크게 감소
            }
        }
        return thresholds.get(self.anti_detection_mode, thresholds["ON"])
    
    def _calculate_recent_requests(self, time_window=3600):
        """최근 지정된 시간(초) 내 요청 수 계산"""
        current_time = time.time()
        cutoff_time = current_time - time_window
        
        if hasattr(self, '_request_timestamps'):
            return len([ts for ts in self._request_timestamps if ts >= cutoff_time])
        return 0
    
    def _check_and_adjust_dynamically(self):
        """동적 대기시간 조절 체크 및 실행"""
        if not self.dynamic_adjustment_enabled or not self._human_behavior_enabled:
            return
        
        current_time = time.time()
        
        # 실시간 모니터링: 10분 기준 점진적 조절 (모드별 임계값)
        recent_10min_requests = self._calculate_recent_requests(600)  # 10분
        realtime_thresholds = {
            "FAST": 20,   # 10분에 20회 (1시간에 120회)
            "ON": 15,     # 10분에 15회 (1시간에 90회)  
            "SAFE": 10    # 10분에 10회 (1시간에 60회)
        }
        threshold = realtime_thresholds.get(self.anti_detection_mode, 25)
        
        # 점진적 조절 시스템
        if recent_10min_requests > threshold:
            # 임계값 초과 정도에 따른 점진적 조절
            excess_ratio = recent_10min_requests / threshold
            
            # 모든 모드 동일한 조절 계수 사용
            if excess_ratio >= 2.0:  # 2배 이상 초과
                new_factor = 8.0  # 700% 증가
                status = "극도로 높음"
            elif excess_ratio >= 1.5:  # 1.5배 이상 초과
                new_factor = 5.0  # 400% 증가
                status = "매우 높음"
            elif excess_ratio >= 1.2:  # 1.2배 이상 초과
                new_factor = 3.0  # 200% 증가
                status = "높음"
            else:  # 임계값 초과
                new_factor = 2.0  # 100% 증가
                status = "보통"
            
            # 조절 계수 업데이트
            old_factor = self.current_adjustment_factor
            self.current_adjustment_factor = new_factor
            self.additional_wait_time = self.original_additional_wait_time * self.current_adjustment_factor
            
            print(f"🚨 [DYNAMIC] 실시간 조절: 10분 내 {recent_10min_requests}회 요청 ({status}, 임계값: {threshold}회)")
            print(f"⚡ [DYNAMIC] 조절 계수: {old_factor:.2f} → {self.current_adjustment_factor:.2f}배, 추가 대기: {self.additional_wait_time:.3f}초")
            return
        
        # 임계값 근처에서 자동 조절 (임계값의 80%~100% 범위)
        elif recent_10min_requests >= threshold * 0.8:
            # 임계값에 가까우면 조절 계수를 점진적으로 감소
            if self.current_adjustment_factor > 1.0:
                # 현재 조절 계수가 1.0보다 크면 점진적으로 감소
                target_factor = 1.0 + (self.current_adjustment_factor - 1.0) * 0.8  # 20% 감소
                if target_factor < 1.0:
                    target_factor = 1.0
                
                old_factor = self.current_adjustment_factor
                self.current_adjustment_factor = target_factor
                self.additional_wait_time = self.original_additional_wait_time * self.current_adjustment_factor
                
                print(f"🎯 [DYNAMIC] 임계값 근접 조절: 10분 내 {recent_10min_requests}회 요청 (임계값: {threshold}회)")
                print(f"⚡ [DYNAMIC] 조절 계수: {old_factor:.2f} → {self.current_adjustment_factor:.2f}배, 추가 대기: {self.additional_wait_time:.3f}초")
                return
        
        # 조절 간격 체크 (1분마다)
        if current_time - self.last_adjustment_time < self.adjustment_interval:
            return
        
        # 최근 1시간 내 요청 수 계산
        recent_requests = self._calculate_recent_requests(3600)
        
        # 모드별 임계값 가져오기
        thresholds = self._get_request_thresholds()
        
        # 대기시간 조절 계수 계산 (더 강한 조절)
        old_factor = self.current_adjustment_factor
        
        if recent_requests >= thresholds["high"]:
            self.current_adjustment_factor = 2.0  # 100% 증가 (더 강한 조절)
            status = "높음"
        elif recent_requests >= thresholds["medium"]:
            self.current_adjustment_factor = 1.5  # 50% 증가
            status = "보통"
        elif recent_requests >= thresholds["low"]:
            self.current_adjustment_factor = 1.0  # 유지
            status = "낮음"
        elif recent_requests >= thresholds["very_low"]:
            self.current_adjustment_factor = 0.7  # 30% 감소
            status = "매우 낮음"
        else:
            self.current_adjustment_factor = 0.5  # 50% 감소
            status = "극히 낮음"
        
        # 대기시간 적용
        self.additional_wait_time = self.original_additional_wait_time * self.current_adjustment_factor
        
        # 조절 시간 업데이트
        self.last_adjustment_time = current_time
        
        # 로깅 (1분마다 현재 상태 표시)
        if abs(old_factor - self.current_adjustment_factor) > 0.05:
            # 조절 계수가 변경된 경우
            print(f"📊 [DYNAMIC] 최근 1시간 요청: {recent_requests}회 ({status})")
            print(f"⚡ [DYNAMIC] 대기시간 조절: {old_factor:.2f} → {self.current_adjustment_factor:.2f}배")
            print(f"⏱️  [DYNAMIC] 실제 대기시간: {self.additional_wait_time:.2f}초")
        else:
            # 조절 계수가 변경되지 않은 경우에도 현재 상태 표시
            print(f"📊 [DYNAMIC] 최근 1시간 요청: {recent_requests}회 ({status}) - 조절 계수 유지: {self.current_adjustment_factor:.2f}배")
    
    def wait_before_query(self, query_type: str) -> None:
        # 6시간 체크 및 리셋 (매 요청마다 실행)
        self._check_and_reset_if_needed()
        
        # 요청 타임스탬프 기록 (동적 조절을 위한 요청 추적)
        current_time = time.time()
        if not hasattr(self, '_request_timestamps'):
            self._request_timestamps = []
        self._request_timestamps.append(current_time)
        
        # 오래된 타임스탬프 정리 (메모리 효율성을 위해 2시간 이상 된 것만 유지)
        cutoff_time = current_time - 7200  # 2시간
        self._request_timestamps = [ts for ts in self._request_timestamps if ts >= cutoff_time]
        
        # 동적 대기시간 조절 (5분마다 실행)
        self._check_and_adjust_dynamically()
        
        # Instaloader의 기본 대기시간 계산
        base_waittime = self.query_waittime(query_type, time.monotonic(), False)
        safe_debug(f"[DEBUG] query_waittime 결과: {base_waittime}초 (query_type: {query_type})")
        
        # Instaloader의 원래 동작 복원 (최소 보장 제거)
        # base_waittime은 Instaloader가 자동으로 조절하도록 함
        
        # 동적 조절된 추가 대기시간 적용
        total_waittime = base_waittime + self.additional_wait_time
        
        # 기본 동작만 수행 (프로필 간 대기는 다운로더 레벨에서 처리)
        if total_waittime > 0:
            if self.additional_wait_time > 0:
                print(f"[REQUEST_WAIT_DEBUG] 기본 대기: {base_waittime:.3f}초 + 동적 조절: {self.additional_wait_time:.3f}초 = 총 {total_waittime:.3f}초")
            else:
                print(f"[REQUEST_WAIT_DEBUG] 기본 대기 시작: {base_waittime:.3f}초")
            self.sleep(total_waittime)
        
        # Instaloader의 내부 상태 업데이트
        super().wait_before_query(query_type)
import shutil
import random
from datetime import datetime
from ..utils.file_utils import create_dir_if_not_exists, logging
from ..utils.config import load_config, save_config
from .profile_manager import add_non_existent_profile_id, is_profile_id_non_existent, get_profile_id_for_username, add_private_not_followed_profile_id, is_private_not_followed_profile_id
from sqlite3 import OperationalError, connect
from platform import system
from glob import glob
from os.path import expanduser
from ..utils.environment import Environment

# 세션 파일 저장 디렉토리 설정
SESSION_DIR = Environment.SESSIONS_DIR
create_dir_if_not_exists(SESSION_DIR)

# 최신 스탬프 파일 경로
STAMPS_FILE_IMAGES = Environment.STAMPS_FILE
STAMPS_FILE_REELS = Environment.CONFIG_DIR / "latest-stamps-reels.ini"

def instaloader_login(username, download_path, include_videos=False, include_reels=False, cookiefile=None, resume_prefix=None, request_wait_time=0.0, anti_detection_mode="ON"):
    """
    Instaloader를 사용해 인스타그램에 로그인합니다. (세션 파일 사용)
    
    매개변수:
        username (str): 사용자 이름.
        download_path (str): 다운로드 경로.
        include_videos (bool): 영상 다운로드 여부.
        include_reels (bool): 릴스 다운로드 여부.
        cookiefile (str): Firefox의 cookies.sqlite 파일 경로 (선택적).
        request_wait_time (float): 요청 간 추가 대기시간 (초).
        anti_detection_mode (str): Anti-detection 모드 ("OFF", "ON", "SAFE").
        
    반환:
        Instaloader 객체 또는 None.
    """
    # Resume prefix 설정 - 기본적으로 이어받기 활성화 (프로필별로 나중에 설정)
    if resume_prefix is None:
        resume_prefix = "resume_default"  # 기본값, 프로필별로 덮어씀
    
    # 요청 간 대기시간 설정 적용
    print(f"[REQUEST_WAIT_DEBUG] 요청 간 대기시간 설정: {request_wait_time}초")
    print(f"[ANTI-DETECTION] 모드 설정: {anti_detection_mode}")
    print(f"[RESUME DEBUG] 기본 Resume prefix 설정: {resume_prefix}")
        
    # Anti-Detection 모드에 따른 Instaloader 설정
    if anti_detection_mode == "OFF":
        # OFF 모드: --no-anti-detection 옵션 사용
        L = instaloader.Instaloader(
            download_videos=include_videos or include_reels,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            post_metadata_txt_pattern='',
            dirname_pattern=download_path,
            max_connection_attempts=10,
            resume_prefix=resume_prefix,
            no_anti_detection=True  # --no-anti-detection 옵션 사용
        )
        print(f"[ANTI-DETECTION] OFF 모드: --no-anti-detection 옵션 사용")
    elif anti_detection_mode == "ON":
        # ON 모드: CustomRateController 사용 (동적 조절 기능 포함)
        L = instaloader.Instaloader(
            download_videos=include_videos or include_reels,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            post_metadata_txt_pattern='',
            dirname_pattern=download_path,
            max_connection_attempts=10,
            resume_prefix=resume_prefix,
            rate_controller=lambda context: CustomRateController(context, request_wait_time, anti_detection_mode)
        )
        print(f"[ANTI-DETECTION] ON 모드: CustomRateController 사용 (동적 조절 활성화)")
    else:
        # FAST/SAFE 모드: CustomRateController 사용
        L = instaloader.Instaloader(
            download_videos=include_videos or include_reels,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            post_metadata_txt_pattern='',
            dirname_pattern=download_path,
            max_connection_attempts=10,
            resume_prefix=resume_prefix,
            rate_controller=lambda context: CustomRateController(context, request_wait_time, anti_detection_mode)
        )
    print_debug_rate_controller(username, request_wait_time)
    session_file = os.path.join(SESSION_DIR, f"{username}.session")
    
    try:
        # 세션 파일이 존재하면 이를 우선 로드
        if os.path.isfile(session_file):
            L.load_session_from_file(username, filename=session_file)
            print_session_loaded(username)
        # 세션 파일이 없고 cookiefile이 제공되면 쿠키를 이용해 로그인 및 세션 저장
        elif cookiefile:
            print("Using cookies from {}.".format(cookiefile))
            conn = connect(f"file:{cookiefile}?immutable=1", uri=True)
            try:
                cookie_data = conn.execute(
                    "SELECT name, value FROM moz_cookies WHERE baseDomain='instagram.com'"
                )
            except OperationalError:
                cookie_data = conn.execute(
                    "SELECT name, value FROM moz_cookies WHERE host LIKE '%instagram.com'"
                )
            L.context._session.cookies.update(cookie_data)
            logged_in_username = L.test_login()
            if not logged_in_username:
                print("Firefox 쿠키를 통해 로그인하지 못했습니다.")
                return None
            print("Imported session cookie for {}.".format(logged_in_username))
            L.context.username = logged_in_username
            L.save_session_to_file(session_file)
        else:
            # 세션 파일이 없고 cookiefile도 제공되지 않으면 에러 (비밀번호 로그인 제거)
            print_login_failure(username, "세션 파일 또는 Firefox 쿠키 파일이 필요합니다")
            return None
    except instaloader.exceptions.BadCredentialsException:
        print_login_failure(username, "잘못된 아이디/비밀번호")
        return None
    except instaloader.exceptions.TwoFactorAuthRequiredException:
        print_login_failure(username, "이중 인증 필요")
        return None
    except Exception as e:
        safe_error(f"로그인 오류", username, e)
        return None

    return L

def get_cookiefile():
    default_cookiefile = {
        "Windows": "~/AppData/Roaming/Mozilla/Firefox/Profiles/*/cookies.sqlite",
        "Darwin": "~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite",
    }.get(system(), "~/.mozilla/firefox/*/cookies.sqlite")
    cookiefiles = glob(expanduser(default_cookiefile))
    if not cookiefiles:
        raise SystemExit("No Firefox cookies.sqlite file found. Use -c COOKIEFILE.")
    return cookiefiles[0]

def download_posts(
    L,
    username,
    search_term,
    search_type,
    target,
    include_images,
    include_videos,
    progress_queue,
    stop_event,
    resume_from=0
):
    """
    해시태그 또는 사용자 ID를 기반으로 인스타그램 게시물을 다운로드합니다.
    """
    def my_tag_filter(post):
        if include_images and include_videos:
            return True
        if include_images and not include_videos:
            return not post.is_video
        if include_videos and not include_images:
            return post.is_video
        return False

    print(f"{search_term} 다운로드 시작 (검색 유형: {search_type})")
    progress_queue.put(("term_start", search_term, username))

    try:
        if search_type == 'hashtag':
            hashtag = instaloader.Hashtag.from_name(L.context, search_term)
            total_posts = hashtag.mediacount
        else:
            print("지원되지 않는 검색 유형입니다.")
            progress_queue.put(("term_error", search_term, "지원되지 않는 검색 유형", username))
            return

        # 타입 안전성 개선: 문자열을 정수로 변환 (test-refactoring에서 추가된 기능)
        if isinstance(total_posts, str):
            try:
                total_posts = int(total_posts)
            except ValueError:
                print(f"경고: total_posts를 정수로 변환할 수 없습니다: {total_posts}")
                total_posts = 0

        if target != 0 and target < total_posts:
            total_posts = target

        # total_posts가 문자열인 경우 정수로 변환
        if isinstance(total_posts, str):
            try:
                total_posts = int(total_posts)
            except ValueError:
                print(f"경고: total_posts를 정수로 변환할 수 없습니다: {total_posts}")
                total_posts = 0

        if stop_event.is_set():
            print("중지 신호 감지. 다운로드 중지됨.")
            progress_queue.put(("term_error", search_term, "사용자 중지", username))
            return

        # 다운로드는 기본 디렉토리(unclassified) 내에 hashtag/[해시태그] 폴더에 저장
        target_folder = os.path.join(L.dirname_pattern, 'hashtag', search_term)
        create_dir_if_not_exists(target_folder)

        original_dirname = L.dirname_pattern
        L.dirname_pattern = target_folder
        
        # 해시태그별 resume prefix 설정
        hashtag_resume_prefix = f"resume_hashtag_{search_term}"
        L.resume_prefix = hashtag_resume_prefix
        print(f"📌 [RESUME HASHTAG] 해시태그: {search_term}, resume_prefix: {hashtag_resume_prefix}")
        
        # 해시태그 resume 파일 확인
        import glob as glob_module
        hashtag_resume_files = glob_module.glob(f"{hashtag_resume_prefix}_*.json.xz")
        if hashtag_resume_files:
            print(f"📌 [RESUME HASHTAG] 기존 resume 파일 발견: {hashtag_resume_files[0]}")
        else:
            print(f"📌 [RESUME HASHTAG] 기존 resume 파일 없음 - 새로 시작")

        try:
            if include_images or include_videos:
                L.download_hashtag_top_serp(
                    search_term,
                    max_count=total_posts,
                    post_filter=my_tag_filter,
                    profile_pic=False
                )
                if include_videos:
                    # 기본 다운로드 경로의 상위 폴더를 기준으로 Reels/hashtag/[해시태그] 경로를 설정
                    base_path = os.path.dirname(original_dirname)
                    videos_folder = os.path.join(base_path, 'Reels', 'hashtag', search_term)
                    create_dir_if_not_exists(videos_folder)
                    video_files = []
                    for root, dirs, files in os.walk(target_folder):
                        for file in files:
                            if file.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                                video_files.append(file)
                                source_path = os.path.join(root, file)
                                destination_path = os.path.join(videos_folder, file)
                                try:
                                    shutil.move(source_path, destination_path)
                                    print(f"동영상 이동: {file} -> {videos_folder}")
                                except Exception as e:
                                    print(f"동영상 이동 오류: {e}")
                                    progress_queue.put(("term_error", search_term, f"동영상 이동 오류: {e}", username))
                    if video_files:
                        progress_queue.put(("term_progress", search_term, "동영상 이동 완료", username))
        except Exception as e:
            print(f"게시물 다운로드 오류: {e}")
            progress_queue.put(("term_error", search_term, f"게시물 다운로드 오류: {e}", username))
            L.dirname_pattern = original_dirname

        L.dirname_pattern = original_dirname
        progress_queue.put(("term_progress", search_term, 1, username))
        print(f"{search_term} 다운로드 완료")
        # 성공 로그 기록
        log_download_success(search_term, search_term, "hashtag", username, 1)
        # term_complete는 crawl_and_download에서 처리하므로 여기서는 전송하지 않음
    except instaloader.exceptions.LoginRequiredException as e:
        print(f"로그인 필요 오류: {e}")
        log_download_failure(search_term, search_term, "로그인 필요", str(e), "hashtag", username)
        progress_queue.put(("term_error", search_term, "로그인 필요", username))
    except instaloader.exceptions.ConnectionException as e:
        print(f"연결 오류: {e}")
        log_download_failure(search_term, search_term, "연결 오류", str(e), "hashtag", username)
        progress_queue.put(("term_error", search_term, f"연결 오류: {e}", username))
    except Exception as e:
        print(f"다운로드 오류: {e}")
        log_download_failure(search_term, search_term, "다운로드 오류", str(e), "hashtag", username)
        progress_queue.put(("account_switch_needed", username))

def rename_directories(base_path, search_type, old_name, new_name):
    """
    기본 경로 내에서 여러 카테고리의 디렉토리 이름을 변경합니다.
    
    매개변수:
        base_path (str): 기본 다운로드 경로.
        search_type (str): 검색 유형 접두사.
        old_name (str): 기존 이름.
        new_name (str): 새 이름.
    """
    folders = [
        (os.path.join(base_path, "unclassified", "ID"), ""),
        (os.path.join(base_path, "Reels", "ID"), ""),
        (os.path.join(base_path, "인물"), f"{search_type}_"),
        (os.path.join(base_path, "비인물"), f"{search_type}_")
    ]
    for folder, prefix in folders:
        old_dir = os.path.join(folder, f"{prefix}{old_name}")
        new_dir = os.path.join(folder, f"{prefix}{new_name}")
        if os.path.exists(old_dir) and not os.path.exists(new_dir):
            os.rename(old_dir, new_dir)
            print(f"디렉토리 이름 변경: {old_dir} -> {new_dir}")
        else:
            print(f"디렉토리 없음 또는 이미 존재: {old_dir}")

def user_download_with_profiles(L, search_user, target, include_images, include_reels, progress_queue, stop_event, allow_duplicate, base_path, search_type):
    """
    특정 사용자의 프로필 및 게시물을 다운로드합니다.
    
    매개변수:
        L (Instaloader): 로그인된 Instaloader 객체.
        search_user (str): 대상 사용자.
        target (int): 다운로드할 게시물 수 (0이면 전체).
        include_images (bool): 이미지 다운로드 여부.
        include_reels (bool): 릴스 다운로드 여부.
        progress_queue: 진행 상황 큐.
        stop_event: 중지 이벤트.
        allow_duplicate (bool): 중복 다운로드 허용 여부.
        base_path (str): 기본 다운로드 경로.
        search_type (str): 검색 유형.
    """
    # target이 문자열인 경우 정수로 변환
    if isinstance(target, str):
        try:
            target = int(target)
        except ValueError:
            print(f"경고: target을 정수로 변환할 수 없습니다: {target}")
            target = 0
    
    def download_content():
        nonlocal search_user, base_path
        resume_prefix = None  # resume_prefix 변수를 함수 스코프에서 접근 가능하도록 선언
        try:
            def my_post_filter(post):
                if include_images and include_reels:
                    return True
                if include_images and not include_reels:
                    return not post.is_video
                if include_reels and not include_images:
                    return post.is_video
                return False

            L_content = L
            latest_stamps_images = LatestStamps(STAMPS_FILE_IMAGES)

            old_username = search_user
            stored_id = latest_stamps_images.get_profile_id(old_username)
            profile = None
            
            # 프로필 조회 시도 (재시도 횟수 제한)
            max_retries = 3
            retry_count = 0
            
            # Rate Limiting을 위한 대기 시간
            time.sleep(2)
            
            if stored_id:
                try:
                    temp_profile = Profile.from_id(L_content.context, stored_id)
                    if temp_profile.username != old_username:
                        latest_stamps_images.rename_profile(old_username, temp_profile.username)
                        print(f"사용자명 변경: {old_username} -> {temp_profile.username}")
                        rename_directories(base_path, search_type, old_username, temp_profile.username)
                        search_user = temp_profile.username
                        profile = temp_profile
                    else:
                        profile = Profile.from_id(L_content.context, stored_id)
                except Exception as e:
                    safe_error(f"저장된 ID로 프로필 조회 실패", exception=e)
                    # 저장된 ID로 실패한 경우 username으로 재시도
                    profile = None
                    try:
                        profile = Profile.from_username(L_content.context, old_username)
                    except Exception as e:
                        error_msg = str(e)
                        safe_error(f"프로필 조회 실패: {error_msg}", old_username)
                        
                        # 오류 유형별 처리
                        if "does not exist" in error_msg:
                            # 프로필이 존재하지 않는 경우
                            log_download_failure(old_username, old_username, "프로필 없음", error_msg, "user", L.context.username)
                            stored_profile_id = get_profile_id_for_username(old_username)
                            if stored_profile_id:
                                add_non_existent_profile_id(stored_profile_id, old_username)
                            else:
                                config = load_config()
                                if old_username not in config.get('NON_EXISTENT_PROFILES', []):
                                    config.setdefault('NON_EXISTENT_PROFILES', []).append(old_username)
                                    save_config(config)
                                    print(f"존재하지 않는 프로필 '{old_username}'을 설정에 저장했습니다.")
                            progress_queue.put(("term_error", old_username, error_msg, L.context.username))
                        elif "401 Unauthorized" in error_msg or "Server Error" in error_msg:
                            # Instagram API 인증 오류 또는 서버 오류
                            log_download_failure(old_username, old_username, "서버 오류", error_msg, "user", L.context.username)
                            progress_queue.put(("term_error", old_username, "Instagram 서버 오류 - 잠시 후 다시 시도해주세요", L.context.username))
                        else:
                            # 기타 오류
                            log_download_failure(old_username, old_username, "프로필 조회 실패", error_msg, "user", L.context.username)
                            progress_queue.put(("term_error", old_username, f"프로필 조회 실패: {error_msg}", L.context.username))
                        return
            else:
                # 저장된 ID가 없는 경우 username으로 조회
                profile = None
                try:
                    profile = Profile.from_username(L_content.context, search_user)
                except Exception as e:
                    error_msg = str(e)
                    print(f"프로필 조회 실패: {search_user} - {error_msg}")
                    
                    # 오류 유형별 처리
                    if "does not exist" in error_msg:
                        # 프로필이 존재하지 않는 경우
                        log_download_failure(search_user, search_user, "프로필 없음", error_msg, "user", L.context.username)
                        stored_profile_id = get_profile_id_for_username(search_user)
                        if stored_profile_id:
                            add_non_existent_profile_id(stored_profile_id, search_user)
                        else:
                            config = load_config()
                            if search_user not in config.get('NON_EXISTENT_PROFILES', []):
                                config.setdefault('NON_EXISTENT_PROFILES', []).append(search_user)
                                save_config(config)
                                print(f"존재하지 않는 프로필 '{search_user}'을 설정에 저장했습니다.")
                        progress_queue.put(("term_error", search_user, error_msg, L.context.username))
                    elif "401 Unauthorized" in error_msg or "Server Error" in error_msg:
                        # Instagram API 인증 오류 또는 서버 오류
                        log_download_failure(search_user, search_user, "서버 오류", error_msg, "user", L.context.username)
                        progress_queue.put(("term_error", search_user, "Instagram 서버 오류 - 잠시 후 다시 시도해주세요", L.context.username))
                    else:
                        # 기타 오류
                        log_download_failure(search_user, search_user, "프로필 조회 실패", error_msg, "user", L.context.username)
                        progress_queue.put(("term_error", search_user, f"프로필 조회 실패: {error_msg}", L.context.username))
                    return

            # profile이 None인 경우 처리
            if profile is None:
                print(f"프로필이 None입니다: {search_user}")
                progress_queue.put(("term_error", search_user, "프로필을 찾을 수 없습니다", L.context.username))
                return
                
            content_folder = os.path.join(base_path, "unclassified", "ID", profile.username)
            L_content.dirname_pattern = content_folder
            create_dir_if_not_exists(content_folder)             

            # Resume prefix를 프로필 중심으로 설정 (로그인 계정과 무관)
            profile_resume_prefix = f"resume_profile_{profile.username}"
            L_content.resume_prefix = profile_resume_prefix 

            if latest_stamps_images.get_profile_id(profile.username) is None:
                latest_stamps_images.save_profile_id(profile.username, profile.userid)
                print(f"프로필 정보 저장: {profile.username}")

            image_kwargs = {
                'profiles': {profile},
                'profile_pic': False,
                'posts': include_images or include_reels,
                'tagged': False,
                'igtv': False,
                'highlights': False,
                'stories': False,
                'fast_update': False,
                'post_filter': my_post_filter,
                'raise_errors': True,
                'latest_stamps': None if allow_duplicate else latest_stamps_images,
                'max_count': int(target) if target != 0 else None,
            }

            # 다운로드 실행
            if stop_event.is_set():
                return
            L_content.download_profiles(**image_kwargs)
            
            # username이 변경된 경우 old_username을 전달하여 검색목록에서 제거
            completed_username = old_username if old_username != profile.username else profile.username
            
            # 성공 로그 기록 (다운로드된 게시물 수는 정확히 알 수 없으므로 0으로 표시)
            log_download_success(completed_username, completed_username, "user", L.context.username, 0)
            
            # term_complete는 crawl_and_download에서 처리하므로 여기서는 전송하지 않음

            if include_reels:
                reels_folder = os.path.join(base_path, 'Reels', 'ID', profile.username)
                create_dir_if_not_exists(reels_folder)
                video_files = []
                for root, dirs, files in os.walk(content_folder):
                    for file in files:
                        if file.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                            video_files.append(file)
                            source_path = os.path.join(root, file)
                            destination_path = os.path.join(reels_folder, file)
                            try:
                                shutil.move(source_path, destination_path)
                                print(f"동영상 이동: {file} -> Reels 폴더")
                            except Exception as e:
                                print(f"동영상 이동 오류: {e}")
                                progress_queue.put(("term_error", profile.username, f"동영상 이동 오류: {e}", L.context.username))
                if video_files:
                    progress_queue.put(("term_progress", profile.username, "동영상 이동 완료", L.context.username))
        except Exception as e:
            error_msg = str(e)
            
            # Resume 파일 삭제 오류는 무시 (Instaloader 4.14의 정상 동작)
            if "지정된 파일을 찾을 수 없습니다" in error_msg and "resume" in error_msg.lower():
                print(f"ℹ️ [RESUME] {search_user} - Resume 파일 삭제 완료 (정상 동작)")
                # Resume 파일 삭제는 정상 동작이므로 성공으로 처리
                progress_queue.put(("term_complete", search_user, "다운로드 완료", L.context.username))
                return
            
            print(f"{search_user} 다운로드 오류: {error_msg}")
            
            # "Private but not followed" 오류 감지 및 저장
            if "Private but not followed" in error_msg:
                # 비공개 프로필 로그 기록
                log_download_failure(search_user, search_user, "비공개 프로필", error_msg, "user", L.context.username)
                
                # 저장된 profile-id가 있으면 해당 ID를 비공개 프로필로 저장
                stored_profile_id = get_profile_id_for_username(search_user)
                if stored_profile_id:
                    add_private_not_followed_profile_id(stored_profile_id, search_user)
                else:
                    # profile-id가 없으면 username으로 저장 (하위 호환성)
                    config = load_config()
                    if search_user not in config.get('PRIVATE_NOT_FOLLOWED_PROFILES', []):
                        config.setdefault('PRIVATE_NOT_FOLLOWED_PROFILES', []).append(search_user)
                        save_config(config)
                        print(f"비공개 프로필 '{search_user}'을 설정에 저장했습니다.")
                
                # 비공개 프로필로 저장된 경우 검색목록에서 제거
                progress_queue.put(("term_complete", search_user, f"비공개 프로필로 저장됨: {error_msg}", L.context.username))
            else:
                # 일반 다운로드 오류 로그 기록
                log_download_failure(search_user, search_user, "다운로드 오류", error_msg, "user", L.context.username)
                progress_queue.put(("term_error", search_user, f"콘텐츠 다운로드 오류: {error_msg}", L.context.username))
            #raise
    download_content()

def setup_download_environment(download_path, include_images, include_videos, include_reels):
    """
    다운로드 환경을 설정합니다.
    """
    import os
    from ..utils.environment import Environment
    
    # 다운로드 경로가 비어있거나 None인 경우 프로젝트 루트의 download 디렉토리 사용
    if not download_path or download_path.strip() == '':
        base_download_path = os.path.join(str(Environment.BASE_DIR), "download")
        print(f"다운로드 경로가 존재하지 않습니다. 기본 경로 사용: {base_download_path}")
        # 크롤링 시작 시에만 download 디렉토리 생성
        create_dir_if_not_exists(base_download_path)
    else:
        base_download_path = download_path
        print(f"다운로드 경로: {base_download_path}")
        # 사용자가 지정한 경로는 항상 생성
        create_dir_if_not_exists(base_download_path)
    
    # 하위 디렉토리 생성
    for sub in ["unclassified", "Reels", "인물", "비인물"]:
        create_dir_if_not_exists(os.path.join(base_download_path, sub))
    
    # 요청 간 대기시간 설정 로드
    config = load_config()
    request_wait_time = config.get('REQUEST_WAIT_TIME', 0.0)
    
    return base_download_path, request_wait_time

def setup_accounts(accounts, base_download_path, include_videos, include_reels, request_wait_time, anti_detection_mode="ON"):
    """
    계정을 설정하고 로그인합니다.
    """
    loaded_loaders = []
    
    if not accounts:
        # 익명 크롤링
        print(f"[REQUEST_WAIT_DEBUG] 익명 크롤링 시작 - 요청 간 대기시간: {request_wait_time}초")
        
        # 익명 크롤링에서도 Anti-Detection 모드 적용
        if anti_detection_mode == "OFF":
            loader = instaloader.Instaloader(
                download_videos=include_videos,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                post_metadata_txt_pattern='',
                dirname_pattern=os.path.join(base_download_path, "unclassified"),
                max_connection_attempts=3,
                resume_prefix="resume_anonymous",
                no_anti_detection=True
            )
        elif anti_detection_mode == "ON":
            loader = instaloader.Instaloader(
                download_videos=include_videos,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                post_metadata_txt_pattern='',
                dirname_pattern=os.path.join(base_download_path, "unclassified"),
                max_connection_attempts=3,
                resume_prefix="resume_anonymous"
            )
        else:
            loader = instaloader.Instaloader(
                download_videos=include_videos,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                post_metadata_txt_pattern='',
                dirname_pattern=os.path.join(base_download_path, "unclassified"),
                max_connection_attempts=3,
                resume_prefix="resume_anonymous",
                rate_controller=lambda context: CustomRateController(context, request_wait_time, anti_detection_mode)
            )
        safe_debug(f"[REQUEST_WAIT_DEBUG] CustomRateController 적용됨 - 익명 사용자, 추가 대기시간: {request_wait_time}초")
        loaded_loaders.append({'loader': loader, 'username': 'anonymous', 'active': True})
    else:
        # 계정 크롤링
        safe_debug(f"[REQUEST_WAIT_DEBUG] 계정 크롤링 시작 - 요청 간 대기시간: {request_wait_time}초")
        
        for account in accounts:
            loader = instaloader_login(
                account['INSTAGRAM_USERNAME'],
                os.path.join(base_download_path, "unclassified"),
                include_videos,
                include_reels,
                get_cookiefile(),
                request_wait_time=request_wait_time,
                anti_detection_mode=anti_detection_mode
            )
            if loader:
                loaded_loaders.append({
                    'loader': loader,
                    'username': account['INSTAGRAM_USERNAME'],
                    'active': True
                })
                
                # 로그인 성공 시 LAST_ACCOUNT_USED 업데이트 및 LOGIN_HISTORY 갱신
                config = load_config()
                config['LAST_ACCOUNT_USED'] = account['INSTAGRAM_USERNAME']
                
                # LOGIN_HISTORY 업데이트 (최근 사용한 계정을 맨 앞으로, 비밀번호 제거)
                login_history = config.get('LOGIN_HISTORY', [])
                login_history = [hist for hist in login_history if hist['username'] != account['INSTAGRAM_USERNAME']]
                login_history.insert(0, {
                    'username': account['INSTAGRAM_USERNAME'],
                    'download_path': account['DOWNLOAD_PATH']
                })
                config['LOGIN_HISTORY'] = login_history[:10]
                
                save_config(config)
            else:
                safe_error(f"로그인 실패", account['INSTAGRAM_USERNAME'])
    
    return loaded_loaders

def process_downloads(loaded_loaders, search_terms, target, search_type, include_images, include_videos, 
                     include_reels, include_human_classify, include_upscale, progress_queue, stop_event, 
                     base_download_path, append_status, root, download_directory_var, allow_duplicate,
                     update_overall_progress, update_current_progress, update_eta, start_time, total_terms,
                     request_wait_time, anti_detection_mode="ON"):
    """
    실제 다운로드를 처리합니다.
    """
    account_index = 0
    total_accounts = len(loaded_loaders)
    last_processed_term = None
    
    from ..processing.post_processing import process_images
    
    try:
        while account_index < total_accounts:
            loader_dict = loaded_loaders[account_index]
            L = loader_dict['loader']
            current_username = loader_dict['username']
            
            try:
                for i, term in enumerate(search_terms):
                    if stop_event.is_set():
                        append_status("중지: 다운로드 중지 신호 감지됨.")
                        return
                    
                    # 프로필 간 추가 대기시간 적용
                    if request_wait_time > 0 and last_processed_term is not None:
                        print(f"[REQUEST_WAIT_DEBUG] 프로필 간 대기 시작: {request_wait_time}초 (이전: {last_processed_term} -> 현재: {term})")
                        time.sleep(request_wait_time)
                        print(f"[REQUEST_WAIT_DEBUG] 프로필 간 대기 완료")
                    
                    # 전체 진행률 업데이트
                    if update_overall_progress and total_terms:
                        update_overall_progress(i, total_terms, term)
                    
                    # 예상 완료 시간 업데이트
                    if update_eta and start_time:
                        update_eta(start_time, i, total_terms)
                    
                    progress_queue.put(("term_progress", term, "콘텐츠 다운로드 시작", L.context.username))
                    
                    # 다운로드 실행
                    if search_type == 'hashtag':
                        download_posts(L, current_username, term, search_type, target,
                                       include_images, include_videos, progress_queue, stop_event, base_download_path)
                    else:
                        user_download_with_profiles(L, term, target, include_images, include_reels,
                                                   progress_queue, stop_event, allow_duplicate, base_download_path, search_type)
                    
                    # 다운로드 완료 후 처리
                    if include_human_classify and not stop_event.is_set():
                        # 인물 분류가 체크되어 있으면 분류 진행
                        classify_dir = os.path.join(base_download_path, 'unclassified',
                                                    'hashtag' if search_type == 'hashtag' else 'ID',
                                                    term)
                        print(f"인물분류 체크: {term} - 디렉토리: {classify_dir}")
                        if os.path.isdir(classify_dir):
                            image_files = [fname for fname in os.listdir(classify_dir) if fname.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
                            print(f"인물분류 체크: {term} - 이미지 파일 수: {len(image_files)}")
                            if image_files:
                                print(f"인물분류 시작: {term}")
                                process_images(root, append_status, download_directory_var, term, current_username, search_type, stop_event, include_upscale, classified=False)
                                # 분류 완료 후 검색 목록에서 삭제
                                progress_queue.put(("term_classify_complete", term, "다운로드 및 분류 완료", L.context.username))
                            else:
                                print(f"인물분류 스킵: {term} - 이미지 파일 없음")
                                # 이미지 파일이 없으면 다운로드 완료 후 검색 목록에서 삭제
                                progress_queue.put(("term_complete", term, "다운로드 완료 (분류 스킵)", L.context.username))
                        else:
                            print(f"인물분류 스킵: {term} - 디렉토리 없음")
                            # 디렉토리가 없으면 다운로드 완료 후 검색 목록에서 삭제
                            progress_queue.put(("term_complete", term, "다운로드 완료 (분류 스킵)", L.context.username))
                        if stop_event.is_set():
                            append_status("중지: 분류 중지됨.")
                            return
                    else:
                        # 인물 분류가 체크되어 있지 않으면 다운로드 완료 후 즉시 검색 목록에서 삭제
                        progress_queue.put(("term_complete", term, "다운로드 완료", L.context.username))
                    
                    if stop_event.is_set():
                        append_status("중지: 다운로드 중지됨.")
                        return
                    
                    # 현재 프로필 처리 완료 표시
                    last_processed_term = term
                break
            except Exception as e:
                error_msg = str(e)
                safe_error(f"계정 처리 오류: {error_msg}", current_username)
                append_status("계정 오류 발생, 재로그인 시도 중...")
                progress_queue.put(("account_relogin", current_username, "재로그인 시도 중..."))

                # 429 오류인 경우: 계정을 순환 (라운드 로빈)
                if "429" in error_msg:
                    safe_error(f"429 오류 발생", current_username)
                    account_index = (account_index + 1) % total_accounts
                    new_username = loaded_loaders[account_index]['username']
                    print_account_switch(current_username, new_username)
                    log_account_switch(current_username, new_username, "429 오류로 인한 계정 전환")
                    progress_queue.put(("account_switch", new_username, "계정 전환 중..."))
                    
                    # 계정 전환 시 LAST_ACCOUNT_USED 업데이트
                    config = load_config()
                    config['LAST_ACCOUNT_USED'] = new_username
                    save_config(config)
                    continue

                # 429 오류가 아닌 경우: 재로그인 시도 후 실패하면 마지막 계정이면 중단
                new_loader = instaloader_login(
                    loader_dict['username'],
                    os.path.join(base_download_path, "unclassified"),
                    include_videos,
                    include_reels,
                    get_cookiefile(),
                    request_wait_time=request_wait_time,
                    anti_detection_mode=anti_detection_mode
                )
                if new_loader:
                    loaded_loaders[account_index]['loader'] = new_loader
                    L = new_loader
                    safe_print(f"재로그인 성공", current_username)
                    continue
                else:
                    safe_error(f"재로그인 실패", current_username)
                    account_index += 1
                    if account_index < total_accounts:
                        next_username = loaded_loaders[account_index]['username']
                        print_account_switch(current_username, next_username)
                        log_account_switch(current_username, next_username, "재로그인 실패로 인한 계정 전환")
                        progress_queue.put(("account_switch", loaded_loaders[account_index]['username'], "계정 전환 중..."))
                        continue
                    else:
                        for term in search_terms:
                            log_download_failure(term, term, "모든 계정 차단", "재로그인 실패로 인한 모든 계정 차단", search_type, current_username)
                            progress_queue.put(("term_error", term, "모든 계정 차단됨", current_username))
                        break
    finally:
        stop_event.clear()

def crawl_and_download(search_terms, target, accounts, search_type, include_images, include_videos, include_reels,
                       include_human_classify, include_upscale, progress_queue, on_complete, stop_event, download_path='download', append_status=None,
                       root=None, download_directory_var=None, allow_duplicate=False, update_overall_progress=None, 
                       update_current_progress=None, update_eta=None, start_time=None, total_terms=None):
    """
    인스타그램 게시물을 크롤링 및 다운로드하는 메인 함수.
    """
    print("크롤링 및 다운로드 시작...")
    
    # append_status가 None인 경우 기본 함수 사용
    if append_status is None:
        append_status = lambda msg: print(f"[STATUS] {msg}")
    
    # 타입 안전성 개선: target이 문자열인 경우 정수로 변환
    if isinstance(target, str):
        try:
            target = int(target)
        except ValueError:
            print(f"경고: target을 정수로 변환할 수 없습니다: {target}")
            target = 0
    
    # 1. 환경 설정
    base_download_path, request_wait_time = setup_download_environment(
        download_path, include_images, include_videos, include_reels
    )
    
    # Anti-Detection 모드 설정 로드
    config = load_config()
    from .anti_detection import migrate_old_config
    # ANTI_DETECTION_MODE가 없는 경우에만 마이그레이션 실행
    if 'ANTI_DETECTION_MODE' not in config:
        config = migrate_old_config(config)
    anti_detection_mode = config.get('ANTI_DETECTION_MODE', 'ON')
    print(f"[ANTI-DETECTION] 크롤링 시작 - 모드: {anti_detection_mode}")
    
    # 2. 계정 설정
    loaded_loaders = setup_accounts(
        accounts, base_download_path, include_videos, include_reels, request_wait_time, anti_detection_mode
    )
    
    # 3. 다운로드 처리
    process_downloads(
        loaded_loaders, search_terms, target, search_type, include_images, include_videos,
        include_reels, include_human_classify, include_upscale, progress_queue, stop_event,
        base_download_path, append_status, root, download_directory_var, allow_duplicate,
        update_overall_progress, update_current_progress, update_eta, start_time, total_terms,
        request_wait_time, anti_detection_mode
    )
    
    # 4. 완료 처리
    # 최종 요청 수 정보 저장
    try:
        # 현재 활성화된 CustomRateController가 있다면 요청 수 정보 저장
        if loaded_loaders:
            for loader_dict in loaded_loaders:
                loader = loader_dict['loader']
                if hasattr(loader, 'context') and hasattr(loader.context, '_rate_controller'):
                    rate_controller = loader.context._rate_controller
                    if hasattr(rate_controller, '_save_request_history_silent'):
                        rate_controller._save_request_history_silent()
                        break
    except Exception as e:
        safe_debug(f"[FINAL_SAVE] 최종 요청 수 저장 실패: {e}")
    
    on_complete("크롤링 완료됨.") 