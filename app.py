import streamlit as st
import os
import re
import zipfile
import io
import pytesseract
from PIL import Image, ImageOps
from pytesseract import Output
from pillow_heif import register_heif_opener

# HEIC 파일 지원 활성화
register_heif_opener()

# ==========================================
# [핵심 로직] OCR 및 이미지 처리 함수들
# ==========================================

def preprocess_image_for_ocr(img):
    """OCR 인식률을 높이기 위한 전처리"""
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    gray = img.convert('L')
    binary = gray.point(lambda p: 255 if p > 140 else 0)
    return binary

def find_largest_number_across_corners(half_image):
    """(간소화됨) 이미지 구석에서 가장 큰 숫자를 찾아 페이지 번호 추측"""
    # Streamlit Cloud에는 Tesseract가 설치되어 있어야 정확히 동작합니다.
    # 설치가 안 되어 있을 경우를 대비해 예외처리
    try:
        # OCR 로직 (v4 코드와 동일)
        w, h = half_image.size
        # 코너만 잘라서 분석 (속도 최적화)
        crop_h = int(h * 0.15)
        crop_w = int(w * 0.3)
        
        roi_bl = half_image.crop((0, h - crop_h, crop_w, h))
        roi_br = half_image.crop((w - crop_w, h - crop_h, w, h))
        
        candidates = []
        for roi_img in [roi_bl, roi_br]:
            processed_roi = preprocess_image_for_ocr(roi_img)
            # Tesseract 설정
            custom_config = r'--oem 3 --psm 6'
            data = pytesseract.image_to_data(processed_roi, config=custom_config, output_type=Output.DICT)
            
            for i in range(len(data['text'])):
                text = data['text'][i].strip()
                num_text = re.sub(r'\D', '', text)
                if num_text:
                    if int(data['conf'][i]) > 30 and data['height'][i] > 5:
                        candidates.append({'text': num_text, 'h': data['height'][i], 'c': data['conf'][i]})
        
        if candidates:
            candidates.sort(key=lambda x: (x['h'], x['c']), reverse=True)
            return candidates[0]['text']
            
    except Exception:
        return None
    return None

def process_image_in_memory(uploaded_file):
    """파일을 메모리 상에서 변환 (RGB 변환 필수 적용)"""
    img = Image.open(uploaded_file)
    
    # 1. 회전 정보(EXIF) 보정
    img = ImageOps.exif_transpose(img)
    
    # 2. [에러 해결] RGBA(투명) 또는 P 모드일 경우 RGB(흰색 배경)로 변환
    if img.mode in ('RGBA', 'P'):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        if img.mode == 'RGBA':
            # 투명 배경을 흰색으로 합성
            background.paste(img, mask=img.split()[3])
            img = background
        else:
            img = img.convert('RGB')
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    
    # 3. 반으로 자르기
    w, h = img.size
    c_x = w // 2
    
    img_l = img.crop((0, 0, c_x, h))
    img_r = img.crop((c_x, 0, w, h))
    
    # 4. 페이지 번호 인식 시도
    # (속도를 위해 생략 가능하나, 기능 유지를 위해 포함)
    left_num = find_largest_number_across_corners(img_l)
    right_num = find_largest_number_across_corners(img_r)
    
    # 파일명 생성 로직
    name_only = os.path.splitext(uploaded_file.name)[0]
    
    if left_num and right_num:
        fname_l, fname_r = f"{left_num}.jpg", f"{right_num}.jpg"
    elif not left_num and right_num:
        fname_l, fname_r = f"{int(right_num)-1}.jpg", f"{right_num}.jpg"
    elif left_num and not right_num:
        fname_l, fname_r = f"{left_num}.jpg", f"{int(left_num)+1}.jpg"
    else:
        fname_l, fname_r = f"{name_only}_L.jpg", f"{name_only}_R.jpg"
        
    # 5. 메모리 버퍼에 저장 (JPEG 형식)
    buf_l = io.BytesIO()
    img_l.save(buf_l, format="JPEG", quality=95)
    
    buf_r = io.BytesIO()
    img_r.save(buf_r, format="JPEG", quality=95)
    
    return [
        (fname_l, buf_l),
        (fname_r, buf_r)
    ]

# ==========================================
# [UI] Streamlit 화면 구성
# ==========================================
st.set_page_config(page_title="책 스캔 분할기", layout="centered")

st.title("📚 책 스캔 이미지 분할기")
st.markdown("""
이미지(JPG, PNG, HEIC)를 업로드하면:
1. 자동으로 **반으로 자르고**
2. 페이지 번호를 인식하여 **이름을 변경**해 줍니다.
""")

uploaded_files = st.file_uploader("이미지 파일을 드래그하거나 선택하세요", 
                                  accept_multiple_files=True, 
                                  type=['png', 'jpg', 'jpeg', 'heic', 'bmp'])

if uploaded_files:
    if st.button(f"총 {len(uploaded_files)}장 변환 시작"):
        # ZIP 파일 생성을 위한 메모리 버퍼
        zip_buffer = io.BytesIO()
        
        # 진행률 표시줄
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for i, file in enumerate(uploaded_files):
                status_text.text(f"처리 중... ({i+1}/{len(uploaded_files)}): {file.name}")
                
                try:
                    results = process_image_in_memory(file)
                    
                    # ZIP에 추가 (중복 이름 처리)
                    for fname, img_data in results:
                        # ZIP 내 중복 파일명 방지
                        if fname in zf.namelist():
                            base, ext = os.path.splitext(fname)
                            fname = f"{base}_{i}{ext}"
                        
                        zf.writestr(fname, img_data.getvalue())
                except Exception as e:
                    st.error(f"⚠️ {file.name} 처리 중 오류 발생: {e}")
                
                progress_bar.progress((i + 1) / len(uploaded_files))
        
        status_text.text("✅ 모든 작업 완료!")
        progress_bar.progress(100)
            
        # 다운로드 버튼 생성
        st.success("변환이 완료되었습니다. 아래 버튼을 눌러 다운로드하세요.")
        st.download_button(
            label="📥 분할된 이미지 다운로드 (ZIP)",
            data=zip_buffer.getvalue(),
            file_name="split_images.zip",
            mime="application/zip"
        )
