# crawling/utils.py
import os
import cv2
import logging
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed

# 로깅 설정 (중앙 집중형)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def create_dir_if_not_exists(directory: str):
    """
    지정된 디렉토리가 없으면 생성합니다.
    """
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        logging.info(f"디렉토리 생성: {directory}")

def convert_webp_to_jpg(webp_path: str) -> str:
    """
    WEBP 파일을 JPEG로 변환하고 원본을 삭제합니다.
    
    반환:
        변환된 JPEG 파일 경로, 실패 시 None.
    """
    try:
        with Image.open(webp_path) as img:
            img = img.convert("RGB")
            jpg_path = os.path.splitext(webp_path)[0] + ".jpg"
            img.save(jpg_path, "JPEG")
        os.remove(webp_path)
        logging.info(f"WEBP -> JPEG 변환: {webp_path} -> {jpg_path}")
        return jpg_path
    except Exception as e:
        logging.error(f"WEBP -> JPEG 변환 실패 ({webp_path}): {e}")
        return None

def load_image(image_path: str):
    """
    OpenCV를 사용하여 이미지를 로드합니다.
    
    반환:
        (이미지 경로, 이미지 데이터) - 실패 시 이미지 데이터는 None.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("이미지 로드 실패")
        return image_path, img
    except Exception as e:
        logging.error(f"{image_path} 이미지 로드 오류: {e}")
        return image_path, None

def collect_image_paths(directory_path: str, recursive: bool = False) -> list:
    """
    지정한 디렉토리에서 이미지 파일 경로들을 수집합니다.
    WEBP 파일은 JPEG로 변환 후 포함합니다.
    
    반환:
        이미지 파일 경로 목록.
    """
    image_paths = []
    for root, dirs, files in os.walk(directory_path):
        if not recursive:
            dirs[:] = []
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            full_path = os.path.join(root, file)
            if ext == '.webp':
                converted = convert_webp_to_jpg(full_path)
                if converted:
                    image_paths.append(converted)
            elif ext in ('.jpg', '.jpeg', '.png'):
                image_paths.append(full_path)
    return image_paths

def load_images_concurrently(image_paths: list, max_workers: int = 8) -> dict:
    """
    이미지들을 병렬로 로드합니다.
    
    반환:
        {이미지 경로: 이미지 데이터} 형태의 딕셔너리.
    """
    image_cache = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(load_image, path): path for path in image_paths}
        for future in as_completed(futures):
            path, img = future.result()
            if img is not None:
                image_cache[path] = img
    return image_cache
