import streamlit as st
import os
import re
import zipfile
import io
import pytesseract
from PIL import Image, ImageOps
from pytesseract import Output
from pillow_heif import register_heif_opener

# ==========================================
# [기본 설정] 페이지 설정 및 초기화
# ==========================================
register_heif_opener()

st.set_page_config(
    page_title="KNOUAC Book Splitter", 
    page_icon="📚",
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# ==========================================
# [상태 관리] 세션 데이터
# ==========================================
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0
if 'language' not in st.session_state:
    st.session_state.language = 'Korean'

def reset_app():
    st.session_state.processed_data = None
    st.session_state.uploader_key += 1
    st.rerun()

# ==========================================
# [다국어 데이터]
# ==========================================
TRANSLATIONS = {
    'page_title': {
        'Korean': '책 스캔 이미지 분할기',
        'English': 'Book Scan Image Splitter'
    },
    'sub_description': {
        'Korean': '두 쪽을 한 판에 스캔한 이미지를 업로드하세요.<br>자동으로 반으로 자르고, 번호를 인식해 파일명을 정리해 드립니다.',
        'English': 'Upload scanned images containing two pages.<br>It automatically splits them in half and organizes filenames by detecting page numbers.'
    },
    'upload_label': {
        'Korean': '이미지 파일 선택 (JPG, PNG, HEIC)',
        'English': 'Select Image Files (JPG, PNG, HEIC)'
    },
    'format_label': {
        'Korean': '저장 형식',
        'English': 'Save Format'
    },
    'split_btn': {
        'Korean': '✂️ 이미지 분할하기',
        'English': '✂️ SPLIT IMAGES'
    },
    'warning_msg': {
        'Korean': '⚠️ 저장할 형식을 최소 하나 선택해주세요 (PDF 또는 ZIP)',
        'English': '⚠️ Please select at least one format (PDF or ZIP)'
    },
    'processing_msg': {
        'Korean': '처리 중...',
        'English': 'Processing...'
    },
    'download_pdf': {
        'Korean': '📕 PDF 다운로드',
        'English': '📕 Download PDF'
    },
    'download_zip': {
        'Korean': '🗂️ ZIP 다운로드',
        'English': '🗂️ Download ZIP'
    },
    'reset_btn': {
        'Korean': '🔄 처음으로 (초기화)',
        'English': '🔄 Reset (Start Over)'
    },
    'menu_settings': {
        'Korean': '설정 (Settings)',
        'English': 'Settings'
    },
    'menu_lang': {
        'Korean': '언어 (Language)',
        'English': 'Language'
    }
}

def get_text(key):
    lang = st.session_state.language
    return TRANSLATIONS[key].get(lang, TRANSLATIONS[key]['Korean'])

# ==========================================
# [스타일] CSS (상단바 고정 및 디자인)
# ==========================================
custom_style = """
<style>
    /* 폰트 적용 */
    html, body, [class*="css"] {
        font-family: 'Suit', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #333;
    }

    /* Streamlit 기본 헤더 숨기기 */
    header[data-testid="stHeader"] {
        visibility: hidden;
    }
    
    /* 상단 여백 조정 (커스텀 헤더 공간 확보) */
    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 2rem !important;
        max-width: 700px;
    }

    /* 🟢 커스텀 상단바 컨테이너 (Sticky) */
    .custom-navbar {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 60px;
        background-color: white;
        z-index: 9999;
        border-bottom: 1px solid #eee;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* 로고 스타일 */
    .knouac-logo {
        font-size: 22px;
        font-weight: 900;
        color: #2c3e50;
        letter-spacing: -0.5px;
        text-decoration: none;
    }

    /* 팝오버(메뉴) 버튼 커스텀 */
    [data-testid="stPopover"] {
        display: flex;
        justify-content: flex-end;
    }
    [data-testid="stPopover"] > button {
        border: none !important;
        background: transparent !important;
        color: #333 !important;
        font-size: 24px !important; /* 아이콘 크기 */
        padding: 0 10px !important;
        margin-top: -5px;
        box-shadow: none !important;
    }
    [data-testid="stPopover"] > button:hover {
        color: #d9534f !important;
        background: transparent !important;
    }

    /* 메인 타이틀 */
    .main-title {
        font-size: 26px;
        font-weight: 700;
        text-align: center;
        margin-bottom: 0.5rem;
        color: #111;
        margin-top: 20px;
    }
    
    /* 설명 텍스트 */
    .sub-description {
        text-align: center;
        color: #666;
        font-size: 15px;
        margin-bottom: 30px;
        line-height: 1.6;
    }

    /* 업로드 박스 */
    [data-testid="stFileUploader"] section {
        border: 2px dashed #ccc !important;
        background-color: #fafafa !important;
        border-radius: 10px !important;
        padding: 40px 20px !important;
        text-align: center;
    }
    [data-testid="stFileUploader"] section:hover {
        border-color: #d9534f !important;
        background-color: #fff !important;
    }

    /* 버튼 스타일 */
    div.stButton > button[kind="primary"] {
        background-color: #d9534f !important;
        border: none;
        color: white;
        width: 100%;
        padding: 0.7rem;
        font-size: 16px;
        font-weight: 600;
        border-radius: 8px;
    }
    div.stButton > button[kind="primary"]:hover { background-color: #c9302c !important; }
    
    div.stDownloadButton > button {
        background-color: #28a745 !important;
        border: none;
        color: white;
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
    }
</style>
"""
st.markdown(custom_style, unsafe_allow_html=True)

# ==========================================
# [로직] 이미지 처리 함수 (OCR, PDF 등)
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
