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
# [설정] 페이지 기본 설정
# ==========================================
st.set_page_config(
    page_title="책 스캔 분할기", 
    page_icon="📖",
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# ==========================================
# [설정] 세션 상태 초기화 (새로고침 시 데이터 유지용)
# ==========================================
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    # 초기화 버튼 누르면 상태 비우고 리로드
    st.session_state.processed_data = None
    st.session_state.uploader_key += 1
    st.rerun()

# ==========================================
# [설정] UI 디자인 (CSS 주입)
# ==========================================
custom_style = """
<style>
    html, body, [class*="css"] {
        font-family: 'Suit', sans-serif;
    }

    /* 📤 업로드 박스 디자인 (점선 테두리) */
    [data-testid="stFileUploader"] section {
        border: 2px dashed #a0a5b5 !important;
        background-color: #fcfcfc !important;
        border-radius: 12px !important;
        padding: 30px 10px !important;
    }
    
    [data-testid="stFileUploader"] section > div > div > svg {
        fill: #7d8294 !important;
    }

    /* 🎛️ 컨트롤 박스 디자인 */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border: 2px dashed #a0a5b5 !important;
        border-radius: 12px !important;
        background-color: #f8f9fa !important;
        padding: 20px !important;
    }

    /* 변환 버튼 (빨간색) */
    div.stButton > button[kind="primary"] {
        background-color: #d9534f !important;
        border: none !important;
        color: white !important;
        width: 100% !important;
        padding: 0.6rem 1rem !important;
        font-weight: 600 !important;
        margin-top: 5px !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #c9302c !important;
    }

    /* 다운로드 버튼 (성공 시, 초록색 계열) */
    div.stDownloadButton > button {
        background-color: #28a745 !important;
        border: none !important;
        color: white !important;
        width: 100% !important;
        font-weight: 600 !important;
    }
    div.stDownloadButton > button:hover {
        background-color: #218838 !important;
    }

    /* 체크박스 디자인 조정 */
    .stCheckbox {
        padding-top: 5px;
    }

    /* 모바일 최적화 */
    @media only screen and (max-width: 640px) {
        .block-container { padding-top: 2rem !important; }
        div.stButton > button[kind="primary"] { font-size: 16px !important; }
    }
</style>
"""
st.markdown(custom_style, unsafe_allow_html=True)

# ==========================================
# [로직] 이미지 처리 함수
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
    except:
        return None
    return None

def resize_for_pdf(img):
    max_width = 1240
    if img.width > max_width:
        ratio = max_width / float(img.width)
        new_height = int(float(img.height) * ratio)
        return img.resize((max_width, new_height), Image.Resampling.LANCZOS)
    return img

def process_image_in_memory(uploaded_file):
    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img)
    if img.mode != 'RGB':
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
    
    img_l_pdf = resize_for_pdf(img_l)
    img_r_pdf = resize_for_pdf(img_r)
    
    return [(fname_l, buf_l, img_l_pdf), (fname_r, buf_r, img_r_pdf)]

# ==========================================
# [UI] 화면 구성
# ==========================================
# [수정] st.title 대신 HTML로 폰트 크기를 26px 정도로 줄여서 표시 (기존보다 작게)
st.markdown("<h2 style='font-size: 26px; font-weight: 700; margin-bottom: 10px;'>책 스캔 이미지 반반 분할기</h2>", unsafe_allow_html=True)

st.markdown("""
<div style="margin-bottom: 20px; color: #555;">
    📖 두 쪽을 한 판에 스캔한 이미지를 업로드하면<br>
    반반 잘라서 하나의 PDF로 합치거나 ZIP으로 다운로드 할 수 있습니다.
</div>
""", unsafe_allow_html=True)

# 1. 파일 업로더
uploaded_files = st.file_uploader(
    "이미지 업로드",
    accept_multiple_files=True, 
    type=['png', 'jpg', 'jpeg', 'heic', 'bmp'],
    key=f"uploader_{st.session_state.uploader_key}",
    label_visibility="collapsed"
)

# 파일 업로드 시 컨트롤 박스 표시
if uploaded_files:
    st.write("") 
    
    with st.container(border=True):
        col_opt, col_act = st.columns([1, 1.2], gap="large")
        
        # [왼쪽] 옵션 선택 (체크박스로 변경하여 'No results' 문제 해결)
        with col_opt:
            st.markdown("**저장 포맷**")
            sub_c1, sub_c2 = st.columns(2)
            with sub_c1:
                opt_pdf = st
