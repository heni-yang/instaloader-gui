# crawling/post_processing.py
import os
import subprocess
from crawling.utils import logging

# 분류 스크립트 파일명 및 모듈 이름
CLASSIFY_SCRIPT_NAME = 'classify_yolo.py'
CLASSIFY_SCRIPT_REL_PATH = os.path.join('processing', CLASSIFY_SCRIPT_NAME)
CLASSIFY_MODULE_NAME = "crawling.processing." + os.path.splitext(CLASSIFY_SCRIPT_NAME)[0]

face_upscale = 2
overall_scale = 2

def run_upscaling(python_executable, input_image_dir, face_upscale, overall_scale):
    """
    업스케일링 스크립트를 모듈 형식으로 호출합니다 (upscaler.py).
    """
    module_name = "crawling.processing.upscaler"
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
        
        append_status(f"분류 프로세스 시작: {' '.join(cmd)}")
        project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
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
    target_dirs = []
    
    if classified:
        if search_type == "hashtag":
            person_dir = os.path.join(download_path, '인물', f"hashtag_{search_term}")
        else:
            person_dir = os.path.join(download_path, '인물', f"user_{search_term}")
        target_dirs.append(person_dir)
        
        if search_type == "hashtag":
            non_person_base = os.path.join(download_path, '비인물', f"hashtag_{search_term}")
        else:
            non_person_base = os.path.join(download_path, '비인물', f"user_{search_term}")
        if os.path.isdir(non_person_base):
            target_dirs.append(non_person_base)
        else:
            append_status(f"오류: 비인물 디렉토리 없음: {non_person_base}")
    else:
        if search_type == "hashtag":
            target_dirs.append(os.path.join(download_path, 'unclassified', 'hashtag', search_term))
        else:
            target_dirs.append(os.path.join(download_path, 'unclassified', 'ID', search_term))
    
    overall_success = True
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
    # 파일 존재 여부는 기존 방식대로 검사 (모듈 실행과는 별개)
    classifier_script_file = os.path.join(script_dir, 'processing', CLASSIFY_SCRIPT_NAME)
    
    if os.name == 'nt':
        python_executable = os.path.join(parent_dir, 'venv', 'classify_venv', 'Scripts', 'python.exe')
    else:
        python_executable = os.path.join(parent_dir, 'venv', 'classify_venv', 'bin', 'python')
    
    if not os.path.exists(python_executable):
        append_status(f"오류: 가상환경 Python 실행 파일 없음: {python_executable}")
        return False
    if not os.path.isfile(classifier_script_file):
        append_status(f"오류: 분류 스크립트 없음: {classifier_script_file}")
        return False
    
    for target_image_dir in target_dirs:
        if not os.path.isdir(target_image_dir):
            append_status(f"오류: 대상 디렉토리 없음: {target_image_dir}")
            overall_success = False
            continue
        
        append_status(f"[{search_type.upper()}] {search_term} 분류 시작: {target_image_dir}")
        result = run_classification_process(
            python_executable,
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
            overall_success = False
        elif result == 0:
            append_status(f"[{search_type.upper()}] {search_term} 분류 완료: {target_image_dir}")
        else:
            append_status(f"[{search_type.upper()}] {search_term} 분류 오류: {target_image_dir}")
            overall_success = False

    if search_type == "hashtag":
        person_dir = os.path.join(download_path, '인물', f"hashtag_{search_term}")
    else:
        person_dir = os.path.join(download_path, '인물', f"user_{search_term}")
            
    if upscale and os.path.isdir(person_dir):
        append_status(f"[{search_type.upper()}] {search_term} 업스케일 시작: {person_dir}")
        # 지원하는 이미지 확장자 목록
        supported_ext = ('.jpg', '.jpeg', '.png')
        ret = run_upscaling(python_executable, person_dir, face_upscale, overall_scale)
        if ret == 0:
            append_status(f"업스케일링 완료: {person_dir}")
        else:
            append_status(f"업스케일링 오류: {person_dir}")
            overall_success = False

    
    return overall_success
