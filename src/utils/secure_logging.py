# src/utils/secure_logging.py
"""
보안 로깅 유틸리티 모듈
민감한 정보를 마스킹하여 안전하게 로깅합니다.
"""
import hashlib
import re
import logging
from typing import Optional, Dict, Set

logger = logging.getLogger(__name__)

class SecureLogger:
    """민감한 정보를 마스킹하는 보안 로거"""
    
    def __init__(self):
        # 사용자명을 해시로 매핑하는 캐시
        self._username_hash_cache: Dict[str, str] = {}
        
        # 민감한 패턴들
        self._sensitive_patterns = [
            r'password["\s]*[:=]["\s]*[^"\s,}]+',  # password 키-값 쌍
            r'token["\s]*[:=]["\s]*[^"\s,}]+',     # token 키-값 쌍
            r'secret["\s]*[:=]["\s]*[^"\s,}]+',    # secret 키-값 쌍
            r'key["\s]*[:=]["\s]*[^"\s,}]+',       # key 키-값 쌍
        ]
        
    def mask_username(self, username: str) -> str:
        """사용자명을 안전한 해시로 마스킹합니다."""
        if not username or username == 'anonymous':
            return username
            
        # 캐시에서 확인
        if username in self._username_hash_cache:
            return self._username_hash_cache[username]
        
        # 사용자명의 앞 2글자 + 해시 4글자
        if len(username) >= 2:
            prefix = username[:2]
        else:
            prefix = username[0] if username else 'u'
            
        # SHA256 해시의 앞 4글자 사용
        hash_part = hashlib.sha256(username.encode()).hexdigest()[:4]
        masked = f"{prefix}***{hash_part}"
        
        # 캐시에 저장
        self._username_hash_cache[username] = masked
        return masked
    
    def mask_sensitive_data(self, text: str) -> str:
        """텍스트에서 민감한 정보를 마스킹합니다."""
        if not text:
            return text
            
        masked_text = text
        
        # 정의된 패턴들로 마스킹
        for pattern in self._sensitive_patterns:
            masked_text = re.sub(
                pattern, 
                lambda m: m.group(0).split(':')[0] + ': ***MASKED***' if ':' in m.group(0) else '***MASKED***',
                masked_text,
                flags=re.IGNORECASE
            )
        
        return masked_text
    
    def safe_print(self, message: str, username: Optional[str] = None) -> None:
        """안전하게 메시지를 출력합니다."""
        safe_message = message
        
        # 사용자명 마스킹
        if username:
            masked_username = self.mask_username(username)
            safe_message = safe_message.replace(username, masked_username)
        
        # 민감한 데이터 마스킹
        safe_message = self.mask_sensitive_data(safe_message)
        
        print(safe_message)
        logger.info(safe_message)
    
    def safe_debug(self, message: str, username: Optional[str] = None) -> None:
        """안전하게 디버그 메시지를 출력합니다."""
        if not logger.isEnabledFor(logging.DEBUG):
            return
            
        safe_message = message
        
        # 사용자명 마스킹
        if username:
            masked_username = self.mask_username(username)
            safe_message = safe_message.replace(username, masked_username)
        
        # 민감한 데이터 마스킹
        safe_message = self.mask_sensitive_data(safe_message)
        
        logger.debug(safe_message)
    
    def safe_error(self, message: str, username: Optional[str] = None, exception: Optional[Exception] = None) -> None:
        """안전하게 오류 메시지를 출력합니다."""
        safe_message = message
        
        # 사용자명 마스킹
        if username:
            masked_username = self.mask_username(username)
            safe_message = safe_message.replace(username, masked_username)
        
        # 민감한 데이터 마스킹
        safe_message = self.mask_sensitive_data(safe_message)
        
        if exception:
            # 예외 메시지에서도 민감한 정보 마스킹
            exception_msg = str(exception)
            if username:
                exception_msg = exception_msg.replace(username, self.mask_username(username))
            exception_msg = self.mask_sensitive_data(exception_msg)
            safe_message = f"{safe_message}: {exception_msg}"
        
        print(safe_message)
        logger.error(safe_message)


# 전역 인스턴스 (싱글톤 패턴)
_secure_logger = None

def get_secure_logger() -> SecureLogger:
    """SecureLogger 싱글톤 인스턴스 반환"""
    global _secure_logger
    if _secure_logger is None:
        _secure_logger = SecureLogger()
    return _secure_logger


# 편의 함수들
def safe_print(message: str, username: Optional[str] = None) -> None:
    """안전한 출력 편의 함수"""
    get_secure_logger().safe_print(message, username)

def safe_debug(message: str, username: Optional[str] = None) -> None:
    """안전한 디버그 편의 함수"""
    get_secure_logger().safe_debug(message, username)

def safe_error(message: str, username: Optional[str] = None, exception: Optional[Exception] = None) -> None:
    """안전한 오류 출력 편의 함수"""
    get_secure_logger().safe_error(message, username, exception)

def mask_username(username: str) -> str:
    """사용자명 마스킹 편의 함수"""
    return get_secure_logger().mask_username(username)


# 레거시 print 함수를 대체하는 컨텍스트별 함수들
def print_login_success(username: str) -> None:
    """로그인 성공 메시지 안전 출력"""
    safe_print(f"로그인 성공: {username}", username)

def print_login_failure(username: str, reason: str = "잘못된 아이디/비밀번호") -> None:
    """로그인 실패 메시지 안전 출력"""
    safe_error(f"{reason}: {username}", username)

def print_session_loaded(username: str) -> None:
    """세션 로드 성공 메시지 안전 출력"""
    safe_print(f"세션 로드 성공: {username}", username)

def print_account_switch(from_username: str, to_username: str) -> None:
    """계정 전환 메시지 안전 출력"""
    safe_print(f"계정 전환: {from_username} → {to_username}", from_username)

def print_debug_rate_controller(username: str, wait_time: float) -> None:
    """레이트 컨트롤러 디버그 메시지 안전 출력"""
    safe_debug(f"[REQUEST_WAIT_DEBUG] CustomRateController 적용됨 - 사용자: {username}, 추가 대기시간: {wait_time}초", username)
