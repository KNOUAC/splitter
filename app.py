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

# 페이지 타이틀을 HTML 디자인에 맞춰 "T-Splitter"로 변경
st.set_page_config(
    page_title="T-Splitter", 
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
        'Korean': 'T-Splitter',
        'English': 'T-Splitter'
    },
    'sub_description': {
        'Korean': '두 쪽을 한 판에 스캔한 이미지를 업로드하면<br> 반반 잘라서 하나의 PDF 또는 ZIP 파일로 제공됩니다.',
        'English': 'If you upload an image that contains two pages scanned together,<br> it will be split into two separate pages and provided as a single PDF or a ZIP file.'
    },
    'upload_label': {
        'Korean': '이미지 파일 업로드',
        'English': 'Upload Image Files'
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
        'Korean': '변환 시작하기',
        'English': 'Start Converting'
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
        'Korean': '언어 설정',
        'English': 'Language Settings'
    },
     'footer_copyright': {
        'Korean': '© 2024 T-Splitter. All rights reserved.',
        'English': '© 2024 T-Splitter. All rights reserved.'
    },
    'footer_contact': {
        'Korean': '문의: support@tsplitter.com',
        'English': 'Contact: support@tsplitter.com'
    }
}

def get_text(key):
    lang = st.session_state.language
    return TRANSLATIONS[key].get(lang, TRANSLATIONS[key]['Korean'])

# ==========================================
# [스타일] CSS (HTML 디자인 반영)
# ==========================================
custom_style = """
<style>
    /* Global Reset & Fonts from HTML */
    * {
        box-sizing: border-box;
    }
    html, body, [class*="css"], [class*="st-"], button, input, textarea, div, span, p, h1, h2, label {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol" !important;
        color: #333;
    }
    body {
        background-color: #f9f9f9;
    }

    /* Hide default Streamlit header */
    header[data-testid="stHeader"] {
        visibility: hidden;
    }

    /* Main Layout Container */
    .block-container {
        max-width: 640px;
        margin: 2rem auto;
        background: #fff;
        padding: 40px !important;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }

    /* Header Styles */
    .header-title {
        font-size: 28px;
        font-weight: 700;
        margin-bottom: 10px;
        color: #111;
    }
    .header-subtitle {
        font-size: 15px;
        color: #666;
        line-height: 1.5;
    }
    .header-divider {
        border-bottom: 1px solid #eee;
        margin-bottom: 2.5rem;
        padding-bottom: 1.5rem;
    }

    /* Language Button Styling */
    [data-testid="stPopover"] > button {
        padding: 8px 12px !important;
        border: 1px solid #ddd !important;
        border-radius: 6px !important;
        background: #fff !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        color: #555 !important;
        box-shadow: none !important;
    }
    [data-testid="stPopover"] > button:hover {
        background: #f5f5f5 !important;
        border-color: #ccc !important;
        color: #333 !important;
    }

    /* Upload Section Styling */
    [data-testid="stFileUploader"] {
        margin-bottom: 2rem;
    }
    [data-testid="stFileUploader"] label {
        font-weight: 600;
        font-size: 15px;
        margin-bottom: 10px;
        display: block;
    }
    [data-testid="stFileUploader"] section {
        border: 2px dashed #ddd !important;
        border-radius: 10px !important;
        padding: 40px 20px !important;
        text-align: center;
        background: #fafafa !important;
    }
    [data-testid="stFileUploader"] section:hover {
        border-color: #007bff !important;
        background: #f0f8ff !important;
    }
    /* Browse files button inside uploader */
    [data-testid="stFileUploader"] button[kind="secondary"] {
        background-color: #007bff !important;
        color: white !important;
        border: none !important;
        padding: 8px 15px !important;
        border-radius: 5px !important;
        font-size: 14px !important;
        font-weight: 500 !important;
        margin-top: 10px;
        box-shadow: none !important;
    }
     [data-testid="stFileUploader"] button[kind="secondary"]:hover {
        background-color: #0056b3 !important;
     }


    /* Options Section Labels */
    .options-label {
        font-weight: 600;
        font-size: 15px;
        margin-bottom: 15px;
        display: block;
    }

    /* Checkbox & Radio Styling (Cleaner look) */
    [data-testid="stCheckbox"] label, [data-testid="stRadio"] label {
        font-size: 14px;
    }
    /* Custom color for selected state */
    div[data-testid="stChecked"] > div:first-child {
        background-color: #007bff !important;
        border-color: #007bff !important;
    }


    /* Convert Button (Primary) */
    div.stButton > button[kind="primary"] {
        width: 100%;
        padding: 15px !important;
        background-color: #007bff !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-size: 16px !important;
        font-weight: 600 !important;
        margin-top: 1rem;
        box-shadow: none !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #0056b3 !important;
    }

    /* Download Button (Secondary/Success) */
    div.stDownloadButton > button {
        width: 100%;
        padding: 12px !important;
        background-color: #28a745 !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        box-shadow: none !important;
    }
     div.stDownloadButton > button:hover {
        background-color: #218838 !important;
    }


    /* Footer */
    .footer {
        text-align: center;
        margin-top: 3rem;
        padding-top: 1.5rem;
        border-top: 1px solid #eee;
        font-size: 13px;
        color: #888;
        line-height: 1.6;
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
# [UI] 헤더 영역 (HTML 디자인 반영)
# ==========================================
# 타이틀과 언어 변경 버튼을 포함한 헤더
h_col1, h_col2 = st.columns([3, 1])
with h_col1:
    st.markdown(f'<h1 class="header-title">{get_text("page_title")}</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="header-subtitle">{get_text("sub_description")}</p>', unsafe_allow_html=True)

with h_col2:
    # 언어 변경 팝오버 버튼 (우측 상단 배치)
    with st.popover("Language", use_container_width=True):
        st.markdown(f"<div style='font-weight: bold; margin-bottom: 10px;'>{get_text('menu_lang')}</div>", unsafe_allow_html=True)
        new_lang = st.radio(
            "Language Selection", 
            ["Korean", "English"],
            index=0 if st.session_state.language == 'Korean' else 1,
            key='lang_radio',
            label_visibility="collapsed"
        )
        if new_lang != st.session_state.language:
            st.session_state.language = new_lang
            st.rerun()

st.markdown('<div class="header-divider"></div>', unsafe_allow_html=True)


# ==========================================
# [UI] 메인 콘텐츠 영역
# ==========================================

# 1. 파일 업로드 섹션
uploaded_files = st.file_uploader(
    get_text('upload_label'),
    accept_multiple_files=True, 
    type=['png', 'jpg', 'jpeg', 'heic', 'bmp'],
    key=f"uploader_{st.session_state.uploader_key}"
)

if uploaded_files:
    st.write("") # 간격 추가
    
    # 2. 옵션 선택 섹션 (저장 형식, 정렬 순서)
    col_opt1, col_opt2 = st.columns(2)
    
    with col_opt1:
        st.markdown(f'<span class="options-label">{get_text("format_label")}</span>', unsafe_allow_html=True)
        c_fmt1, c_fmt2 = st.columns(2)
        with c_fmt1:
            opt_pdf = st.checkbox("PDF", value=True)
        with c_fmt2:
            opt_zip = st.checkbox("ZIP", value=False)
        
    with col_opt2:
        sort_option = 'asc'
        if opt_pdf:
            st.markdown(f'<span class="options-label">{get_text("sort_label")}</span>', unsafe_allow_html=True)
            sort_option = st.radio(
                "Sort",
                ["asc", "desc"],
                format_func=lambda x: get_text('sort_asc') if x == 'asc' else get_text('sort_desc'),
                label_visibility="collapsed"
            )

    # 3. 변환 버튼 및 결과 처리 영역
    st.write("") # 간격 추가
    
    if st.session_state.processed_data is None:
        btn_text_base = get_text('split_btn')
        count_text = f"({len(uploaded_files)} files)" if st.session_state.language == 'English' else f"({len(uploaded_files)}장)"
        
        # 전체 너비의 파란색 버튼
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
        # 처리 완료 후 다운로드 버튼 및 초기화 버튼 표시
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
            
        st.write("")
        if st.button(get_text('reset_btn'), on_click=reset_app, use_container_width=True):
            pass

# ==========================================
# [UI] 푸터 영역
# ==========================================
st.markdown(f"""
<div class="footer">
    <p>{get_text('footer_copyright')}</p>
    <p>{get_text('footer_contact')}</p>
</div>
""", unsafe_allow_html=True)
