import os
import shutil
import sys
import logging
import math
from ultralytics import YOLO
from PIL import Image
import torch
import numpy as np
from collections import defaultdict

import detectron2
from detectron2.engine import DefaultPredictor
from detectron2.config import get_cfg
from detectron2 import model_zoo

##############################################
# 임계값 설정 (로직별, 모델별로 세분화)
##############################################
PERSON_CONF_THRESHOLD_YOLO = 0.98
PERSON_CONF_THRESHOLD_DETECTRON = 0.98
PERSON_SIZE_THRESHOLD = 0.65

FACE_CONF_THRESHOLD_YOLO_POSE = 0.5
FACE_CONF_THRESHOLD_DETECTRON_KEYPOINT = 0.5
FACE_SIZE_THRESHOLD = 0.0015

BODY_CONF_THRESHOLD_YOLO_POSE = 0.5
BODY_CONF_THRESHOLD_DETECTRON_KEYPOINT = 0.5
BODY_SIZE_THRESHOLD = 0.1159

KEYPOINT_CONFIDENCE_THRESHOLD = 0.5  # 키포인트 공통 임계값 (키포인트 자체 신뢰도)

##############################################
script_dir = os.path.dirname(os.path.abspath(__file__))

YOLO_MODEL_NAME = "yolo11s.pt"
YOLO_POSE_MODEL_NAME = "yolo11x-pose.pt"

DETECTRON2_CONFIG = "COCO-Detection/faster_rcnn_R_50_FPN_3x.yaml"
DETECTRON2_WEIGHTS = model_zoo.get_checkpoint_url(DETECTRON2_CONFIG)
DETECTRON2_KEYPOINT_CONFIG = "COCO-Keypoints/keypoint_rcnn_R_50_FPN_3x.yaml"
DETECTRON2_KEYPOINT_WEIGHTS = model_zoo.get_checkpoint_url(DETECTRON2_KEYPOINT_CONFIG)

WEIGHTS_PATH = os.path.join(script_dir, "yolo_model", YOLO_MODEL_NAME)
POSE_WEIGHTS = os.path.join(script_dir, "yolo_model", YOLO_POSE_MODEL_NAME)

BATCH_SIZE = 32

HUMAN_KEYPOINTS = {
    'nose': 0,
    'left_eye': 1,
    'right_eye': 2,
    'left_ear': 3,
    'right_ear': 4
}
NON_HUMAN_KEYPOINTS = [5, 6, 11, 12, 7, 8, 9, 10, 13, 14, 15, 16]

##############################################
# 공용 함수
##############################################
def compute_iou(box1, box2):
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    inter_area = max(0, x2 - x1)*max(0, y2 - y1)
    box1_area = (box1[2]-box1[0])*(box1[3]-box1[1])
    box2_area = (box2[2]-box2[0])*(box2[3]-box2[1])
    union_area = box1_area+box2_area-inter_area
    return inter_area/union_area if union_area>0 else 0

def weighted_box_fusion(boxes, iou_threshold=0.4):
    # boxes: [(conf, [x1,y1,x2,y2], source), ...]
    boxes = sorted(boxes, key=lambda x: x[0], reverse=True)
    fused_boxes = []

    while boxes:
        # 가장 신뢰도 높은 박스 선택
        best_conf, best_box, best_source = boxes.pop(0)
        cluster = [(best_conf, best_box)]
        
        # IoU가 iou_threshold 이상인 박스들을 모음
        to_remove = []
        for idx, (conf,box,src) in enumerate(boxes):
            iou = compute_iou(best_box, box)
            if iou > iou_threshold:
                cluster.append((conf, box))
                to_remove.append(idx)
        
        # 뒤에서부터 제거(인덱스 밀림 방지)
        for idx in reversed(to_remove):
            boxes.pop(idx)

        # cluster 내 박스들을 가중 평균
        if cluster:
            sum_conf = sum([c for c,b in cluster])
            x1_avg = sum([b[0]*c for c,b in cluster])/sum_conf
            y1_avg = sum([b[1]*c for c,b in cluster])/sum_conf
            x2_avg = sum([b[2]*c for c,b in cluster])/sum_conf
            y2_avg = sum([b[3]*c for c,b in cluster])/sum_conf
            avg_conf = sum_conf/len(cluster)  # 평균 신뢰도(또는 그냥 max 사용 가능)
            fused_boxes.append((avg_conf,[x1_avg,y1_avg,x2_avg,y2_avg],"WBF"))
    return fused_boxes

def ensemble_detections(dets_a, dets_b, iou_threshold=0.4):
    all_dets = dets_a + dets_b
    class_boxes = defaultdict(list)
    for det in all_dets:
        cls_id, conf, bbox, source = det
        class_boxes[cls_id].append((conf,bbox,source))

    final_boxes = []
    for cls_id,boxes in class_boxes.items():
        # WBF 적용
        fused = weighted_box_fusion(boxes, iou_threshold)
        for conf,bbox,src in fused:
            final_boxes.append((cls_id,conf,bbox,src))
    return final_boxes

def is_valid_bbox(box, img_area, min_ratio=0.05, max_ratio=0.5):
    x1,y1,x2,y2 = box
    ba=(x2-x1)*(y2-y1)
    ratio=ba/img_area
    return min_ratio<=ratio<=max_ratio

def is_aspect_ratio_valid(box, aspect_ratio_range=(0.5,2.0)):
    x1,y1,x2,y2=box
    w=x2-x1
    h=y2-y1
    if w==0 or h==0:
        return False
    r=h/w
    return aspect_ratio_range[0]<=r<=aspect_ratio_range[1]

def is_centered(box, img_width, img_height, center_threshold=0.3):
    x1,y1,x2,y2=box
    cx=(x1+x2)/2
    cy=(y1+y2)/2
    img_cx=img_width/2
    img_cy=img_height/2
    dx=abs(cx-img_cx)/img_width
    dy=abs(cy-img_cy)/img_height
    return dx<=center_threshold and dy<=center_threshold

def calculate_distance(kp1,kp2):
    x1,y1,_=kp1
    x2,y2,_=kp2
    return math.sqrt((x2-x1)**2+(y2-y1)**2)

def estimate_face_area(nose,left_eye=None,right_eye=None):
    if left_eye is not None and right_eye is not None:
        dist_lr=calculate_distance(left_eye,right_eye)
        dist_nl=calculate_distance(nose,left_eye)
        dist_nr=calculate_distance(nose,right_eye)
        a=dist_lr/2
        b=(dist_nl+dist_nr)/4
    elif left_eye is not None or right_eye is not None:
        eye=left_eye if left_eye is not None else right_eye
        dist_ne=calculate_distance(nose,eye)
        a=dist_ne/2
        b=dist_ne/4
    else:
        a=0
        b=0
    if a>0 and b>0:
        return math.pi*a*b
    return 0

def estimate_body_area(keypoints_data):
    body_kps=[keypoints_data[i] for i in NON_HUMAN_KEYPOINTS if i<len(keypoints_data)]
    body_kps=[kp for kp in body_kps if kp is not None and len(kp)>=3 and kp[2]>=KEYPOINT_CONFIDENCE_THRESHOLD]
    if not body_kps:
        return 0
    xs=[kp[0] for kp in body_kps]
    ys=[kp[1] for kp in body_kps]
    w=max(xs)-min(xs)
    h=max(ys)-min(ys)
    return w*h

def merge_keypoints(yolo_kps, rcnn_kps, conf_threshold=KEYPOINT_CONFIDENCE_THRESHOLD):
    if yolo_kps is None and rcnn_kps is None:
        return None
    if yolo_kps is not None and rcnn_kps is not None:
        merged=[]
        for (x1,y1,c1),(x2,y2,c2) in zip(yolo_kps,rcnn_kps):
            if c1>=conf_threshold and c2>=conf_threshold:
                merged.append(((x1+x2)/2,(y1+y2)/2,(c1+c2)/2))
            elif c1>=conf_threshold:
                merged.append((x1,y1,c1))
            elif c2>=conf_threshold:
                merged.append((x2,y2,c2))
            else:
                merged.append((0,0,0))
        return np.array(merged)
    elif yolo_kps is not None:
        merged=[]
        for (x,y,c) in yolo_kps:
            merged.append((x,y,c if c>=conf_threshold else 0))
        return np.array(merged)
    else:
        merged=[]
        for (x,y,c) in rcnn_kps:
            merged.append((x,y,c if c>=conf_threshold else 0))
        return np.array(merged)

##############################################
# Detect functions
##############################################
def detect_person_yolo(yolo_result, img_area):
    person_dets=[]
    for box in yolo_result.boxes:
        cls_id=int(box.cls)
        if cls_id==0: # person
            conf=float(box.conf)
            if conf>=PERSON_CONF_THRESHOLD_YOLO:
                x_center,y_center,w,h=box.xywh[0].tolist()
                x1=x_center-w/2
                y1=y_center-h/2
                x2=x_center+w/2
                y2=y_center+h/2
                person_dets.append((cls_id,conf,[x1,y1,x2,y2],'YOLO'))
    return person_dets

def detect_person_detectron(predictor, image, img_area):
    outputs=predictor(image)
    inst=outputs.get("instances",None)
    if inst is None:
        return []
    inst=inst.to("cpu")
    boxes=inst.pred_boxes.tensor.numpy()
    classes=inst.pred_classes.numpy()
    scores=inst.scores.numpy()

    dets=[]
    for box,cls,score in zip(boxes,classes,scores):
        if cls==0 and score>=PERSON_CONF_THRESHOLD_DETECTRON:
            dets.append((cls,float(score),box.tolist(),'Detectron'))
    return dets

def detect_keypoints_detectron(predictor, image):
    out = predictor(image)
    inst = out.get("instances",None)
    if inst is None:
        return None
    inst=inst.to("cpu")
    if not inst.has("pred_keypoints"):
        return None
    kps=inst.pred_keypoints.numpy()
    classes=inst.pred_classes.numpy()
    scores=inst.scores.numpy()
    best_idx=-1
    best_score=0
    for i,(c,s) in enumerate(zip(classes,scores)):
        if c==0 and s>best_score:
            best_score=s
            best_idx=i
    if best_idx==-1:
        return None
    return kps[best_idx]

def detect_yolo_pose_face(yolo_pose_result):
    if (yolo_pose_result is not None and 
        hasattr(yolo_pose_result,'keypoints') and
        yolo_pose_result.keypoints is not None and
        yolo_pose_result.keypoints.data.numel()>0):
        kps = yolo_pose_result.keypoints.data.cpu().numpy()[0]
        return kps
    return None

def detect_yolo_pose_body(yolo_pose_result):
    if (yolo_pose_result is not None and
        hasattr(yolo_pose_result,'keypoints') and
        yolo_pose_result.keypoints is not None and
        yolo_pose_result.keypoints.data.numel()>0):
        kps = yolo_pose_result.keypoints.data.cpu().numpy()[0]
        return kps
    return None

##############################################
# 로직 구현
##############################################
def logic1_person(yolo_result, predictor, image, img_area):
    yolo_dets = detect_person_yolo(yolo_result, img_area)
    rcnn_dets = detect_person_detectron(predictor, image, img_area)

    final_dets = ensemble_detections(yolo_dets, rcnn_dets, iou_threshold=0.4)
    filtered=[]
    for cls_id,conf,bbox,source in final_dets:
        w=bbox[2]-bbox[0]
        h=bbox[3]-bbox[1]
        area=w*h
        ratio=area/img_area
        if ratio>=PERSON_SIZE_THRESHOLD:
            filtered.append((cls_id,conf,bbox,source))
    return filtered

def logic2_face(yolo_pose_result, rcnn_kps, img_area):
    yolo_kps = detect_yolo_pose_face(yolo_pose_result)
    merged=merge_keypoints(yolo_kps, rcnn_kps, KEYPOINT_CONFIDENCE_THRESHOLD)
    if merged is None:
        return []
    nose = merged[HUMAN_KEYPOINTS['nose']]
    left_eye = merged[HUMAN_KEYPOINTS['left_eye']]
    right_eye= merged[HUMAN_KEYPOINTS['right_eye']]

    if nose[2]>0 and left_eye[2]>0 and right_eye[2]>0:
        face_area=estimate_face_area(nose,left_eye,right_eye)
        face_ratio=face_area/img_area
        if face_ratio>=FACE_SIZE_THRESHOLD:
            return [('face',face_ratio,None,'face_ensemble')]
    return []

def logic3_body(yolo_pose_result, rcnn_kps, img_area):
    yolo_kps = detect_yolo_pose_body(yolo_pose_result)
    merged = merge_keypoints(yolo_kps, rcnn_kps, KEYPOINT_CONFIDENCE_THRESHOLD)
    if merged is None:
        return []
    
    # 손목을 제외한 필수 바디 키포인트 정의 (예: 어깨, 엘보우, 힙, 무릎, 발목)
    ESSENTIAL_BODY_KEYPOINTS = [5, 6, 7, 8, 11, 12, 13, 14, 15, 16]  # 어깨, 엘보우, 힙, 무릎, 발목
    
    # 신뢰도가 높은 필수 키포인트 수 계산
    essential_detected = [
        kp for idx, kp in enumerate(merged) 
        if idx in ESSENTIAL_BODY_KEYPOINTS and kp[2] >= KEYPOINT_CONFIDENCE_THRESHOLD
    ]
    
    # 최소 필수 키포인트 수 설정
    MIN_ESSENTIAL_KEYPOINTS = 4  # 필요에 따라 조정 가능
    
    if len(essential_detected) < MIN_ESSENTIAL_KEYPOINTS:
        # 필수 바디 키포인트가 충분하지 않으면 비인물로 분류
        #logging.info(f"필수 바디 키포인트 부족: {len(essential_detected)}개 검출됨.")
        return []
    
    body_area_val = estimate_body_area(merged)
    body_ratio = body_area_val / img_area
    if body_ratio >= BODY_SIZE_THRESHOLD:
        return [('body', body_ratio, None, 'body_ensemble')]
    return []

def classify_images(directory_path, weights, pose_weights, predictor, keypoint_predictor, batch_size):
    human_dir = os.path.join(directory_path,"인물")
    non_human_dir = os.path.join(directory_path,"비인물")
    os.makedirs(human_dir, exist_ok=True)
    os.makedirs(non_human_dir, exist_ok=True)

    yolo_model = YOLO(weights)
    pose_model = YOLO(pose_weights)

    image_paths=[]
    for root,_,files in os.walk(directory_path):
        for f in files:
            if f.lower().endswith(('.jpg','.jpeg','.png')):
                image_paths.append(os.path.join(root,f))

    for i in range(0,len(image_paths),batch_size):
        batch = image_paths[i:i+batch_size]
        try:
            logging.info(f"배치 {i//batch_size+1}: {len(batch)}개의 이미지를 처리 중...")
            results = yolo_model(batch)
            pose_results = pose_model(batch)

            for image_path, yolo_result, pose_result in zip(batch, results, pose_results):
                try:
                    detection_reasons=[]
                    with Image.open(image_path) as img:
                        image = np.array(img.convert("RGB"))[:,:,::-1].copy()
                        h,w=image.shape[:2]
                        img_area=w*h

                    person_final=logic1_person(yolo_result, predictor, image, img_area)
                    if person_final:
                        detection_reasons.append("Person detected from 로직1 앙상블(WBF)")

                    rcnn_kps = detect_keypoints_detectron(keypoint_predictor, image)

                    face_final=logic2_face(pose_result, rcnn_kps, img_area)
                    if face_final:
                        detection_reasons.append("Face detected from 로직2 앙상블(WBF)")

                    body_final=logic3_body(pose_result, rcnn_kps, img_area)
                    if body_final:
                        detection_reasons.append("Body detected from 로직3 앙상블(WBF)")

                    if person_final or face_final or body_final:
                        reasons = "; ".join(detection_reasons) if detection_reasons else "Detected"
                        logging.info(f"[인물 이미지] {image_path} - 이유: {reasons}")
                        shutil.move(image_path, os.path.join(human_dir, os.path.basename(image_path)))
                    else:
                        logging.info(f"[비인물 이미지] {image_path} - 이유: No detection after WBF thresholds.")
                        shutil.move(image_path, os.path.join(non_human_dir, os.path.basename(image_path)))

                except Exception as e:
                    logging.error(f"이미지 처리 오류: {image_path} - {e}")

        except Exception as e:
            logging.error(f"배치 처리 오류: {batch} - {e}")

def main():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler=logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter=logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    cfg = get_cfg()
    cfg.merge_from_file(model_zoo.get_config_file(DETECTRON2_CONFIG))
    cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = PERSON_CONF_THRESHOLD_DETECTRON
    cfg.MODEL.WEIGHTS = DETECTRON2_WEIGHTS
    predictor = DefaultPredictor(cfg)

    cfg_kp = get_cfg()
    cfg_kp.merge_from_file(model_zoo.get_config_file(DETECTRON2_KEYPOINT_CONFIG))
    cfg_kp.MODEL.ROI_HEADS.SCORE_THRESH_TEST = max(FACE_CONF_THRESHOLD_DETECTRON_KEYPOINT, BODY_CONF_THRESHOLD_DETECTRON_KEYPOINT)
    cfg_kp.MODEL.WEIGHTS = DETECTRON2_KEYPOINT_WEIGHTS
    keypoint_predictor = DefaultPredictor(cfg_kp)

    if len(sys.argv)!=2:
        logging.error("사용법: python classify_yolo_rcnn.py [이미지_디렉토리]")
        sys.exit(1)

    DIRECTORY_PATH=sys.argv[1]
    classify_images(
        directory_path=DIRECTORY_PATH,
        weights=WEIGHTS_PATH,
        pose_weights=POSE_WEIGHTS,
        predictor=predictor,
        keypoint_predictor=keypoint_predictor,
        batch_size=BATCH_SIZE
    )

if __name__=="__main__":
    main()
