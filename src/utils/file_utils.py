# crawling/utils.py
import os
import logging
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed

# 로깅 설정 (중앙 집중형)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

# cv2 조건부 import
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logging.warning("cv2 모듈을 사용할 수 없습니다. 이미지 처리 기능이 제한됩니다.")

class ImageProcessor:
    """
    이미지 처리 관련 기능을 제공하는 클래스입니다.
    """
    
    @staticmethod
    def convert_webp_to_jpg(webp_path: str) -> str:
        """
        WEBP 파일을 JPEG로 변환하고 원본을 삭제합니다.
        
        매개변수:
            webp_path (str): WEBP 파일 경로
            
        반환:
            str: 변환된 JPEG 파일 경로, 실패 시 None
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
    
    @staticmethod
    def load_image(image_path: str):
        """
        OpenCV를 사용하여 이미지를 로드합니다.
        
        매개변수:
            image_path (str): 이미지 파일 경로
            
        반환:
            tuple: (이미지 경로, 이미지 데이터) - 실패 시 이미지 데이터는 None
        """
        if not CV2_AVAILABLE:
            logging.error(f"cv2 모듈이 없어 이미지를 로드할 수 없습니다: {image_path}")
            return image_path, None
        
        try:
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError("이미지 로드 실패")
            return image_path, img
        except Exception as e:
            logging.error(f"{image_path} 이미지 로드 오류: {e}")
            return image_path, None

class DirectoryManager:
    """
    디렉토리 및 파일 관리 기능을 제공하는 클래스입니다.
    """
    
    @staticmethod
    def create_dir_if_not_exists(directory: str):
        """
        지정된 디렉토리가 없으면 생성합니다.
        
        매개변수:
            directory (str): 생성할 디렉토리 경로
        """
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            logging.info(f"디렉토리 생성: {directory}")
    
    @staticmethod
    def collect_image_paths(directory_path: str, recursive: bool = False) -> list:
        """
        지정한 디렉토리에서 이미지 파일 경로들을 수집합니다.
        WEBP 파일은 JPEG로 변환 후 포함합니다.
        
        매개변수:
            directory_path (str): 검색할 디렉토리 경로
            recursive (bool): 하위 디렉토리 포함 여부
            
        반환:
            list: 이미지 파일 경로 목록
        """
        image_paths = []
        for root, dirs, files in os.walk(directory_path):
            if not recursive:
                dirs[:] = []
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                full_path = os.path.join(root, file)
                if ext == '.webp':
                    converted = ImageProcessor.convert_webp_to_jpg(full_path)
                    if converted:
                        image_paths.append(converted)
                elif ext in ('.jpg', '.jpeg', '.png'):
                    image_paths.append(full_path)
        return image_paths

class ImageLoader:
    """
    이미지 로딩 관련 기능을 제공하는 클래스입니다.
    """
    
    @staticmethod
    def load_images_concurrently(image_paths: list, max_workers: int = 8) -> dict:
        """
        이미지들을 병렬로 로드합니다.
        
        매개변수:
            image_paths (list): 이미지 경로 목록
            max_workers (int): 최대 워커 수
            
        반환:
            dict: {이미지 경로: 이미지 데이터} 형태의 딕셔너리
        """
        image_cache = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(ImageProcessor.load_image, path): path for path in image_paths}
            for future in as_completed(futures):
                path, img = future.result()
                if img is not None:
                    image_cache[path] = img
        return image_cache

# 하위 호환성을 위한 함수들
def create_dir_if_not_exists(directory: str):
    """
    지정된 디렉토리가 없으면 생성합니다. (하위 호환성)
    """
    DirectoryManager.create_dir_if_not_exists(directory)

def convert_webp_to_jpg(webp_path: str) -> str:
    """
    WEBP 파일을 JPEG로 변환하고 원본을 삭제합니다. (하위 호환성)
    """
    return ImageProcessor.convert_webp_to_jpg(webp_path)

def load_image(image_path: str):
    """
    OpenCV를 사용하여 이미지를 로드합니다. (하위 호환성)
    """
    return ImageProcessor.load_image(image_path)

def collect_image_paths(directory_path: str, recursive: bool = False) -> list:
    """
    지정한 디렉토리에서 이미지 파일 경로들을 수집합니다. (하위 호환성)
    """
    return DirectoryManager.collect_image_paths(directory_path, recursive)

def load_images_concurrently(image_paths: list, max_workers: int = 8) -> dict:
    """
    이미지들을 병렬로 로드합니다. (하위 호환성)
    """
    return ImageLoader.load_images_concurrently(image_paths, max_workers)
