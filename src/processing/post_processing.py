# src/processing/post_processing.py
import os
import subprocess
from ..utils.file_utils import logging

# 분류 스크립트 파일명 및 모듈 이름
CLASSIFY_SCRIPT_NAME = 'classify_yolo.py'
CLASSIFY_SCRIPT_REL_PATH = os.path.join('processing', CLASSIFY_SCRIPT_NAME)
CLASSIFY_MODULE_NAME = "src.processing.yolo." + os.path.splitext(CLASSIFY_SCRIPT_NAME)[0]

face_upscale = 2
overall_scale = 2

class ProcessingEnvironment:
    """
    분류 처리를 위한 환경 설정을 관리합니다.
    """
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.parent_dir = os.path.abspath(os.path.join(self.script_dir, '..', '..'))
        self.python_executable = self._detect_python_path()
        self.classifier_script_file = os.path.join(self.script_dir, 'yolo', CLASSIFY_SCRIPT_NAME)
    
    def _detect_python_path(self):
        """
        가상환경의 Python 실행 파일 경로를 감지합니다.
        """
        if os.name == 'nt':
            return os.path.join(self.parent_dir, 'venv', 'classify_venv', 'Scripts', 'python.exe')
        else:
            return os.path.join(self.parent_dir, 'venv', 'classify_venv', 'bin', 'python')
    
    def validate_environment(self, append_status):
        """
        분류 환경이 유효한지 검증합니다.
        """
        if not os.path.exists(self.python_executable):
            append_status(f"오류: 가상환경 Python 실행 파일 없음: {self.python_executable}")
            return False
        
        if not os.path.isfile(self.classifier_script_file):
            append_status(f"오류: 분류 스크립트 없음: {self.classifier_script_file}")
            return False
        
        return True

class DirectoryManager:
    """
    분류 대상 디렉토리를 관리합니다.
    """
    @staticmethod
    def get_target_directories(download_path, search_term, search_type, classified):
        """
        분류 대상 디렉토리 목록을 반환합니다.
        """
        target_dirs = []
        
        if classified:
            target_dirs.extend(DirectoryManager._get_classified_directories(download_path, search_term, search_type))
        else:
            target_dirs.append(DirectoryManager._get_unclassified_directory(download_path, search_term, search_type))
        
        return target_dirs
    
    @staticmethod
    def _get_classified_directories(download_path, search_term, search_type):
        """
        이미 분류된 디렉토리들을 반환합니다.
        """
        dirs = []
        
        # 인물 디렉토리
        if search_type == "hashtag":
            person_dir = os.path.join(download_path, '인물', f"hashtag_{search_term}")
        else:
            person_dir = os.path.join(download_path, '인물', f"user_{search_term}")
        dirs.append(person_dir)
        
        # 비인물 디렉토리
        if search_type == "hashtag":
            non_person_base = os.path.join(download_path, '비인물', f"hashtag_{search_term}")
        else:
            non_person_base = os.path.join(download_path, '비인물', f"user_{search_term}")
        
        if os.path.isdir(non_person_base):
            dirs.append(non_person_base)
        
        return dirs
    
    @staticmethod
    def _get_unclassified_directory(download_path, search_term, search_type):
        """
        미분류 디렉토리를 반환합니다.
        """
        if search_type == "hashtag":
            return os.path.join(download_path, 'unclassified', 'hashtag', search_term)
        else:
            return os.path.join(download_path, 'unclassified', 'ID', search_term)

def run_upscaling(python_executable, input_image_dir, face_upscale, overall_scale):
    """
    업스케일링 스크립트를 모듈 형식으로 호출합니다 (upscaler.py).
    """
    module_name = "src.processing.upscaler.upscaler"
    cmd = [
        python_executable,
        "-m",
        module_name,
        input_image_dir,
        str(face_upscale),
        str(overall_scale)
    ]
    print("업스케일 프로세스 시작:", " ".join(cmd))
    process = subprocess.Popen(cmd, text=True)
    process.communicate()
    return process.returncode

def run_classification_process(python_executable, classifier_module, target_image_dir, stop_event, append_status, search_type, search_term, download_path):
    """
    분류 프로세스를 서브프로세스로 실행합니다.
    
    매개변수:
        python_executable (str): Python 실행 파일 경로.
        classifier_module (str): 분류 스크립트 모듈 이름.
        target_image_dir (str): 분류할 이미지 디렉토리.
        stop_event: 중지 이벤트.
        append_status: 상태 메시지 기록 함수.
        search_type (str): 검색 유형.
        search_term (str): 검색어.
        download_path (str): 다운로드 기본 경로.
        
    반환:
        int 또는 None: 프로세스 종료 코드, 오류 발생 시 None.
    """
    try:
        # -m 옵션을 사용하여 모듈 형태로 실행
        cmd = [
            python_executable,
            "-m",
            classifier_module,
            target_image_dir,
            search_type,
            search_term,
            download_path
        ]
        
        project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
        env = os.environ.copy()
        env['PYTHONPATH'] = project_root + os.pathsep + env.get('PYTHONPATH', '')
        
        process = subprocess.Popen(cmd, cwd=project_root, env=env, text=True, encoding='utf-8', shell=False)
        stdout, stderr = process.communicate()
        
        if stop_event.is_set():
            process.terminate()
            append_status("분류 프로세스 중지됨.")
            return None
        
        if stdout:
            append_status(f"분류 출력:\n{stdout}")
        if stderr:
            append_status(f"분류 오류:\n{stderr}")
        return process.returncode
    except Exception as e:
        append_status(f"분류 스크립트 실행 중 오류: {e}")
        return None

def process_single_directory(target_image_dir, env, search_type, search_term, download_path, stop_event, append_status):
    """
    단일 디렉토리에 대해 분류를 실행합니다.
    """
    if not os.path.isdir(target_image_dir):
        append_status(f"오류: 대상 디렉토리 없음: {target_image_dir}")
        return False
    
    result = run_classification_process(
        env.python_executable,
        CLASSIFY_MODULE_NAME,
        target_image_dir,
        stop_event,
        append_status,
        search_type,
        search_term,
        download_path
    )
    
    if result is None:
        append_status("오류: 분류 프로세스 중지 또는 실행 실패")
        return False
    elif result == 0:
        return True
    else:
        append_status(f"인물분류 오류: {search_term}")
        return False

def process_upscaling(download_path, search_term, search_type, upscale, env, append_status):
    """
    업스케일링을 처리합니다.
    """
    if not upscale:
        return True
    
    # 인물 디렉토리 경로 생성
    if search_type == "hashtag":
        person_dir = os.path.join(download_path, '인물', f"hashtag_{search_term}")
    else:
        person_dir = os.path.join(download_path, '인물', f"user_{search_term}")
    
    if not os.path.isdir(person_dir):
        append_status(f"업스케일 스킵: 인물 디렉토리 없음")
        return True
    
    append_status(f"업스케일 시작: {search_term}")
    
    ret = run_upscaling(env.python_executable, person_dir, face_upscale, overall_scale)
    if ret == 0:
        append_status(f"업스케일 완료: {search_term}")
        return True
    else:
        append_status(f"업스케일 오류: {search_term}")
        return False

def process_images(root, append_status, download_directory_var, search_term, username, search_type, stop_event, upscale, classified=False):
    """
    지정된 디렉토리의 이미지에 대해 분류 프로세스를 실행합니다.
    
    매개변수:
        root: GUI 루트 창 등.
        append_status: 상태 기록 함수.
        download_directory_var: 다운로드 경로 변수.
        search_term (str): 검색어.
        username (str): 사용자 이름.
        search_type (str): 검색 유형 ('hashtag' 또는 'user').
        stop_event: 중지 이벤트.
        classified (bool): 이미지 분류 여부.
        upscale (bool): 업스케일 여부.
        
    반환:
        bool: 전체 분류 성공 여부.
    """
    download_path = download_directory_var.get().strip()
    
    # 환경 설정 및 검증
    env = ProcessingEnvironment()
    if not env.validate_environment(append_status):
        return False
    
    # 분류 시작 메시지
    append_status(f"{search_term} 분류 시작")
    
    # 대상 디렉토리 목록 생성
    target_dirs = DirectoryManager.get_target_directories(download_path, search_term, search_type, classified)
    
    # 각 디렉토리에 대해 분류 실행
    overall_success = True
    for target_image_dir in target_dirs:
        if not process_single_directory(target_image_dir, env, search_type, search_term, download_path, stop_event, append_status):
            overall_success = False
    
    # 업스케일링 처리
    if overall_success and upscale:
        if not process_upscaling(download_path, search_term, search_type, upscale, env, append_status):
            overall_success = False
    
    return overall_success
