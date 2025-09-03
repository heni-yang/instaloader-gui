# src/utils/security.py
"""
보안 관련 유틸리티 모듈
비밀번호 암호화/복호화 및 보안 키 관리
"""
import os
import base64
import hashlib
import logging
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from .environment import Environment

logger = logging.getLogger(__name__)

class PasswordManager:
    """비밀번호 암호화/복호화 관리 클래스"""
    
    def __init__(self):
        self.key_file = Environment.CONFIG_DIR / "security.key"
        self.salt_file = Environment.CONFIG_DIR / "security.salt"
        self._cipher = None
        self._initialize_encryption()
    
    def _initialize_encryption(self):
        """암호화 시스템 초기화"""
        try:
            # 기존 키와 솔트가 있으면 로드
            if self.key_file.exists() and self.salt_file.exists():
                self._load_existing_key()
            else:
                # 새로운 키와 솔트 생성
                self._generate_new_key()
            
            logger.info("암호화 시스템 초기화 완료")
        except Exception as e:
            logger.error(f"암호화 시스템 초기화 실패: {e}")
            raise SecurityError(f"암호화 초기화 실패: {e}")
    
    def _generate_new_key(self):
        """새로운 암호화 키와 솔트 생성"""
        try:
            # 랜덤 솔트 생성
            salt = os.urandom(16)
            
            # 머신 고유 정보를 기반으로 패스워드 생성
            machine_info = self._get_machine_fingerprint()
            
            # PBKDF2를 사용하여 키 유도
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(machine_info.encode()))
            
            # 키와 솔트를 파일에 저장
            self._save_key_and_salt(key, salt)
            
            # Fernet 암호화 객체 생성
            self._cipher = Fernet(key)
            
            logger.info("새로운 암호화 키 생성 완료")
        except Exception as e:
            logger.error(f"암호화 키 생성 실패: {e}")
            raise SecurityError(f"키 생성 실패: {e}")
    
    def _load_existing_key(self):
        """기존 암호화 키 로드"""
        try:
            # 솔트 로드
            with open(self.salt_file, 'rb') as f:
                salt = f.read()
            
            # 머신 고유 정보로 키 재생성
            machine_info = self._get_machine_fingerprint()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(machine_info.encode()))
            
            # Fernet 암호화 객체 생성
            self._cipher = Fernet(key)
            
            # 키 파일의 내용과 비교하여 검증
            with open(self.key_file, 'rb') as f:
                stored_key = f.read()
            
            if key != stored_key:
                raise SecurityError("저장된 키와 생성된 키가 일치하지 않습니다")
            
            logger.info("기존 암호화 키 로드 완료")
        except Exception as e:
            logger.error(f"암호화 키 로드 실패: {e}")
            raise SecurityError(f"키 로드 실패: {e}")
    
    def _save_key_and_salt(self, key, salt):
        """키와 솔트를 안전하게 파일에 저장"""
        try:
            # 디렉토리 생성
            Environment.ensure_directories()
            
            # 키 저장 (바이너리 모드)
            with open(self.key_file, 'wb') as f:
                f.write(key)
            
            # 솔트 저장 (바이너리 모드)
            with open(self.salt_file, 'wb') as f:
                f.write(salt)
            
            # 파일 권한 설정 (Windows에서는 제한적)
            try:
                os.chmod(self.key_file, 0o600)  # 소유자만 읽기/쓰기
                os.chmod(self.salt_file, 0o600)
            except OSError:
                # Windows에서는 chmod가 제한적이므로 무시
                pass
            
            logger.info("암호화 키와 솔트 저장 완료")
        except Exception as e:
            logger.error(f"키/솔트 저장 실패: {e}")
            raise SecurityError(f"키/솔트 저장 실패: {e}")
    
    def _get_machine_fingerprint(self):
        """머신 고유 지문 생성"""
        try:
            # 여러 시스템 정보를 조합하여 고유한 지문 생성
            import platform
            import uuid
            
            fingerprint_data = [
                platform.node(),  # 컴퓨터 이름
                platform.system(),  # OS 이름
                str(uuid.getnode()),  # MAC 주소
                os.environ.get('USERNAME', ''),  # 사용자명
                str(Path.home()),  # 홈 디렉토리
            ]
            
            # 데이터를 결합하고 해시
            combined = '|'.join(fingerprint_data)
            fingerprint = hashlib.sha256(combined.encode()).hexdigest()
            
            logger.debug("머신 지문 생성 완료")
            return fingerprint
        except Exception as e:
            logger.error(f"머신 지문 생성 실패: {e}")
            # 실패 시 기본값 사용
            return "default_machine_fingerprint"
    
    def encrypt_password(self, password):
        """비밀번호 암호화"""
        try:
            if not password:
                return ""
            
            if not self._cipher:
                raise SecurityError("암호화 시스템이 초기화되지 않았습니다")
            
            # 문자열을 바이트로 변환하고 암호화
            encrypted_bytes = self._cipher.encrypt(password.encode('utf-8'))
            
            # Base64로 인코딩하여 문자열로 반환
            encrypted_str = base64.urlsafe_b64encode(encrypted_bytes).decode('utf-8')
            
            logger.debug("비밀번호 암호화 완료")
            return f"ENC:{encrypted_str}"  # 암호화된 데이터임을 표시하는 접두사
        except Exception as e:
            logger.error(f"비밀번호 암호화 실패: {e}")
            raise SecurityError(f"암호화 실패: {e}")
    
    def decrypt_password(self, encrypted_password):
        """비밀번호 복호화"""
        try:
            if not encrypted_password:
                return ""
            
            # 암호화된 데이터인지 확인
            if not encrypted_password.startswith("ENC:"):
                # 평문 비밀번호인 경우 그대로 반환 (하위 호환성)
                logger.warning("평문 비밀번호 감지됨")
                return encrypted_password
            
            if not self._cipher:
                raise SecurityError("암호화 시스템이 초기화되지 않았습니다")
            
            # "ENC:" 접두사 제거
            encrypted_str = encrypted_password[4:]
            
            # Base64 디코딩
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_str.encode('utf-8'))
            
            # 복호화
            decrypted_bytes = self._cipher.decrypt(encrypted_bytes)
            
            # 문자열로 변환
            password = decrypted_bytes.decode('utf-8')
            
            logger.debug("비밀번호 복호화 완료")
            return password
        except Exception as e:
            logger.error(f"비밀번호 복호화 실패: {e}")
            raise SecurityError(f"복호화 실패: {e}")
    
    def is_encrypted(self, password):
        """비밀번호가 암호화되어 있는지 확인"""
        return password and password.startswith("ENC:")
    
    def migrate_plaintext_password(self, plaintext_password):
        """평문 비밀번호를 암호화된 형태로 마이그레이션"""
        try:
            if not plaintext_password:
                return ""
            
            if self.is_encrypted(plaintext_password):
                # 이미 암호화된 경우 그대로 반환
                return plaintext_password
            
            # 평문 비밀번호를 암호화
            return self.encrypt_password(plaintext_password)
        except Exception as e:
            logger.error(f"비밀번호 마이그레이션 실패: {e}")
            raise SecurityError(f"마이그레이션 실패: {e}")


class SecurityError(Exception):
    """보안 관련 예외 클래스"""
    pass


# 전역 인스턴스 (싱글톤 패턴)
_password_manager = None

def get_password_manager():
    """PasswordManager 싱글톤 인스턴스 반환"""
    global _password_manager
    if _password_manager is None:
        _password_manager = PasswordManager()
    return _password_manager


# 편의 함수들
def encrypt_password(password):
    """비밀번호 암호화 편의 함수"""
    return get_password_manager().encrypt_password(password)

def decrypt_password(encrypted_password):
    """비밀번호 복호화 편의 함수"""
    return get_password_manager().decrypt_password(encrypted_password)

def is_password_encrypted(password):
    """비밀번호 암호화 여부 확인 편의 함수"""
    return get_password_manager().is_encrypted(password)

def migrate_plaintext_password(plaintext_password):
    """평문 비밀번호 마이그레이션 편의 함수"""
    return get_password_manager().migrate_plaintext_password(plaintext_password)
