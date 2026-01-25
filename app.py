import streamlit as st
import os
import re
import zipfile
import io
import pytesseract
from PIL import Image, ImageOps
from pytesseract import Output
from pillow_heif import register_heif_opener

# HEIC 파일 지원
register_heif_opener()

# ==========================================
# [설정] 페이지 기본 설정 (가장 위에 있어야 함)
# ==========================================
st.set_page_config(
    page_title="책 스캔 분할기", 
    page_icon="📚",
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# ==========================================
# [디자인] 모바일 반응형 CSS (최종: 화면 꽉 채우기)
# ==========================================
mobile_style = """
<style>
    /* 기본 폰트 적용 */
    html, body, [class*="css"] {
        font-family: sans-serif;
    }

    /* 📱 모바일 환경 (화면 너비 640px 이하) 설정 */
    @media only screen and (max-width: 640px) {
        
        /* 1. [핵심] 내용을 화면 양옆으로 꽉 채우기 */
        .block-container {
            max-width: 100% !important;  /* 최대 너비 제한 해제 */
            padding-left: 1rem !important; /* 좌측 여백 최소화 */
            padding-right: 1rem !important; /* 우측 여백 최소화 */
            padding-top: 2rem !important;
        }
        
        /* 2. 제목 시원하게 */
        h1 {
            font-size: 28px !important;
            margin-bottom: 1rem !important;
        }
        
        /* 3. 본문 텍스트 크기 및 줄간격 확보 */
        .stMarkdown p, .stMarkdown li {
            font-size: 18px !important;
            line-height: 1.6 !important;
        }
        
        /* 4. 업로드 박스: 너비를 100%로 강제하고 내부 여백 확보 */
        [data-testid="stFileUploader"] {
            width: 100% !important;
        }
        [data-testid="stFileUploader"] section {
            padding: 2rem !important; /* 터치 영역 넉넉하게 */
            min-height: 150px !important;
        }
        /* 드래그 앤 드롭 안내 문구 키우기 */
        [data-testid="stFileUploader"] div, 
        [data-testid="stFileUploader"] span, 
        [data-testid="stFileUploader"] small {
            font-size: 16px !important; 
        }

        /* 5. 버튼: 화면 가로폭 가득 채우기 */
        .stButton button {
            width: 100% !important;
            font-size: 20px !important;
            padding: 0.8rem !important;
            margin-top: 0.5rem !important;
        }
    }
</style>
"""
st.markdown(mobile_style, unsafe_allow_html=True)

# ==========================================
# [로직] 이미지 처리 함수들
# ==========================================
def preprocess_image_for_ocr(img):
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    gray = img.convert('L')
    binary = gray.point(lambda p: 255 if p > 140 else 0)
    return binary

def find_largest_number_across_corners(half_image):
    try:
        w, h = half_image.size
        crop_h = int(h * 0.15)
        crop_w = int(w * 0.3)
        
        roi_bl = half_image.crop((0, h - crop_h, crop_w, h))
        roi_br = half_image.crop((w - crop_w, h - crop_h, w, h))
        
        candidates = []
        for roi_img in [roi_bl, roi_br]:
            processed_roi = preprocess_image_for_ocr(roi_img)
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
    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img)
    
    # RGBA -> RGB 변환
    if img.mode in ('RGBA', 'P'):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == 'P': img = img.convert('RGBA')
        if img.mode == 'RGBA':
            background.paste(img, mask=img.split()[3])
            img = background
        else:
            img = img.convert('RGB')
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    
    w, h = img.size
    c_x = w // 2
    
    img_l = img.crop((0, 0, c_x, h))
    img_r = img.crop((c_x, 0, w, h))
    
    left_num = find_largest_number_across_corners(img_l)
    right_num = find_largest_number_across_corners(img_r)
    
    name_only = os.path.splitext(uploaded_file.name)[0]
    
    if left_num and right_num:
        fname_l, fname_r = f"{left_num}.jpg", f"{right_num}.jpg"
    elif not left_num and right_num:
        fname_l, fname_r = f"{int(right_num)-1}.jpg", f"{right_num}.jpg"
    elif left_num and not right_num:
        fname_l, fname_r = f"{left_num}.jpg", f"{int(left_num)+1}.jpg"
    else:
        fname_l, fname_r = f"{name_only}_L.jpg", f"{name_only}_R.jpg"
        
    buf_l = io.BytesIO()
    img_l.save(buf_l, format="JPEG", quality=95)
    
    buf_r = io.BytesIO()
    img_r.save(buf_r, format="JPEG", quality=95)
    
    return [(fname_l, buf_l), (fname_r, buf_r)]

# ==========================================
# [UI] 화면 구성 (설명 부분 개선)
# ==========================================
st.title("📚 책 스캔 이미지 분할기")

# 텍스트 대신 Info 박스나 마크다운 헤더 사용으로 가독성 높임
st.markdown("""
### 💡 사용 방법
이미지(JPG, PNG, HEIC)를 업로드하면:
1. 자동으로 **반으로 자르고** ✂️
2. 페이지 번호를 인식하여 **이름을 변경**해 줍니다. 🔢
""")

st.write("---") # 구분선

uploaded_files = st.file_uploader(
    "👇 아래 영역을 터치하여 사진을 선택하세요", 
    accept_multiple_files=True, 
    type=['png', 'jpg', 'jpeg', 'heic', 'bmp']
)

if uploaded_files:
    # 버튼도 크게 보이도록 스타일 적용됨
    if st.button(f"🚀 총 {len(uploaded_files)}장 변환 시작하기", type="primary"):
        zip_buffer = io.BytesIO()
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for i, file in enumerate(uploaded_files):
                status_text.text(f"⏳ 처리 중... ({i+1}/{len(uploaded_files)})")
                try:
                    results = process_image_in_memory(file)
                    for fname, img_data in results:
                        if fname in zf.namelist():
                            base, ext = os.path.splitext(fname)
                            fname = f"{base}_{i}{ext}"
                        zf.writestr(fname, img_data.getvalue())
                except Exception as e:
                    st.error(f"⚠️ 오류: {file.name} - {e}")
                
                progress_bar.progress((i + 1) / len(uploaded_files))
        
        status_text.success("✅ 변환 완료!")
        progress_bar.progress(100)
            
        st.download_button(
            label="📥 결과물 다운로드 (ZIP)",
            data=zip_buffer.getvalue(),
            file_name="split_images.zip",
            mime="application/zip",
            type="primary" 
        )
