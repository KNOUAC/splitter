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
    
    # [수정된 부분] 들여쓰기 오류 해결
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
# [UI] 상단 네비게이션 바 (Sticky Header)
# ==========================================
c1, c2 = st.columns([8, 1])

with c1:
    st.markdown('<div class="knouac-logo">KNOUAC</div>', unsafe_allow_html=True)

with c2:
    # ☰ 메뉴 팝오버
    with st.popover("☰", use_container_width=False):
        st.markdown(f"**{get_text('menu_settings')}**")
        
        # 언어 선택
        new_lang = st.radio(
            get_text('menu_lang'),
            ["Korean", "English"],
            index=0 if st.session_state.language == 'Korean' else 1,
            key='lang_radio'
        )
        
        if new_lang != st.session_state.language:
            st.session_state.language = new_lang
            st.rerun()

        st.divider()
        st.caption("ver 1.0.0")

st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

# ==========================================
# [UI] 메인 콘텐츠
# ==========================================

# 타이틀 & 설명
st.markdown(f'<div class="main-title">{get_text("page_title")}</div>', unsafe_allow_html=True)
st.markdown(f"""
<div class="sub-description">
    {get_text("sub_description")}
</div>
""", unsafe_allow_html=True)

# 파일 업로더
uploaded_files = st.file_uploader(
    get_text('upload_label'),
    accept_multiple_files=True, 
    type=['png', 'jpg', 'jpeg', 'heic', 'bmp'],
    key=f"uploader_{st.session_state.uploader_key}",
    label_visibility="collapsed"
)

# 기능 컨트롤 영역
if uploaded_files:
    st.write("") 
    
    with st.container(border=True):
        col_opt, col_act = st.columns([1, 1.2], gap="large")
        
        # [옵션]
        with col_opt:
            st.markdown(f"**{get_text('format_label')}**")
            c1, c2 = st.columns(2)
            with c1:
                opt_pdf = st.checkbox("PDF", value=True)
            with c2:
                opt_zip = st.checkbox("ZIP", value=False)
        
        # [액션]
        with col_act:
            st.write("") 
            
            # (A) 변환 시작
            if st.session_state.processed_data is None:
                btn_text_base = get_text('split_btn')
                count_text = f"({len(uploaded_files)} files)" if st.session_state.language == 'English' else f"({len(uploaded_files)}장)"
                
                if st.button(f"{btn_text_base} {count_text}", type="primary", use_container_width=True):
                    if not opt_pdf and not opt_zip:
                        st.warning(get_text('warning_msg'))
                    else:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        processed_list = []
                        
                        try:
                            total = len(uploaded_files)
                            process_msg = get_text('processing_msg')
                            
                            for i, file in enumerate(uploaded_files):
                                status_text.text(f"{process_msg} {i+1} / {total}")
                                results = process_image_in_memory(file)
                                
                                for fname, zip_buf, pdf_img in results:
                                    base, ext = os.path.splitext(fname)
                                    if any(x[0] == fname for x in processed_list):
                                        fname = f"{base}_{i}{ext}"
                                    processed_list.append((fname, zip_buf, pdf_img))
                                
                                progress_bar.progress((i + 1) / total)
                            
                            st.session_state.processed_data = processed_list
                            status_text.empty()
                            progress_bar.empty()
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error: {e}")

            # (B) 다운로드
            else:
                data_list = st.session_state.processed_data
                
                if opt_pdf:
                    pdf_buffer = io.BytesIO()
                    pil_imgs = [item[2] for item in data_list]
                    if pil_imgs:
                        pil_imgs[0].save(pdf_buffer, format="PDF", save_all=True, append_images=pil_imgs[1:], resolution=100.0)
                        st.download_button(
                            label=get_text('download_pdf'),
                            data=pdf_buffer.getvalue(),
                            file_name="split_book.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )

                if opt_zip:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zf:
                        for fname, z_buf, _ in data_list:
                            zf.writestr(fname, z_buf.getvalue())
                    
                    st.download_button(
                        label=get_text('download_zip'),
                        data=zip_buffer.getvalue(),
                        file_name="split_images.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
    
    # 초기화 버튼
    if st.session_state.processed_data is not None:
        st.write("")
        if st.button(get_text('reset_btn'), on_click=reset_app, use_container_width=True):
            pass
