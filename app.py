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
    # [원복] 잘 동작하던 app(1).py의 로직 그대로 사용
    # 별도의 st.rerun() 없이 키 값 변경만으로 업로더를 초기화합니다.
    st.session_state.processed_data = None
    st.session_state.uploader_key += 1

# ==========================================
# [유틸] 자연 정렬 (Natural Sort) 함수
# ==========================================
def atoi(text):
    return int(text) if text.isdigit() else text

def natural_keys(text):
    '''
    alist.sort(key=natural_keys) -> 1, 2, 10, 11, ... 순서로 정렬됨
    '''
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
# [스타일] CSS
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
    
    /* 상단 여백 조정 */
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
    
    /* 🟢 로고 스타일 (Impact 폰트 - 음영 제거) */
    .knouac-logo {
        font-family: 'Impact', sans-serif !important;
        font-size: 32px;
        font-weight: 400;
        color: #2c3e50;
        letter-spacing: 1px;
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
        font-size: 24px !important;
        padding: 0 10px !important;
        margin-top: -5px;
        box-shadow: none !important;
    }
    [data-testid="stPopover"] > button:hover {
        color: #d9534f !important;
        background: transparent !important;
    }

    /* 🟢 설정 메뉴 내부 (라디오 버튼 등) 폰트 변경: Trebuchet MS */
    [data-testid="stRadio"], 
    [data-testid="stRadio"] label, 
    [data-testid="stRadio"] div, 
    [data-testid="stRadio"] p {
        font-family: 'Trebuchet MS', sans-serif !important;
    }

    /* 🔵 라디오 버튼 선택 색상 (Red -> Blue) 강력 적용 */
    div[data-testid="stRadio"] label[data-checked="true"] div[role="radio"] {
        background-color: #007bff !important;
        border-color: #007bff !important;
    }
    div[data-testid="stRadio"] label[data-checked="true"] p {
        color: #007bff !important;
    }

    /* 🔵 체크박스(PDF/ZIP) 선택 색상 (Red -> Blue) 강력 적용 */
    div[data-testid="stCheckbox"] label[data-checked="true"] span[role="checkbox"] {
        background-color: #007bff !important;
        border-color: #007bff !important;
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

    /* 🟢 업로드 박스 디자인 */
    [data-testid="stFileUploader"] section {
        border: 4px dashed #ccc !important;
        background-color: #fafafa !important;
        border-radius: 10px !important;
        padding: 40px 20px !important;
        text-align: center;
    }
    
    /* 🔵 업로드 박스 호버/드래그 시 색상 변경 (Red -> Blue) */
    [data-testid="stFileUploader"] section:hover {
        border-color: #007bff !important; /* 파란색 */
        background-color: #f0f8ff !important; /* 아주 연한 파랑 배경 */
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
# [로직] 이미지 처리 함수 (파일명 기반 처리)
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
    
    # [수정] OCR 제거 -> 원본 파일명 기반 이름 생성
    # 파일명 오름차순 정렬을 위해 {파일명}_01_L, {파일명}_02_R 로 저장
    name_only = os.path.splitext(uploaded_file.name)[0]
    
    fname_l = f"{name_only}_01_L.jpg"
    fname_r = f"{name_only}_02_R.jpg"
        
    buf_l = io.BytesIO()
    img_l.save(buf_l, format="JPEG", quality=95)
    
    buf_r = io.BytesIO()
    img_r.save(buf_r, format="JPEG", quality=95)
    
    return [(fname_l, buf_l, img_l), (fname_r, buf_r, img_r)]

# ==========================================
# [UI] 상단 네비게이션 바 (Sticky Header)
# ==========================================
c1, c2 = st.columns([8, 1])

with c1:
    st.markdown('<div class="knouac-logo">KNOUAC</div>', unsafe_allow_html=True)

with c2:
    # ☰ 메뉴 팝오버
    with st.popover("☰", use_container_width=False):
        st.markdown(
            f"<div style='font-family: Trebuchet MS; font-weight: bold;'>{get_text('menu_settings')}</div>", 
            unsafe_allow_html=True
        )
        
        new_lang = st.radio(
            "Language", 
            ["Korean", "English"],
            index=0 if st.session_state.language == 'Korean' else 1,
            key='lang_radio',
            label_visibility="collapsed"
        )
        
        if new_lang != st.session_state.language:
            st.session_state.language = new_lang
            st.rerun()

        st.divider()
        st.caption("ver 1.0.1 THEOHYEON")

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
    key=f"uploader_{st.session_state.uploader_key}", # [원복] 잘 동작하던 동적 Key 방식 사용
    label_visibility="collapsed" 
)

# 기능 컨트롤 영역
if uploaded_files:
    st.write("") 
    
    with st.container(border=True):
        col_opt, col_act = st.columns([1, 1.2], gap="large")
        
        # [옵션]
        with col_opt:
            # 1. 저장 형식
            st.markdown(f"**{get_text('format_label')}**")
            c_fmt1, c_fmt2 = st.columns(2)
            with c_fmt1:
                opt_pdf = st.checkbox("PDF", value=True)
            with c_fmt2:
                opt_zip = st.checkbox("ZIP", value=False)
            
            st.write("") # 간격
            
            # 2. [추가] 정렬 순서 (PDF 선택 시에만 표시)
            sort_option = 'asc'
            if opt_pdf:
                st.markdown(f"**{get_text('sort_label')}**")
                sort_option = st.radio(
                    "Sort",
                    ["asc", "desc"],
                    format_func=lambda x: get_text('sort_asc') if x == 'asc' else get_text('sort_desc'),
                    label_visibility="collapsed"
                )

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
                                    # 중복 방지
                                    if any(x[0] == fname for x in processed_list):
                                        fname = f"{base}_{i}{ext}"
                                    processed_list.append((fname, zip_buf, pdf_img))
                                
                                progress_bar.progress((i + 1) / total)
                            
                            # 🟢 [추가] 정렬 로직 적용
                            is_reverse = (sort_option == 'desc')
                            processed_list.sort(key=lambda x: natural_keys(x[0]), reverse=is_reverse)
                            
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
                        # [해상도 유지] 200.0 DPI
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
    
    # 초기화 버튼
    if st.session_state.processed_data is not None:
        st.write("")
        if st.button(get_text('reset_btn'), on_click=reset_app, use_container_width=True):
            pass
