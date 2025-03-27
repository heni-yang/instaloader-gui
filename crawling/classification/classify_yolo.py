# crawling/classification/classify_yolo.py
"""
독립 실행형 YOLO 이미지 분류 스크립트.
타겟 디렉토리의 이미지를 YOLO 세그멘테이션 및 포즈 모델로 처리하여
이미지를 'human', 'body'(얼굴 가림), 'nonhuman' 등으로 분류합니다.
사용법:
    테스트 모드 (어노테이션 포함): python classify_yolo.py <target_image_dir>
    테스트 모드 (원본 복사):       python classify_yolo.py <target_image_dir> --raw
    생산 모드:                     python classify_yolo.py <target_image_dir> <search_type> <search_term> <download_path>
"""
import os
import sys
import shutil
import logging
import math
import time
import copy
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

import cv2
import numpy as np
import torch
from PIL import Image
from shapely.geometry import Polygon, box as shapely_box
from ultralytics import YOLO
from crawling.utils import convert_webp_to_jpg, collect_image_paths, load_images_concurrently, logging

# CUDA 사용 시 GPU 메모리 사용을 60%로 제한
if torch.cuda.is_available():
    torch.cuda.set_per_process_memory_fraction(0.6, 0)

# ===================================================
# 상수 및 모델 파일 경로 설정
# ===================================================
PERSON_CONF_THRESHOLD_YOLO = 0.98
PERSON_SIZE_THRESHOLD = 0.13

FACE_CONF_THRESHOLD_YOLO_POSE = 0.51
FACE_SIZE_THRESHOLD = 0.00069

BODY_CONF_THRESHOLD_YOLO_POSE = 0.1
BODY_SIZE_THRESHOLD = 0.005

KEYPOINT_CONFIDENCE_THRESHOLD = 0.5

TARGET_THROUGHPUT = 50  # 목표: 50 이미지/초
MAX_YOLO_BATCH_SIZE = 4
MIN_YOLO_BATCH_SIZE = 4

DIFF_RATIO_THRESHOLD = 1.0
MIN_DIFF_RATIO_IMPROVEMENT = 0.05

BATCH_THROUGHPUT_HISTORY_LEN = 3

DEBUG_ANNOTATION = False
DEBUG_DIR = "debug_annotations"
if DEBUG_ANNOTATION:
    os.makedirs(DEBUG_DIR, exist_ok=True)

script_dir = os.path.dirname(os.path.abspath(__file__))
YOLO_MODEL_NAME = "yolo11l-seg.pt"
YOLO_POSE_MODEL_NAME = "yolo11x-pose.pt"
WEIGHTS_PATH = os.path.join(script_dir, "yolo_model", YOLO_MODEL_NAME)
POSE_WEIGHTS = os.path.join(script_dir, "yolo_model", YOLO_POSE_MODEL_NAME)

# COCO 클래스 이름
COCO_CLASSES = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane",
    5: "bus", 6: "train", 7: "truck", 8: "boat", 9: "traffic light",
    10: "fire hydrant", 11: "stop sign", 12: "parking meter", 13: "bench",
    14: "bird", 15: "cat", 16: "dog", 17: "horse", 18: "sheep",
    19: "cow", 20: "elephant", 21: "bear", 22: "zebra", 23: "giraffe",
    24: "backpack", 25: "umbrella", 26: "handbag", 27: "tie", 28: "suitcase",
    29: "frisbee", 30: "skis", 31: "snowboard", 32: "sports ball", 33: "kite",
    34: "baseball bat", 35: "baseball glove", 36: "skateboard", 37: "surfboard",
    38: "tennis racket", 39: "bottle", 40: "wine glass", 41: "cup", 42: "fork",
    43: "knife", 44: "spoon", 45: "bowl", 46: "banana", 47: "apple",
    48: "sandwich", 49: "orange", 50: "broccoli", 51: "carrot", 52: "hot dog",
    53: "pizza", 54: "donut", 55: "cake", 56: "chair", 57: "couch",
    58: "potted plant", 59: "bed", 60: "dining table", 61: "toilet", 62: "tv",
    63: "laptop", 64: "mouse", 65: "remote", 66: "keyboard", 67: "cell phone",
    68: "microwave", 69: "oven", 70: "toaster", 71: "sink", 72: "refrigerator",
    73: "book", 74: "clock", 75: "vase", 76: "scissors", 77: "teddy bear",
    78: "hair drier", 79: "toothbrush"
}

CLASSIFICATION_FACE_COVERING_CLASSES = list(range(9, 12)) + list(range(14, 55)) + list(range(59, 66)) + list(range(68, 80)) + [67]
REMAINING_CLASSES = set(range(80)) - ({0} | set(CLASSIFICATION_FACE_COVERING_CLASSES))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ===================================================
# 헬퍼 함수: 이미지 전처리, 로딩 등
# (utils.py에 일부 기능을 위임)
# ===================================================
def get_seg_masks(seg_result):
    if hasattr(seg_result, 'masks') and seg_result.masks is not None and hasattr(seg_result.masks, 'xy'):
        return seg_result.masks.xy
    return None

# 이하 나머지 함수들은 앞서 제공한 코드와 유사하며, 한국어 주석 포함
# (draw_keypoints, draw_skeleton, extract_pose_keypoints, calculate_distance, estimate_face_area,
#  estimate_body_area, select_pose_by_bbox_area, compute_polygon_box_iou, select_pose_with_polygon_iou,
#  build_single_pose_result, logic_face, logic_body, polygon_area, polygon_intersection_area, compute_intersection_area,
#  check_face_covering_overlap 등)
# … (코드 생략, 앞서 제공한 내용 참조)

# ===================================================
# 이미지 분류 및 어노테이션 처리
# ===================================================
def classify_single_image(image_path, preloaded_img, seg_result, pose_result,
                          human_dir, body_dir, non_human_dir, pose_model,
                          mode="production", save_annotation=True):
    # 이 함수의 상세 로직은 앞서 제공한 코드와 유사하며, 한국어 주석 추가됨
    # … (코드 생략, 앞서 제공한 내용을 참조)
    pass  # 실제 구현 코드 삽입

def update_batch_size_optimal(current_bs, current_throughput, state, throughput_history, tolerance=0.1, step=2):
    # 배치 크기 동적 조절 로직 (앞서 제공한 내용 참고)
    pass  # 실제 구현 코드 삽입

def process_batch(batch_paths, image_cache, seg_model, pose_model):
    # 배치 처리 함수 (앞서 제공한 내용 참고)
    pass  # 실제 구현 코드 삽입

def process_images(image_paths, seg_model, pose_model, human_dir, body_dir, non_human_dir,
                   mode="production", save_annotation=True):
    # 전체 이미지 처리 함수 (앞서 제공한 내용 참고)
    pass  # 실제 구현 코드 삽입

def main():
    # 메인 함수: 테스트 모드 및 생산 모드 지원 (앞서 제공한 내용 참고)
    if len(sys.argv) in [2, 3]:
        target_dir = sys.argv[1]
        raw_mode = (len(sys.argv) == 3 and sys.argv[2] == "--raw")
        human_dir = os.path.join(target_dir, "인물")
        non_human_dir = os.path.join(target_dir, "비인물")
        body_dir = os.path.join(non_human_dir, "body")
        os.makedirs(human_dir, exist_ok=True)
        os.makedirs(non_human_dir, exist_ok=True)
        os.makedirs(body_dir, exist_ok=True)
        image_paths = collect_image_paths(target_dir, recursive=False)
        seg_model = YOLO(WEIGHTS_PATH)
        pose_model = YOLO(POSE_WEIGHTS)
        process_images(
            image_paths,
            seg_model,
            pose_model,
            human_dir,
            body_dir,
            non_human_dir,
            mode="test",
            save_annotation=(not raw_mode)
        )
    elif len(sys.argv) == 5:
        target_dir, search_type, search_term, download_path = sys.argv[1:5]
        human_dir = os.path.join(download_path, "인물", f"{search_type}_{search_term}")
        non_human_dir = os.path.join(download_path, "비인물", f"{search_type}_{search_term}")
        body_dir = os.path.join(non_human_dir, "body")
        os.makedirs(human_dir, exist_ok=True)
        os.makedirs(non_human_dir, exist_ok=True)
        os.makedirs(body_dir, exist_ok=True)
        image_paths = collect_image_paths(target_dir, recursive=True)
        seg_model = YOLO(WEIGHTS_PATH)
        pose_model = YOLO(POSE_WEIGHTS)
        process_images(
            image_paths,
            seg_model,
            pose_model,
            human_dir,
            body_dir,
            non_human_dir,
            mode="production",
            save_annotation=False
        )
    else:
        print("Usage:")
        print("  테스트 모드 (어노테이션 포함): python classify_yolo.py <target_image_dir>")
        print("  테스트 모드 (원본 복사):      python classify_yolo.py <target_image_dir> --raw")
        print("  생산 모드:                  python classify_yolo.py <target_image_dir> <search_type> <search_term> <download_path>")
        sys.exit(1)

if __name__ == "__main__":
    main()
