import os
import subprocess

# 분류 스크립트 관련 설정 상수
#CLASSIFY_SCRIPT_NAME = 'classify_yolo.py'
CLASSIFY_SCRIPT_NAME = 'yolo_test9_latest.py'
# classification 디렉토리에 스크립트가 있다고 가정
CLASSIFY_SCRIPT_REL_PATH = os.path.join('classification', CLASSIFY_SCRIPT_NAME)

def run_classification_process(python_executable, classifier_script, target_image_dir, stop_event, append_status, search_type, search_term, download_path):
    try:
        cmd = [
            python_executable,
            classifier_script,
            target_image_dir,
            search_type,
            search_term,
            download_path
        ]
        
        process = subprocess.Popen(
            cmd,
            text=True,
            encoding='utf-8',
            shell=False,
        )
        
        append_status(f"분류 프로세스 시작: {' '.join([python_executable, classifier_script, target_image_dir])}")
        
        stdout, stderr = process.communicate()

        if stop_event.is_set():
            process.terminate()
            append_status("분류 프로세스가 중지되었습니다.")
            return None

        if stdout:
            append_status(f"분류 프로세스 출력:\n{stdout}")
        if stderr:
            append_status(f"분류 프로세스 오류:\n{stderr}")
        return process.returncode
    except Exception as e:
        append_status(f"분류 스크립트를 실행하는 중 에러 발생: {e}")
        return None

def classify_images(root, append_status, download_directory_var, search_term, username, search_type, stop_event, classified=False):
    download_path = download_directory_var.get().strip()
    target_dirs = []

    if classified:
        # 인물 디렉토리는 그대로 추가
        if search_type == "hashtag":
            person_dir = os.path.join(download_path, '인물', f"hashtag_{search_term}")
        else:
            person_dir = os.path.join(download_path, '인물', f"user_{search_term}")
        target_dirs.append(person_dir)

        # 비인물 디렉토리: 상위 폴더만 포함하도록 수정
        if search_type == "hashtag":
            non_person_base = os.path.join(download_path, '비인물', f"hashtag_{search_term}")
        else:
            non_person_base = os.path.join(download_path, '비인물', f"user_{search_term}")

        if os.path.isdir(non_person_base):
            # 기존 하위 폴더까지 순회하여 추가하던 부분은 주석 처리합니다.
            # for current_dir, subdirs, files in os.walk(non_person_base):
            #     # current_dir: 하위 디렉토리 포함
            #     target_dirs.append(current_dir)
            target_dirs.append(non_person_base)
        else:
            append_status(f"오류: 분류할 비인물 디렉토리가 존재하지 않습니다: {non_person_base}")
    else:
        # 기본 분류: 미분류 이미지가 저장된 디렉토리 (unclassified)
        if search_type == "hashtag":
            target_dirs.append(os.path.join(download_path, 'unclassified', 'hashtag', search_term, 'Image'))
        else:
            target_dirs.append(os.path.join(download_path, 'unclassified', 'ID', search_term, 'Image'))

    overall_success = True

    # 현재 파일(classifier.py)에서 스크립트 위치를 절대경로로 변환
    script_dir = os.path.dirname(os.path.abspath(__file__))
    classifier_script = os.path.join(script_dir, 'classification', CLASSIFY_SCRIPT_NAME)

    # OS별 파이썬 실행 파일 경로 설정
    if os.name == 'nt':
        python_executable = os.path.join(script_dir, 'classification', 'classify_venv', 'Scripts', 'python.exe')
    else:
        python_executable = os.path.join(script_dir, 'classification', 'classify_venv', 'bin', 'python')

    if not os.path.exists(python_executable):
        append_status(f"오류: 분류 가상 환경의 Python 실행 파일을 찾을 수 없습니다: {python_executable}")
        return False

    if not os.path.isfile(classifier_script):
        append_status(f"오류: 분류 스크립트를 찾을 수 없습니다: {classifier_script}")
        return False

    for target_image_dir in target_dirs:
        if not os.path.isdir(target_image_dir):
            append_status(f"오류: 분류할 디렉토리가 존재하지 않습니다: {target_image_dir}")
            overall_success = False
            continue

        append_status(f"[{search_type.upper()}] {search_term} 디렉토리 분류 시작: {target_image_dir}")
        print(f"[{search_type.upper()}] {search_term} 디렉토리 분류 시작: {target_image_dir}")

        result = run_classification_process(
            python_executable,
            classifier_script,
            target_image_dir,
            stop_event,
            append_status,
            search_type,
            search_term,
            download_path
        )

        if result is None:
            append_status("오류: 분류 프로세스가 중지되었거나 실행에 실패했습니다.")
            overall_success = False
        elif result == 0:
            append_status(f"[{search_type.upper()}] {search_term} 디렉토리 분류 완료: {target_image_dir}")
        else:
            append_status(f"[{search_type.upper()}] {search_term} 디렉토리 분류 중 오류 발생: {target_image_dir}")
            overall_success = False

    return overall_success
