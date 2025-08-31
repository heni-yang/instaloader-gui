# crawling/processing/classify_yolo.py
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
# if torch.cuda.is_available():
    # torch.cuda.set_per_process_memory_fraction(0.6, 0)

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
project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
YOLO_MODEL_NAME = "yolo11l-seg.pt"
YOLO_POSE_MODEL_NAME = "yolo11x-pose.pt"
WEIGHTS_PATH = os.path.join(project_root, "models", "classification", YOLO_MODEL_NAME)
POSE_WEIGHTS = os.path.join(project_root, "models", "classification", YOLO_POSE_MODEL_NAME)

# COCO 기준 키포인트 인덱스
HUMAN_KEYPOINTS = {'nose': 0, 'left_eye': 1, 'right_eye': 2, 'left_ear': 3, 'right_ear': 4}
# NON_HUMAN_KEYPOINTS: 실제 키포인트 인덱스 (필요에 따라 수정)
NON_HUMAN_KEYPOINTS = list(range(5, 17))

# 몸통 스켈레톤 연결선
body_skeleton = [
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16)
]

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

##############################################
# 포즈 및 시각화 관련 함수
##############################################
def extract_pose_keypoints(pose_result):
    if (pose_result is not None and hasattr(pose_result, 'keypoints') and 
        pose_result.keypoints is not None and pose_result.keypoints.data.numel() > 0):
        return pose_result.keypoints.data.cpu().numpy()[0]
    return None

def draw_keypoints(img, keypoints, color=(0, 0, 255)):
    for x, y, conf in keypoints:
        if conf > KEYPOINT_CONFIDENCE_THRESHOLD:
            cv2.circle(img, (int(x), int(y)), 3, color, -1)
    return img

def draw_skeleton(img, keypoints, skeleton, color=(0, 255, 255), thickness=2):
    for i, j in skeleton:
        if i < len(keypoints) and j < len(keypoints):
            kp1, kp2 = keypoints[i], keypoints[j]
            if kp1[2] > KEYPOINT_CONFIDENCE_THRESHOLD and kp2[2] > KEYPOINT_CONFIDENCE_THRESHOLD:
                cv2.line(img, (int(kp1[0]), int(kp1[1])), (int(kp2[0]), int(kp2[1])), color, thickness)
    return img

def draw_face_skeleton_extended(img, face_keypoints, threshold=0.5):
    nose = face_keypoints[HUMAN_KEYPOINTS['nose']]
    left_eye = face_keypoints[HUMAN_KEYPOINTS['left_eye']]
    right_eye = face_keypoints[HUMAN_KEYPOINTS['right_eye']]
    if nose[2] > threshold and left_eye[2] > threshold and right_eye[2] > threshold:
        cv2.line(img, (int(nose[0]), int(nose[1])), (int(left_eye[0]), int(left_eye[1])), (255, 255, 0), 2)
        cv2.line(img, (int(nose[0]), int(nose[1])), (int(right_eye[0]), int(right_eye[1])), (255, 255, 0), 2)
    return img

def calculate_distance(kp1, kp2):
    return math.sqrt((kp2[0] - kp1[0])**2 + (kp2[1] - kp1[1])**2)

def estimate_face_area(nose, left_eye, right_eye):
    a = calculate_distance(left_eye, right_eye) / 2
    b = (calculate_distance(nose, left_eye) + calculate_distance(nose, right_eye)) / 4
    return math.pi * a * b if a and b else 0

def estimate_body_area(keypoints_data):
    body_kps = [kp for i, kp in enumerate(keypoints_data)
                if i in NON_HUMAN_KEYPOINTS and kp is not None and len(kp) >= 3 and kp[2] >= KEYPOINT_CONFIDENCE_THRESHOLD]
    if not body_kps:
        return 0
    xs = [kp[0] for kp in body_kps]
    ys = [kp[1] for kp in body_kps]
    return (max(xs) - min(xs)) * (max(ys) - min(ys))

##############################################
# 박스 및 폴리곤 관련 함수
##############################################
def select_pose_by_bbox_area(pose_result, seg_box, area_diff_ratio_thresh=DIFF_RATIO_THRESHOLD):
    if not (hasattr(pose_result, 'boxes') and pose_result.boxes is not None and
            pose_result.boxes.xyxy is not None and pose_result.boxes.xyxy.shape[0] > 0):
        return None

    seg_area = max(seg_box[2] - seg_box[0], 0) * max(seg_box[3] - seg_box[1], 0)
    if seg_area <= 0:
        return None

    boxes = pose_result.boxes.xyxy.cpu().numpy()
    best_idx, best_diff = None, float('inf')
    for i in range(boxes.shape[0]):
        x1, y1, x2, y2 = boxes[i]
        pose_area = max(x2 - x1, 0) * max(y2 - y1, 0)
        if pose_area <= 0:
            continue
        diff_ratio = abs(pose_area - seg_area) / seg_area
        if diff_ratio < best_diff:
            best_diff = diff_ratio
            best_idx = i
    # hysteresis: 변화가 MIN_DIFF_RATIO_IMPROVEMENT 이상일 때만 업데이트
    if best_idx is not None and best_diff <= area_diff_ratio_thresh - MIN_DIFF_RATIO_IMPROVEMENT:
        return best_idx
    return None

def compute_polygon_box_iou(seg_poly, box):
    try:
        poly_seg = Polygon(seg_poly).buffer(0)
        box_poly = shapely_box(*box).buffer(0)
        if not poly_seg.is_valid or not box_poly.is_valid:
            logging.warning("Invalid geometry in compute_polygon_box_iou.")
            return 0
        inter_area = poly_seg.intersection(box_poly).area
        union_area = poly_seg.area + box_poly.area - inter_area
        return inter_area / union_area if union_area > 0 else 0
    except Exception as e:
        logging.error(f"Error in compute_polygon_box_iou: {e}")
        return 0

def select_pose_with_polygon_iou(pose_result, seg_poly, iou_thresh=0.1):
    if not (hasattr(pose_result, 'boxes') and pose_result.boxes is not None and
            pose_result.boxes.xyxy is not None and pose_result.boxes.xyxy.shape[0] > 0):
        return None
    boxes = pose_result.boxes.xyxy.cpu().numpy()
    best_idx, best_iou = -1, 0
    for i in range(boxes.shape[0]):
        iou_val = compute_polygon_box_iou(seg_poly, boxes[i])
        if iou_val > best_iou:
            best_iou = iou_val
            best_idx = i
    return best_idx if best_idx != -1 and best_iou >= iou_thresh else None

def build_single_pose_result(original_pose_result, best_idx):
    single_pose = copy.deepcopy(original_pose_result)
    if single_pose.boxes is not None and best_idx < single_pose.boxes.xyxy.shape[0]:
        single_pose.boxes = single_pose.boxes[best_idx:best_idx+1]
        if hasattr(single_pose.boxes, 'orig_idxs'):
            single_pose.boxes.orig_idxs = single_pose.boxes.orig_idxs[best_idx:best_idx+1]
    else:
        single_pose.boxes = None

    if hasattr(single_pose, 'keypoints') and single_pose.keypoints is not None:
        single_pose.keypoints = single_pose.keypoints[best_idx:best_idx+1] if single_pose.keypoints.shape[0] > best_idx else None
    if hasattr(single_pose, 'masks') and single_pose.masks is not None:
        if single_pose.masks.data.shape[0] > best_idx:
            single_pose.masks.data = single_pose.masks.data[best_idx:best_idx+1]
            if hasattr(single_pose.masks, 'xy') and len(single_pose.masks.xy) > best_idx:
                single_pose.masks.xy = [single_pose.masks.xy[best_idx]]
        else:
            single_pose.masks = None
    return single_pose

##############################################
# 얼굴/몸통 검출 로직
##############################################
def logic_face(pose_result, model_input_area, keypoints):
    if keypoints is None:
        logging.info("Face detection: 키포인트 결과가 없음.")
        return []
    nose = keypoints[HUMAN_KEYPOINTS['nose']]
    left_eye = keypoints[HUMAN_KEYPOINTS['left_eye']]
    right_eye = keypoints[HUMAN_KEYPOINTS['right_eye']]
    logging.info(f"Face detection: nose={nose[2]:.2f}, left_eye={left_eye[2]:.2f}, right_eye={right_eye[2]:.2f}")
    if nose[2] < FACE_CONF_THRESHOLD_YOLO_POSE or left_eye[2] < FACE_CONF_THRESHOLD_YOLO_POSE or right_eye[2] < FACE_CONF_THRESHOLD_YOLO_POSE:
        return []
    face_area = estimate_face_area(nose, left_eye, right_eye)
    face_ratio = face_area / model_input_area
    logging.info(f"Face detection: 면적 비율={face_ratio:.4f} (임계값: {FACE_SIZE_THRESHOLD})")
    return [('face', face_ratio, None, 'face_yolo')] if face_ratio >= FACE_SIZE_THRESHOLD else []

def logic_body(pose_result, model_input_area, keypoints):
    if keypoints is None:
        logging.info("Body detection: 키포인트 결과 없음.")
        return []
    ESSENTIAL_BODY_KEYPOINTS = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    essential = [kp for i, kp in enumerate(keypoints)
                 if i in ESSENTIAL_BODY_KEYPOINTS and kp[2] >= BODY_CONF_THRESHOLD_YOLO_POSE]
    if len(essential) < 4:
        logging.info(f"Body detection: 필수 키포인트 부족 (검출 {len(essential)}개)")
        return []
    body_area_val = estimate_body_area(keypoints)
    body_ratio = body_area_val / model_input_area
    logging.info(f"Body detection: 면적 비율={body_ratio:.4f} (임계값: {BODY_SIZE_THRESHOLD})")
    return [('body', body_ratio, None, 'body_yolo')] if body_ratio >= BODY_SIZE_THRESHOLD else []

##############################################
# 얼굴 가림 판별 함수
##############################################
def polygon_area(polygon_coords):
    try:
        return Polygon(polygon_coords).area
    except Exception as e:
        logging.error(f"폴리곤 면적 계산 오류: {e}")
        return 0

def polygon_intersection_area(polygon_coords, face_bbox):
    try:
        poly = Polygon(polygon_coords)
        face_rect = shapely_box(*face_bbox)
        return poly.intersection(face_rect).area
    except Exception as e:
        logging.error(f"폴리곤 교집합 계산 오류: {e}")
        return 0

def compute_intersection_area(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    if xB < xA or yB < yA:
        return 0
    return (xB - xA) * (yB - yA)

def check_face_covering_overlap(seg_result, face_bbox, person_index, full_img_area, overlap_threshold=0.3, max_obj_area_ratio=0.8):
    if not (hasattr(seg_result, 'boxes') and seg_result.boxes is not None):
        return False
    try:
        cls_array = seg_result.boxes.cls.cpu().numpy() if hasattr(seg_result.boxes.cls, 'cpu') else np.array(seg_result.boxes.cls)
    except Exception as e:
        logging.error(f"클래스 정보 추출 오류: {e}")
        return False

    face_area = (face_bbox[2] - face_bbox[0]) * (face_bbox[3] - face_bbox[1])
    if face_area <= 0:
        return False
    # get_seg_masks() 사용
    seg_masks = get_seg_masks(seg_result)
    use_polygon = seg_masks is not None

    for i, cls_id in enumerate(cls_array):
        if i <= person_index:
            continue
        if int(cls_id) in CLASSIFICATION_FACE_COVERING_CLASSES:
            if use_polygon and i < len(seg_masks):
                polygon = np.array(seg_masks[i], dtype=np.float32)
                obj_area = polygon_area(polygon)
                inter_area = polygon_intersection_area(polygon, face_bbox)
            else:
                try:
                    box = seg_result.boxes.xyxy[i]
                    obj_box = [int(val) for val in box.tolist()]
                    obj_area = (obj_box[2] - obj_box[0]) * (obj_box[3] - obj_box[1])
                    inter_area = compute_intersection_area(face_bbox, obj_box)
                except Exception as e:
                    logging.error(f"박스 처리 오류: {e}")
                    continue
            if (obj_area / full_img_area) >= max_obj_area_ratio:
                logging.info(f"객체 (idx={i}, class={int(cls_id)}) 면적 비율 {obj_area/full_img_area:.2f} >= {max_obj_area_ratio}, 제외")
                continue
            if inter_area / face_area >= overlap_threshold:
                logging.info(f"인물 뒤 객체 (idx={i}, class={int(cls_id)})와 얼굴 겹침 비율 {inter_area/face_area:.2f}")
                return True
    return False

# ===================================================
# 이미지 분류 및 어노테이션 처리
# ===================================================
def classify_single_image(image_path, preloaded_img, seg_result, pose_result,
                          human_dir, body_dir, non_human_dir, pose_model,
                          mode="production", save_annotation=True):
    if preloaded_img is None:
        logging.error(f"캐시 이미지 없음: {image_path}")
        return
        
    if seg_result is None:
        logging.error(f"세그멘테이션 결과 없음: {image_path}")
        return
    # seg_result.masks 검사
    if not (hasattr(seg_result, 'masks') and seg_result.masks is not None and
            hasattr(seg_result.masks, 'xy') and seg_result.masks.xy is not None):
        logging.warning(f"세그멘테이션 마스크 정보가 없음: {image_path}")

    orig = preloaded_img.copy()
    input_h, input_w = orig.shape[:2]
    original_area = input_w * input_h

    # (1) 세그멘테이션 결과 검증 및 인물 영역 선택
    max_person_area = 0
    max_person_index = None
    resized_H = resized_W = 0
    if hasattr(seg_result, 'masks') and seg_result.masks is not None and seg_result.masks.data is not None:
        masks_np = seg_result.masks.data.cpu().numpy() if hasattr(seg_result.masks.data, 'cpu') else seg_result.masks.data.numpy()
        if masks_np.ndim >= 3:
            resized_H, resized_W = masks_np.shape[1:3]
            try:
                cls_array = seg_result.boxes.cls.cpu().numpy() if hasattr(seg_result.boxes.cls, 'cpu') else np.array(seg_result.boxes.cls)
            except Exception as e:
                logging.error(f"세그 클래스 추출 오류: {e}")
                cls_array = []
            person_indices = [i for i, cls_id in enumerate(cls_array) if int(cls_id) == 0]
            for i in person_indices:
                area = np.sum(masks_np[i] > 0.5)
                if area > max_person_area:
                    max_person_area = area
                    max_person_index = i

    person_ratio = 0
    if resized_H > 0 and resized_W > 0:
        scale_factor = (input_w / resized_W) * (input_h / resized_H)
        original_person_area = max_person_area * scale_factor
        person_ratio = original_person_area / original_area
        logging.info(f"인물 면적 비율: {person_ratio*100:.2f}%")
    else:
        logging.info("인물 마스크 정보 없음.")

    pose_input_area = original_area

    # (2) 인물 영역이 충분하면 크롭 후 pose 재추론 수행
    if person_ratio >= PERSON_SIZE_THRESHOLD and max_person_index is not None and hasattr(seg_result, 'boxes') and seg_result.boxes is not None:
        box = seg_result.boxes.xyxy[max_person_index]
        x1, y1, x2, y2 = [int(val) for val in box.tolist()]
        w_box, h_box = x2 - x1, y2 - y1
        margin_factor = 0.02
        margin_x, margin_y = int(w_box * margin_factor), int(h_box * margin_factor)
        x1, y1 = max(0, x1 - margin_x), max(0, y1 - margin_y)
        x2, y2 = min(orig.shape[1], x2 + margin_x), min(orig.shape[0], y2 + margin_y)
        logging.info(f"크롭 영역: ({x1}, {y1}) ~ ({x2}, {y2}), margin: {margin_factor}")
        cropped = orig[y1:y2, x1:x2]
        desired_size = 640
        h_cropped, w_cropped = cropped.shape[:2]
        scale = desired_size / max(w_cropped, h_cropped)
        new_w, new_h = int(w_cropped * scale), int(h_cropped * scale)
        resized = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        delta_w, delta_h = desired_size - new_w, desired_size - new_h
        top, bottom = delta_h // 2, delta_h - (delta_h // 2)
        left_pad, right_pad = delta_w // 2, delta_w - (delta_w // 2)
        resized_cropped = cv2.copyMakeBorder(resized, top, bottom, left_pad, right_pad,
                                               cv2.BORDER_CONSTANT, value=[0, 0, 0])
        if DEBUG_ANNOTATION:
            cv2.imwrite(os.path.join(DEBUG_DIR, f"cropped_{os.path.basename(image_path)}"), resized_cropped)

        pose_crop_result = None
        try:
            pose_crop_results = pose_model(resized_cropped)
            pose_crop_result = pose_crop_results[0]
            keypoints_crop = extract_pose_keypoints(pose_crop_result)
            if keypoints_crop is None or keypoints_crop.shape[0] < 3:
                raise ValueError("크롭 이미지 키포인트 부족")
        except Exception as e:
            logging.error(f"크롭 pose 추론 실패: {e}")
            pose_crop_result = None

        if pose_crop_result is not None and pose_crop_result.keypoints is not None:
            kps = pose_crop_result.keypoints.data.cpu().numpy()[0]
            # 원본 크롭 좌표 복원
            kps[:, 0] = (kps[:, 0] - left_pad) / scale + x1
            kps[:, 1] = (kps[:, 1] - top) / scale + y1
            pose_crop_result.keypoints.data = torch.tensor([kps])
            keypoints_pose = extract_pose_keypoints(pose_crop_result)
            xs, ys = keypoints_pose[:, 0], keypoints_pose[:, 1]
            pose_bbox_cropped = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
            seg_box = box.tolist()
            seg_area = (seg_box[2] - seg_box[0]) * (seg_box[3] - seg_box[1])
            pose_area_cropped = (pose_bbox_cropped[2] - pose_bbox_cropped[0]) * (pose_bbox_cropped[3] - pose_bbox_cropped[1])
            diff_ratio_cropped = abs(pose_area_cropped - seg_area) / seg_area if seg_area > 0 else 999
            best_idx = select_pose_by_bbox_area(pose_result, seg_box, area_diff_ratio_thresh=DIFF_RATIO_THRESHOLD)
            diff_ratio_best = 999
            if best_idx is not None:
                boxes = pose_result.boxes.xyxy.cpu().numpy()
                best_box = boxes[best_idx]
                best_pose_area = (best_box[2] - best_box[0]) * (best_box[3] - best_box[1])
                diff_ratio_best = abs(best_pose_area - seg_area) / seg_area if seg_area > 0 else 999
            logging.info(f"크롭 diff_ratio={diff_ratio_cropped:.4f}, 기존 diff_ratio={diff_ratio_best:.4f}")
            # hysteresis: 개선 정도가 충분하다면 크롭 결과 사용
            if diff_ratio_cropped < diff_ratio_best - MIN_DIFF_RATIO_IMPROVEMENT:
                logging.info("크롭 pose 결과 사용")
                pose_result = pose_crop_result
            elif best_idx is not None:
                logging.info(f"Fallback: 기존 pose box 사용 (index {best_idx})")
                pose_result = build_single_pose_result(pose_result, best_idx)
    # (3) 결과 연계 검증: 세그와 포즈 결과 개수 일치 여부 확인
    if not (hasattr(seg_result, "boxes") and hasattr(pose_result, "boxes") and
            seg_result.boxes.xyxy.shape[0] == pose_result.boxes.xyxy.shape[0]):
        logging.warning(f"세그와 포즈 결과 개수 불일치: {seg_result.boxes.xyxy.shape[0]} vs {pose_result.boxes.xyxy.shape[0]}. 매칭 오류 우려 있음.")

    keypoints = extract_pose_keypoints(pose_result)
    face_covered = False

    # (4) 분류 결정 (face / body / nonhuman)
    if person_ratio == 0:
        classification = "nonhuman"
        logging.info("분류: 인물 미검출 -> nonhuman")
    elif person_ratio >= PERSON_SIZE_THRESHOLD:
        face_final = logic_face(pose_result, original_area, keypoints)
        if face_final:
            nose = keypoints[HUMAN_KEYPOINTS['nose']]
            left_eye = keypoints[HUMAN_KEYPOINTS['left_eye']]
            right_eye = keypoints[HUMAN_KEYPOINTS['right_eye']]
            if (nose[2] >= FACE_CONF_THRESHOLD_YOLO_POSE and
                left_eye[2] >= FACE_CONF_THRESHOLD_YOLO_POSE and
                right_eye[2] >= FACE_CONF_THRESHOLD_YOLO_POSE):
                face_bbox = (int(min(nose[0], left_eye[0], right_eye[0])),
                             int(min(nose[1], left_eye[1], right_eye[1])),
                             int(max(nose[0], left_eye[0], right_eye[0])),
                             int(max(nose[1], left_eye[1], right_eye[1])))
                if max_person_index is not None and check_face_covering_overlap(seg_result, face_bbox, max_person_index, original_area):
                    classification = "body"
                    face_covered = True
                    logging.info("분류: 얼굴 가림 -> body")
                else:
                    classification = "human"
                    logging.info("분류: 얼굴 검출 -> human")
            else:
                classification = "human"
        else:
            body_final = logic_body(pose_result, original_area, keypoints)
            classification = "body" if body_final else "nonhuman"
    else:
        body_final = logic_body(pose_result, original_area, keypoints)
        classification = "body" if body_final else "nonhuman"

    # (5) 결과 저장 및 어노테이션 처리
    if mode == "production":
        out_filename = os.path.basename(image_path)
        dest_dir = human_dir if classification == "human" else (body_dir if classification == "body" else non_human_dir)
        out_path = os.path.join(dest_dir, out_filename)
        try:
            shutil.move(image_path, out_path)
            logging.info(f"파일 이동: {image_path} -> {out_path}")
        except Exception as e:
            logging.error(f"파일 이동 실패: {image_path} - {e}")
    elif mode == "test":
        if not save_annotation:
            out_filename = os.path.basename(image_path)
            dest_dir = human_dir if classification == "human" else (body_dir if classification == "body" else non_human_dir)
            out_path = os.path.join(dest_dir, out_filename)
            shutil.copy2(image_path, out_path)
            logging.info(f"(raw mode) 원본 복사: {image_path} -> {out_path}")
        else:
            annotated = orig.copy()
            # (a) 세그먼테이션 어노테이션 (보라색)
            if hasattr(seg_result, 'boxes') and seg_result.boxes is not None:
                try:
                    cls_array = seg_result.boxes.cls.cpu().numpy() if hasattr(seg_result.boxes.cls, 'cpu') else np.array(seg_result.boxes.cls)
                except Exception as e:
                    logging.error(f"세그 클래스 오류: {e}")
                    cls_array = []
                seg_masks = get_seg_masks(seg_result)
                if seg_masks is not None:
                    for i in range(len(cls_array)):
                        if int(cls_array[i]) not in REMAINING_CLASSES:
                            continue
                        polygon = np.array(seg_masks[i], dtype=np.int32)
                        overlay = annotated.copy()
                        cv2.fillPoly(overlay, [polygon], color=(255, 0, 255))
                        annotated = cv2.addWeighted(overlay, 0.3, annotated, 0.7, 0)
                        cv2.polylines(annotated, [polygon], isClosed=True, color=(255, 0, 255), thickness=1)
                        detected_label = COCO_CLASSES.get(int(cls_array[i]), "unknown")
                        x, y, w, h = cv2.boundingRect(polygon)
                        cv2.putText(annotated, f"{detected_label} {i}", (x, y - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
                else:
                    for i in range(len(cls_array)):
                        if int(cls_array[i]) not in REMAINING_CLASSES:
                            continue
                        box = seg_result.boxes.xyxy[i]
                        x1_box, y1_box, x2_box, y2_box = [int(val) for val in box.tolist()]
                        overlay = annotated.copy()
                        cv2.rectangle(overlay, (x1_box, y1_box), (x2_box, y2_box), (255, 0, 255), -1)
                        annotated = cv2.addWeighted(overlay, 0.3, annotated, 0.7, 0)
                        cv2.rectangle(annotated, (x1_box, y1_box), (x2_box, y2_box), (255, 0, 255), 1)
                        detected_label = COCO_CLASSES.get(int(cls_array[i]), "unknown")
                        cv2.putText(annotated, f"{detected_label} {i}", (x1_box, y2_box + 15),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
                person_indices = [i for i, cls_id in enumerate(cls_array) if int(cls_id) == 0]
                face_covering_indices = [i for i, cls_id in enumerate(cls_array)
                                         if int(cls_id) in CLASSIFICATION_FACE_COVERING_CLASSES]
            else:
                person_indices = []
                face_covering_indices = []

            # (b) 인물 및 face covering 영역 어노테이션
            seg_masks = get_seg_masks(seg_result)
            if seg_masks is not None:
                for i in person_indices:
                    if i != max_person_index:
                        continue
                    polygon = np.array(seg_masks[i], dtype=np.int32)
                    cv2.polylines(annotated, [polygon], isClosed=True, color=(0, 255, 0), thickness=2)
                    overlay = annotated.copy()
                    cv2.fillPoly(overlay, [polygon], color=(0, 255, 0))
                    annotated = cv2.addWeighted(overlay, 0.4, annotated, 0.6, 0)
            if hasattr(seg_result, 'boxes') and seg_result.boxes is not None:
                for i in person_indices:
                    box = seg_result.boxes.xyxy[i]
                    x1_box, y1_box, x2_box, y2_box = [int(val) for val in box.tolist()]
                    cv2.rectangle(annotated, (x1_box, y1_box), (x2_box, y2_box), (255, 0, 0), 2)
                    cv2.putText(annotated, f"person {i}", (x1_box, y1_box - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)
                for i in face_covering_indices:
                    if seg_masks is not None:
                        polygon = np.array(seg_masks[i], dtype=np.int32)
                        cv2.polylines(annotated, [polygon], isClosed=True, color=(0, 0, 255), thickness=2)
                        overlay = annotated.copy()
                        cv2.fillPoly(overlay, [polygon], color=(0, 0, 255))
                        annotated = cv2.addWeighted(overlay, 0.4, annotated, 0.6, 0)
                    if hasattr(seg_result, 'boxes') and seg_result.boxes is not None:
                        box = seg_result.boxes.xyxy[i]
                        x1_box, y1_box, x2_box, y2_box = [int(val) for val in box.tolist()]
                        cv2.rectangle(annotated, (x1_box, y1_box), (x2_box, y2_box), (0, 0, 255), 2)
                        detected_label = COCO_CLASSES.get(int(seg_result.boxes.cls[i]), "unknown")
                        cv2.putText(annotated, f"{detected_label} {i}", (x1_box, y1_box - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            # (c) 키포인트 및 skeleton 어노테이션
            if keypoints is not None:
                cv2.putText(annotated, "Face detected", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
                annotated = draw_keypoints(annotated, keypoints, color=(255, 255, 0))
                annotated = draw_face_skeleton_extended(annotated, keypoints, threshold=0.5)
                if logic_body(pose_result, pose_input_area, keypoints):
                    cv2.putText(annotated, "Body detected", (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                    annotated = draw_keypoints(annotated, keypoints, color=(0, 255, 255))
                    annotated = draw_skeleton(annotated, keypoints, body_skeleton, color=(0, 255, 255), thickness=2)
            # (d) 포즈 결과 어노테이션
            if hasattr(pose_result, 'boxes') and pose_result.boxes is not None:
                for i, box_pose in enumerate(pose_result.boxes.xyxy):
                    original_idx = pose_result.boxes.orig_idxs[i] if hasattr(pose_result.boxes, 'orig_idxs') else i
                    x1_pose, y1_pose, x2_pose, y2_pose = [int(val) for val in box_pose.tolist()]
                    cv2.rectangle(annotated, (x1_pose, y1_pose), (x2_pose, y2_pose), (0, 255, 0), 2)
                    cv2.putText(annotated, f"pose {original_idx}",
                                (x1_pose, y1_pose - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            base, ext = os.path.splitext(os.path.basename(image_path))
            out_filename = f"{base}_coverd{ext}" if classification == "body" and face_covered else f"{base}_{classification}{ext}"
            dest_dir = human_dir if classification == "human" else (body_dir if classification == "body" else non_human_dir)
            out_path = os.path.join(dest_dir, out_filename)
            cv2.imwrite(out_path, annotated)
            logging.info(f"어노테이션 저장: {out_path}")
            if DEBUG_ANNOTATION:
                cv2.imwrite(os.path.join(DEBUG_DIR, f"annotated_{os.path.basename(image_path)}"), annotated)
    
##############################################
# 동적 배치 사이즈 조절 (히스테리시스 적용)
##############################################
def update_batch_size_optimal(current_bs, current_throughput, state, throughput_history, tolerance=0.1, step=2):
    # GPU 메모리 사용 확인
    if torch.cuda.is_available():
        mem_alloc = torch.cuda.memory_allocated(0)
        mem_reserved = torch.cuda.memory_reserved(0)
        if mem_reserved > 0 and mem_alloc / mem_reserved > 0.5:
            state['direction'] = -1

    throughput_history.append(current_throughput)
    if len(throughput_history) > BATCH_THROUGHPUT_HISTORY_LEN:
        throughput_history.popleft()
    avg_throughput = sum(throughput_history) / len(throughput_history)

    if state['last_bs'] is None:
        state['last_bs'] = current_bs
        state['last_avg'] = avg_throughput
        state['direction'] = 1 if avg_throughput < TARGET_THROUGHPUT else -1
        return current_bs, state

    if abs(avg_throughput - TARGET_THROUGHPUT) <= tolerance:
        state['last_bs'] = current_bs
        state['last_avg'] = avg_throughput
        return current_bs, state

    current_error = abs(avg_throughput - TARGET_THROUGHPUT)
    last_error = abs(state['last_avg'] - TARGET_THROUGHPUT)
    if current_error > last_error:
        state['direction'] = -state['direction']
    candidate_bs = current_bs + state['direction'] * step
    candidate_bs = max(MIN_YOLO_BATCH_SIZE, min(candidate_bs, MAX_YOLO_BATCH_SIZE))
    state['last_bs'] = current_bs
    state['last_avg'] = avg_throughput
    return candidate_bs, state

def process_batch(batch_paths, image_cache, seg_model, pose_model):
    # 각 이미지에 대해 캐시된 이미지를 사용
    batch_images = [image_cache[path] for path in batch_paths if path in image_cache]
    start_time = time.time()
    seg_results = seg_model(batch_images)
    pose_results = pose_model(batch_images)
    elapsed = time.time() - start_time
    throughput = len(batch_paths) / elapsed if elapsed > 0 else 0
    for result in pose_results:
        if result.boxes is not None and result.boxes.xyxy is not None:
            n_boxes = len(result.boxes.xyxy)
            result.boxes.orig_idxs = np.arange(n_boxes)
    return seg_results, pose_results, throughput

def process_images(image_paths, seg_model, pose_model, human_dir, body_dir, non_human_dir,
                   mode="production", save_annotation=True):
    logging.info("이미지 로딩 시작...")
    print(torch.cuda.is_available())
    image_cache = load_images_concurrently(image_paths, max_workers=8)
    logging.info(f"{len(image_cache)}개의 이미지 메모리 로드 완료.")
    current_bs = (MIN_YOLO_BATCH_SIZE + MAX_YOLO_BATCH_SIZE) // 2
    logging.info(f"초기 배치 사이즈: {current_bs}")
    optimal_state = {'last_bs': None, 'last_avg': None, 'direction': 1}
    throughput_history = deque()
    i = 0
    total_images = len(image_paths)
    while i < total_images:
        batch_paths = image_paths[i:i + current_bs]
        try:
            seg_results, pose_results, throughput = process_batch(batch_paths, image_cache, seg_model, pose_model)
            # 결과 연계 검증: 세그와 포즈 결과 개수 체크
            if not (len(seg_results) == len(pose_results) == len(batch_paths)):
                logging.warning("세그 또는 포즈 결과 개수가 배치 이미지 수와 일치하지 않음. 해당 배치는 스킵합니다.")
                i += len(batch_paths)
                continue
            for idx, path in enumerate(batch_paths):
                classify_single_image(
                    path,
                    image_cache.get(path),
                    seg_results[idx],
                    pose_results[idx],
                    human_dir,
                    body_dir,
                    non_human_dir,
                    pose_model,
                    mode=mode,
                    save_annotation=save_annotation
                )
            current_bs, optimal_state = update_batch_size_optimal(current_bs, throughput, optimal_state, throughput_history, tolerance=0.1, step=2)
            logging.info(f"Throughput: {throughput:.2f} 이미지/초, 최적 배치 사이즈: {current_bs}")
            i += len(batch_paths)
        except RuntimeError as e:
            logging.error(f"배치 처리 오류: {batch_paths} - {e}")
            i += current_bs

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
