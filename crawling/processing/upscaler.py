# crawling/processing/upscaler.py
import os
import sys
import numpy as np
from PIL import Image
import torch
from gfpgan import GFPGANer
from basicsr.archs.rrdbnet_arch import RRDBNet
from realesrgan import RealESRGANer

def upscale_image(input_path: str, output_path: str, face_upscale: int = 2, overall_scale: int = 4) -> str:
    """
    GFPGAN과 Real-ESRGAN을 조합하여 이미지를 업스케일링합니다.
    
    1. GFPGAN: 얼굴 복원 (피부 질감, 눈썹, 눈 디테일 복구)
    2. Real-ESRGAN: 전체 이미지 업스케일링 (배경 포함)
    
    매개변수:
        input_path: 원본 이미지 경로
        output_path: 최종 업스케일된 이미지 저장 경로
        face_upscale: GFPGAN 업스케일 배율 (일반적으로 2)
        overall_scale: Real-ESRGAN 업스케일 배율 (일반적으로 4)
        
    반환:
        output_path (str): 업스케일링된 이미지 저장 경로
    """
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # 모델 파일 경로: models/upscaling 폴더 내에 있음 (프로젝트 루트 기준)
    project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
    model_dir = os.path.join(project_root, 'models', 'upscaling')
    gfpgan_model_path = os.path.join(model_dir, 'GFPGANv1.3.pth')
    realesrgan_model_path = os.path.join(model_dir, f'RealESRGAN_x{overall_scale}plus.pth')
    
    # 1. GFPGAN으로 얼굴 복원
    print("GFPGAN: 얼굴 복원 시작...")
    gfpgan = GFPGANer(
        model_path=gfpgan_model_path,
        upscale=face_upscale,
        arch='clean',
        channel_multiplier=2,
        device=device
    )
    _, _, restored_img = gfpgan.enhance(
        input_path,
        has_aligned=False,
        only_center_face=False,
        paste_back=True
    )
    
    temp_path = os.path.join(os.path.dirname(output_path), 'temp_restored.jpg')
    restored_img.save(temp_path)
    print("GFPGAN: 얼굴 복원 완료, 임시 저장:", temp_path)
    
    # 2. Real-ESRGAN을 이용한 전체 이미지 업스케일링
    print("Real-ESRGAN: 전체 이미지 업스케일 시작...")
    model = RRDBNet(
        num_in_ch=3,
        num_out_ch=3,
        num_feat=64,
        num_block=23,
        num_grow_ch=32,
        scale=overall_scale
    )
    upscaler = RealESRGANer(
        scale=overall_scale,
        model_path=realesrgan_model_path,
        model=model,
        tile=0,
        tile_pad=10,
        pre_pad=0,
        half=True,
        device=device
    )
    
    img = Image.open(temp_path).convert('RGB')
    sr_image, _ = upscaler.enhance(np.array(img), outscale=1)
    Image.fromarray(sr_image).save(output_path)
    print("Real-ESRGAN: 업스케일 완료, 저장 위치:", output_path)
    
    if os.path.exists(temp_path):
        os.remove(temp_path)
    
    return output_path

if __name__ == "__main__":
    # 사용법:
    # 디렉토리 모드: python upscaler.py <input_directory> [face_upscale] [overall_scale]
    # 예: python upscaler.py "input_directory" 2 4
    # 파일 모드: python upscaler.py <input_image_path> <output_image_path> [face_upscale] [overall_scale]
    if len(sys.argv) < 2:
        print("Usage:")
        print(" 디렉토리 모드: python upscaler.py <input_directory> [face_upscale] [overall_scale]")
        print(" 파일 모드: python upscaler.py <input_image_path> <output_image_path> [face_upscale] [overall_scale]")
        sys.exit(1)
    
    input_path = sys.argv[1]
    face_upscale = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    overall_scale = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    
    if os.path.isdir(input_path):
        output_dir = os.path.join(input_path, "upscale")
        os.makedirs(output_dir, exist_ok=True)
        supported_ext = ('.jpg', '.jpeg', '.png')
        for file in os.listdir(input_path):
            if file.lower().endswith(supported_ext):
                in_file = os.path.join(input_path, file)
                out_file = os.path.join(output_dir, file)
                print(f"Processing {in_file} -> {out_file}")
                upscale_image(in_file, out_file, face_upscale, overall_scale)
        print("디렉토리 내 모든 이미지 업스케일 완료!")
    else:
        if len(sys.argv) < 3:
            print("Usage: python upscaler.py <input_image_path> <output_image_path> [face_upscale] [overall_scale]")
            sys.exit(1)
        output_path = sys.argv[2]
        upscale_image(input_path, output_path, face_upscale, overall_scale)
