import streamlit as st
import os
import re
import zipfile
import io
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

# ==========================================
# [기본 설정] 페이지 설정 및 초기화
# ==========================================
register_heif_opener()

st.set_page_config(
    page_title="Theowise Book Splitter", 
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
    # on_click 콜백이 끝나면 Streamlit이 '자동으로' 화면을 갱신합니다.
    st.session_state.processed_data = None
    st.session_state.uploader_key += 1

# ==========================================
# [유틸] 자연 정렬 (Natural Sort) 함수
# ==========================================
def atoi(text):
    return int(text) if text.isdigit() else text

def natural_keys(text):
    return [atoi(c) for c in re.split(r'(\d+)', text)]

# ==========================================
# [다국어 데이터]
# ==========================================
TRANSLATIONS = {
    'page_title': {
        'Korean': '책 스캔 이미지 반반 분할기',
        'English': 'Book scan image left-right splitter'
    },
    'sub_description': {
        'Korean': '두 쪽을 한 판에 스캔한 이미지를 업로드하면<br> 반반 잘라서 하나의 PDF 또는 ZIP 파일로 제공됩니다.',
        'English': 'If you upload an image that contains two pages scanned together,<br> it will be split into two separate pages and provided as a single PDF or a ZIP file.'
    },
    'upload_label': {
        'Korean': '여기를 터치해 이미지 선택 (JPG, PNG, HEIC, BMP)',
        'English': 'Touch here to select images (JPG, PNG, HEIC, BMP)'
    },
    'format_label': {
        'Korean': '저장 형식',
        'English': 'Save Format'
    },
    'sort_label': { 
        'Korean': '정렬 순서 (파일명 기준)',
        'English': 'Sort Order (Filename)'
    },
    'sort_asc': { 
        'Korean': '오름차순 (1→9)',
        'English': 'Ascending (1→9)'
    },
    'sort_desc': { 
        'Korean': '내림차순 (9→1)',
        'English': 'Descending (9→1)'
    },
    'split_btn': {
        'Korean': '⌖ 변환 시작하기',
        'English': '⌖ Start splitting'
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
        'Korean': '📗 PDF 다운로드',
        'English': '📗 Download PDF'
    },
    'download_zip': {
        'Korean': '🗂️ ZIP 다운로드',
        'English': '🗂️ Download ZIP'
    },
    'reset_btn': {
        'Korean': '🗑️ 처음으로 (초기화)',
        'English': '🗑️ Reset (Start Over)'
    },
    'menu_settings': {
        'Korean': '언어 (Language)', 
        'English': '언어 (Language)' 
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
# [스타일] CSS (강제 적용 버전)
# ==========================================
custom_style = """
<style>
    /* 폰트 임포트 */
    @import url('https://fonts.googleapis.com/css2?family=Gothic+A1:wght@300;400;500;600;700;800;900&display=swap');

    /* 1. 기본 폰트 설정 */
    html, body, [class*="css"], [class*="st-"], button, input, textarea, div, span, p {
        font-family: 'Gothic A1', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: #333;
    }

    /* 2. 테마 색상 변수 강제 덮어쓰기 (가장 중요) */
    :root {
        --primary-color: #38b6ff !important;
        --st-color-primary: #38b6ff !important;
    }

    /* Streamlit 헤더 숨김 */
    header[data-testid="stHeader"] { visibility: hidden; }
    .block-container { padding-top: 3rem !important; padding-bottom: 2rem !important; max-width: 700px; }

    /* 로고 */
    .theowise-logo {
        font-family: 'Gothic A1', sans-serif !important;
        font-size: 28px;
        font-weight: 900 !important;
        color: #2c3e50;
        letter-spacing: -1px;
        text-decoration: none;
    }

    /* 업로드 박스 */
    [data-testid="stFileUploader"] section {
        border: 3px dashed #ccc !important;
        background-color: #fafafa !important;
        border-radius: 10px !important;
        padding: 40px 20px !important;
    }
    [data-testid="stFileUploader"] section:hover {
        border-color: #38b6ff !important;
        background-color: #e1f5fe !important;
    }
    [data-testid="stFileUploader"] button {
        border-color: #38b6ff !important;
        color: #38b6ff !important;
        background-color: transparent !important;
    }
    [data-testid="stFileUploader"] button:hover {
        border-color: #0288d1 !important;
        color: #0288d1 !important;
        background-color: #e1f5fe !important;
    }

    /* ★ 체크박스 색상 강제 변경 (aria-checked 사용) ★ */
    div[data-testid="stCheckbox"] div[role="checkbox"][aria-checked="true"] {
        background-color: #38b6ff !important;
        border-color: #38b6ff !important;
    }
    div[data-testid="stCheckbox"] div[role="checkbox"][aria-checked="true"] div {
        background-color: #38b6ff !important; /* 내부 체크 표시 색상 보정 */
    }

    /* ★ 라디오 버튼 색상 강제 변경 (aria-checked 사용) ★ */
    div[data-testid="stRadio"] div[role="radio"][aria-checked="true"] {
        background-color: #38b6ff !important;
        border-color: #38b6ff !important;
    }
    div[data-testid="stRadio"] div[role="radio"][tabindex="0"] {
        color: #38b6ff !important; /* 포커스 시 색상 */
    }

    /* ★ 변환 버튼 (Primary) ★ */
    div.stButton > button[kind="primary"] {
        background-color: #38b6ff !important;
        border: 1px solid #38b6ff !important;
        color: white !important;
        width: 100%;
        padding: 0.7rem;
        font-size: 16px;
        font-weight: 800 !important; /* 글자 더 굵게 */
        border-radius: 8px;
        text-shadow: 0 1px 3px rgba(0,0,0,0.2); /* 텍스트 그림자 강화 */
    }
    div.stButton > button[kind="primary"]:hover { 
        background-color: #0288d1 !important;
        border-color: #0288d1 !important;
        color: white !important;
    }
    
    /* 기타 스타일 */
    [data-testid="stFileUploaderDeleteBtn"] button { color: #888 !important; border: none !important; }
    [data-testid="stFileUploaderDeleteBtn"] button:hover { color: #333 !important; background: #eee !important; }
    [data-testid="stFileUploaderDeleteBtn"] svg { fill: #888 !important; }
    [data-testid="stFileUploaderDeleteBtn"]:hover svg { fill: #333 !important; }

    .main-title { font-size: 26px; font-weight: 700; text-align: center; margin-bottom: 0.5rem; color: #111; margin-top: 20px; }
    .sub-description { text-align: center; color: #666; font-size: 15px; margin-bottom: 30px; line-height: 1.6; }
    
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
# [로직] 이미지 처리 함수
# ==========================================
def process_image_in_memory(uploaded_file):
    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img)
    
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    w, h = img.size
    c_x = w // 2
    
    img_l = img.crop((0, 0, c_x, h))
    img_r = img.crop((c_x, 0, w, h))
    
    name_only = os.path.splitext(uploaded_file.name)[0]
    
    fname_l = f"{name_only}_01_L.jpg"
    fname_r = f"{name_only}_02_R.jpg"
        
    buf_l = io.BytesIO()
    img_l.save(buf_l, format="JPEG", quality=95)
    
    buf_r = io.BytesIO()
    img_r.save(buf_r, format="JPEG", quality=95)
    
    return [(fname_l, buf_l, img_l), (fname_r, buf_r, img_r)]

# ==========================================
# [UI] 상단 네비게이션 바
# ==========================================
st.markdown('<div class="theowise-logo">Theowise</div>', unsafe_allow_html=True)
st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

# ==========================================
# [UI] 메인 콘텐츠
# ==========================================

st.markdown(f'<div class="main-title">{get_text("page_title")}</div>', unsafe_allow_html=True)
st.markdown(f"""
<div class="sub-description">
    {get_text("sub_description")}
</div>
""", unsafe_allow_html=True)

st.markdown(
    f"<div style='text-align: center; font-weight: bold; margin-bottom: 10px;'>{get_text('upload_label')}</div>", 
    unsafe_allow_html=True
)

uploaded_files = st.file_uploader(
    "static_label", 
    accept_multiple_files=True, 
    type=['png', 'jpg', 'jpeg', 'heic', 'bmp'],
    key=f"uploader_{st.session_state.uploader_key}",
    label_visibility="collapsed" 
)

if uploaded_files:
    st.write("") 
    
    with st.container(border=True):
        col_opt, col_act = st.columns([1, 1.2], gap="large")
        
        with col_opt:
            st.markdown(f"**{get_text('format_label')}**")
            c_fmt1, c_fmt2 = st.columns(2)
            with c_fmt1:
                opt_pdf = st.checkbox("PDF", value=True)
            with c_fmt2:
                opt_zip = st.checkbox("ZIP", value=False)
            
            st.write("")
            
            sort_option = 'asc'
            if opt_pdf:
                st.markdown(f"**{get_text('sort_label')}**")
                sort_option = st.radio(
                    "Sort",
                    ["asc", "desc"],
                    format_func=lambda x: get_text('sort_asc') if x == 'asc' else get_text('sort_desc'),
                    label_visibility="collapsed"
                )

        with col_act:
            st.write("") 
            
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
                            
                            is_reverse = (sort_option == 'desc')
                            processed_list.sort(key=lambda x: natural_keys(x[0]), reverse=is_reverse)
                            
                            st.session_state.processed_data = processed_list
                            status_text.empty()
                            progress_bar.empty()
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error: {e}")

            else:
                data_list = st.session_state.processed_data
                
                if opt_pdf:
                    pdf_buffer = io.BytesIO()
                    pil_imgs = [item[2] for item in data_list]
                    if pil_imgs:
                        # [해상도 유지] 200.0 DPI (크롬 50% 줌 최적화)
                        pil_imgs[0].save(pdf_buffer, format="PDF", save_all=True, append_images=pil_imgs[1:], resolution=200.0)
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
    
    if st.session_state.processed_data is not None:
        st.write("")
        if st.button(get_text('reset_btn'), on_click=reset_app, use_container_width=True):
            pass
