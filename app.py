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
LANG_MAP = {
    '한국어': 'Korean',
    'English (영어)': 'English',
    '中文 (중국어)': 'Chinese',
    '日本語 (일본어)': 'Japanese',
    'français (프랑스어)': 'French'
}
LANG_MAP_REV = {v: k for k, v in LANG_MAP.items()}

TRANSLATIONS = {
    'page_title': { 'Korean': 'T-Splitter', 'English': 'T-Splitter', 'Chinese': 'T-Splitter', 'Japanese': 'T-Splitter', 'French': 'T-Splitter' },
    'sub_description': {
        'Korean': '두 쪽을 한 판에 스캔한 이미지를 업로드하면<br> 반반 잘라서 하나의 PDF 또는 ZIP 파일로 제공됩니다.',
        'English': 'If you upload an image that contains two pages scanned together,<br> it will be split into two separate pages and provided as a single PDF or a ZIP file.',
        'Chinese': '上传包含两页扫描在一起的图像，<br>它将被分成两个单独的页面，并作为单个PDF或ZIP文件提供。',
        'Japanese': '2ページを1枚にスキャンした画像をアップロードすると、<br>半分に分割して1つのPDFまたはZIPファイルとして提供されます。',
        'French': 'Si vous téléchargez une image contenant deux pages numérisées ensemble,<br> elle sera divisée en deux pages distinctes et fournie sous forme de fichier PDF ou ZIP unique.'
    },
    'upload_label': { 'Korean': '이미지 파일 업로드', 'English': 'Upload Image Files', 'Chinese': '上传图像文件', 'Japanese': '画像ファイルをアップロード', 'French': 'Télécharger des fichiers image' },
    'format_label': { 'Korean': '저장 형식', 'English': 'Save Format', 'Chinese': '保存格式', 'Japanese': '保存形式', 'French': 'Format d\'enregistrement' },
    'sort_label': { 'Korean': '정렬 순서 (파일명 기준)', 'English': 'Sort Order (Filename)', 'Chinese': '排序顺序 (文件名)', 'Japanese': '並び順 (ファイル名)', 'French': 'Ordre de tri (nom de fichier)' },
    'sort_asc': { 'Korean': '오름차순 (1→9)', 'English': 'Ascending (1→9)', 'Chinese': '升序 (1→9)', 'Japanese': '昇順 (1→9)', 'French': 'Croissant (1→9)' },
    'sort_desc': { 'Korean': '내림차순 (9→1)', 'English': 'Descending (9→1)', 'Chinese': '降序 (9→1)', 'Japanese': '降順 (9→1)', 'French': 'Décroissant (9→1)' },
    'split_btn': { 'Korean': '변환 시작하기', 'English': 'Start Converting', 'Chinese': '开始转换', 'Japanese': '変換を開始', 'French': 'Commencer la conversion' },
    'warning_msg': { 'Korean': '⚠️ 저장할 형식을 최소 하나 선택해주세요 (PDF 또는 ZIP)', 'English': '⚠️ Please select at least one format (PDF or ZIP)', 'Chinese': '⚠️ 请至少选择一种格式 (PDF 或 ZIP)', 'Japanese': '⚠️ 保存する形式を少なくとも1つ選択してください (PDF または ZIP)', 'French': '⚠️ Veuillez sélectionner au moins un format (PDF ou ZIP)' },
    'processing_msg': { 'Korean': '처리 중...', 'English': 'Processing...', 'Chinese': '处理中...', 'Japanese': '処理中...', 'French': 'Traitement...' },
    'download_pdf': { 'Korean': '📗 PDF 다운로드', 'English': '📗 Download PDF', 'Chinese': '📗 下载 PDF', 'Japanese': '📗 PDFをダウンロード', 'French': '📗 Télécharger le PDF' },
    'download_zip': { 'Korean': '🗂️ ZIP 다운로드', 'English': '🗂️ Download ZIP', 'Chinese': '🗂️ 下载 ZIP', 'Japanese': '🗂️ ZIPをダウンロード', 'French': '🗂️ Télécharger le ZIP' },
    'reset_btn': { 'Korean': '🗑️ 처음으로 (초기화)', 'English': '🗑️ Reset (Start Over)', 'Chinese': '🗑️ 重置 (重新开始)', 'Japanese': '🗑️ リセット (最初から)', 'French': '🗑️ Réinitialiser' },
    'footer_copyright': { 'Korean': '© 2026 T-Splitter. All rights reserved.', 'English': '© 2026 T-Splitter. All rights reserved.', 'Chinese': '© 2026 T-Splitter. All rights reserved.', 'Japanese': '© 2026 T-Splitter. All rights reserved.', 'French': '© 2026 T-Splitter. All rights reserved.' },
    'footer_contact': { 'Korean': '문의: hoon1018@knou.ac.kr', 'English': 'Contact: hoon1018@knou.ac.kr', 'Chinese': 'Contact: hoon1018@knou.ac.kr', 'Japanese': 'Contact: hoon1018@knou.ac.kr', 'French': 'Contact: hoon1018@knou.ac.kr' }
}

def get_text(key):
    lang = st.session_state.language
    return TRANSLATIONS[key].get(lang, TRANSLATIONS[key].get('English', TRANSLATIONS[key]['Korean']))

# ==========================================
# [스타일] CSS (버튼: 흰색/Bold, 체크박스: 검정)
# ==========================================
custom_style = """
<style>
    /* Global Reset */
    * { box-sizing: border-box; }
    html, body, [class*="css"], [class*="st-"], button, input, textarea, div, span, p, h1, h2, label {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        color: #333;
    }
    body { background-color: #f9f9f9; }
    header[data-testid="stHeader"] { visibility: hidden; }

    /* Main Container */
    .block-container {
        max-width: 640px;
        margin: 2rem auto;
        background: #fff;
        padding: 40px !important;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }

    /* Header */
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

    /* Upload Area */
    [data-testid="stFileUploader"] section {
        border: 2px dashed #ddd !important;
        background: #fafafa !important;
        border-radius: 10px !important;
    }
    [data-testid="stFileUploader"] section:hover {
        border-color: #007bff !important;
        background: #f0f8ff !important;
    }

    /* ================================================================
       [버튼 스타일] 변환 시작하기
       - 배경: 파란색 (#007bff)
       - 글자: 흰색 (#ffffff) / 굵게 (Bold)
       ================================================================ */
    div.stButton > button[kind="primary"] {
        background-color: #007bff !important;
        color: #ffffff !important; /* 글자색 흰색 */
        border: none !important;
        padding: 15px !important;
        border-radius: 8px !important;
        font-size: 16px !important;
        font-weight: 700 !important; /* 글자 굵게 (Bold) */
        margin-top: 10px;
        box-shadow: none !important;
    }
    
    /* 버튼 내부 텍스트(p태그 등)까지 강제 적용 */
    div.stButton > button[kind="primary"] * {
        color: #ffffff !important;
        font-weight: 700 !important;
    }

    div.stButton > button[kind="primary"]:hover { 
        background-color: #0056b3 !important; 
    }
    div.stButton > button[kind="primary"]:focus:not(:active) {
        color: #ffffff !important;
        border-color: transparent !important;
    }

    /* ================================================================
       [체크박스 & 라디오 버튼 색상: 검정(#333)]
       ================================================================ */
    /* 1. HTML 표준 accent-color */
    input[type="checkbox"], input[type="radio"] {
        accent-color: #333333 !important;
    }
    
    /* 2. Streamlit 테마 변수 강제 오버라이드 (기본 붉은색 제거) */
    :root {
        --primary-color: #333333 !important;
    }

    /* 3. 내부 요소 직접 타겟팅 */
    div[data-baseweb="checkbox"] [aria-checked="true"] {
        background-color: #333333 !important;
        border-color: #333333 !important;
    }
    div[data-baseweb="radio"] [aria-checked="true"] > div:first-child {
        background-color: #333333 !important;
        border-color: #333333 !important;
    }
    div[data-baseweb="radio"] [aria-checked="true"] > div:first-child > div {
        background-color: #ffffff !important;
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
    
    /* Selectbox */
    div[data-baseweb="select"] > div {
        font-size: 14px !important;
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
# [UI] 헤더 영역
# ==========================================
h_col1, h_col2 = st.columns([3, 1.2])

with h_col1:
    st.markdown(f'<h1 class="header-title">{get_text("page_title")}</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="header-subtitle">{get_text("sub_description")}</p>', unsafe_allow_html=True)

with h_col2:
    st.markdown('<div style="font-size:13px; font-weight:600; color:#555; margin-bottom:4px;">🌎 Language</div>', unsafe_allow_html=True)
    
    current_label = LANG_MAP_REV.get(st.session_state.language, '한국어')
    
    selected_lang_label = st.selectbox(
        "Language",
        list(LANG_MAP.keys()),
        index=list(LANG_MAP.keys()).index(current_label),
        label_visibility="collapsed"
    )
    
    new_lang_code = LANG_MAP[selected_lang_label]
    if new_lang_code != st.session_state.language:
        st.session_state.language = new_lang_code
        st.rerun()

st.markdown('<div class="header-divider"></div>', unsafe_allow_html=True)


# ==========================================
# [UI] 메인 콘텐츠 영역
# ==========================================

# 1. 파일 업로드
st.markdown(f'<div style="font-size:14px; font-weight:600; margin-bottom:8px;">{get_text("upload_label")}</div>', unsafe_allow_html=True)

uploaded_files = st.file_uploader(
    label="file_uploader_fixed",      
    label_visibility="collapsed",     
    accept_multiple_files=True, 
    type=['png', 'jpg', 'jpeg', 'heic', 'bmp'],
    key=f"uploader_{st.session_state.uploader_key}"
)

if uploaded_files:
    st.write("") 
    
    # 2. 옵션
    col_opt1, col_opt2 = st.columns(2)
    
    with col_opt1:
        st.markdown(f'<span style="font-weight:600; font-size:15px; display:block; margin-bottom:15px;">{get_text("format_label")}</span>', unsafe_allow_html=True)
        c_fmt1, c_fmt2 = st.columns(2)
        with c_fmt1:
            opt_pdf = st.checkbox("PDF", value=True, key=f"chk_pdf_{st.session_state.uploader_key}")
        with c_fmt2:
            opt_zip = st.checkbox("ZIP", value=False, key=f"chk_zip_{st.session_state.uploader_key}")
        
    with col_opt2:
        sort_option = 'asc'
        if opt_pdf:
            st.markdown(f'<span style="font-weight:600; font-size:15px; display:block; margin-bottom:15px;">{get_text("sort_label")}</span>', unsafe_allow_html=True)
            sort_option = st.radio(
                "Sort",
                ["asc", "desc"],
                format_func=lambda x: get_text('sort_asc') if x == 'asc' else get_text('sort_desc'),
                label_visibility="collapsed",
                key=f"radio_sort_{st.session_state.uploader_key}"
            )

    # 3. 변환 및 다운로드
    st.write("") 
    
    if st.session_state.processed_data is None:
        btn_text_base = get_text('split_btn')
        count_text = f"({len(uploaded_files)} files)" if st.session_state.language == 'English' else f"({len(uploaded_files)}장)"
        
        # 버튼에 type="primary"가 적용되어 CSS 스타일을 받습니다.
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
# [UI] 푸터
# ==========================================
st.markdown(f"""
<div class="footer">
    <p>{get_text('footer_copyright')}</p>
    <p>{get_text('footer_contact')}</p>
</div>
""", unsafe_allow_html=True)
