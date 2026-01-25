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
# [설정] 세션 상태 초기화
# ==========================================
# 파일 업로더 키
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0
# 변환된 데이터를 저장할 저장소
if 'processed_results' not in st.session_state:
    st.session_state.processed_results = None

def reset_app():
    st.session_state.uploader_key += 1
    st.session_state.processed_results = None
    st.rerun()

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

    [data-testid="stFileUploader"] button {
        background-color: #ffffff !important;
        border: 1px solid #d1d5db !important;
        border-radius: 6px !important;
        padding: 0.4rem 1.0rem !important;
    }

    /* 🎛️ 컨트롤 박스 디자인 */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border: 2px dashed #a0a5b5 !important;
        border-radius: 12px !important;
        background-color: #f8f9fa !important;
        padding: 20px !important;
    }

    /* 버튼 스타일 - 붉은색 강조 */
    div.stButton > button[kind="primary"] {
        background-color: #d9534f !important;
        border: none !important;
        color: white !important;
        width: 100% !important;
        padding: 0.5rem 1rem !important;
        font-weight: 600 !important;
        margin-top: 2px !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #c9302c !important;
    }
    
    /* 다운로드 버튼 (성공 시) 스타일 - 초록색 계열로 변경하여 완료 느낌 주기 (선택 사항) */
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

    /* 멀티 셀렉트 박스 스타일 */
    .stMultiSelect div[data-baseweb="select"] {
        background-color: white !important;
        border-color: #d1d5db !important;
    }

    /* 🚫 "No results" 숨기기 (드롭다운 메뉴의 리스트 아이템 중 텍스트가 없는 경우 등) */
    /* Streamlit 구조상 완벽한 타겟팅은 어렵지만, 드롭다운이 비었을 때 시각적 노이즈 제거 */
    ul[data-testid="stSelectboxVirtualDropdown"] li:first-child {
        /* "No results" 텍스트를 포함하는 요소가 보통 첫번째 li로 렌더링됨. 
           주의: 실제 옵션이 하나일 때 숨겨질 위험이 있으나, 현재 multiselect는 선택된 상태이므로 안전 */
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
st.title("📖 책 스캔 이미지 분할기")

st.markdown("""
<div style="margin-bottom: 20px; color: #555;">
    두 쪽을 한 판에 스캔한 이미지를 업로드하면 반반 잘라서<br>
    하나의 PDF로 합치거나 ZIP으로 다운로드 할 수 있습니다.
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

# 파일 업로드 시에만 컨트롤 박스 표시
if uploaded_files:
    st.write("") 
    
    # 2. 컨트롤 박스 (점선 테두리)
    with st.container(border=True):
        col_menu, col_btn = st.columns([1, 1], gap="medium")
        
        with col_menu:
            # 멀티 선택 메뉴
            selected_formats = st.multiselect(
                "저장 포맷 선택",
                ["PDF", "ZIP"],
                default=["PDF"],
                label_visibility="collapsed",
                placeholder="저장 포맷 선택"
            )
        
        with col_btn:
            # 상태 A: 아직 변환 전이거나, 새로 파일을 올렸을 때 -> [변환 버튼] 표시
            if st.session_state.processed_results is None:
                if st.button(f"SPLIT IMAGE ({len(uploaded_files)}장)", type="primary", use_container_width=True):
                    
                    # === 변환 로직 시작 ===
                    if not selected_formats:
                        st.warning("⚠️ 포맷을 선택해주세요.")
                    else:
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        processed_data_list = []
                        
                        try:
                            for i, file in enumerate(uploaded_files):
                                status_text.text(f"✂️ 자르는 중... ({i+1}/{len(uploaded_files)})")
                                results = process_image_in_memory(file)
                                
                                for fname, zip_buf, pdf_img in results:
                                    base, ext = os.path.splitext(fname)
                                    if any(x[0] == fname for x in processed_data_list):
                                        fname = f"{base}_{i}{ext}"
                                    processed_data_list.append((fname, zip_buf, pdf_img))
                                
                                progress_bar.progress((i + 1) / len(uploaded_files))
                            
                            # 처리 완료 후 세션에 저장
                            st.session_state.processed_results = processed_data_list
                            status_text.empty()
                            progress_bar.empty()
                            
                            # 화면 리로드하여 버튼을 '다운로드'로 교체
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"오류 발생: {e}")
            
            # 상태 B: 변환 완료 -> [다운로드 버튼] 표시
            else:
                # 사용자가 선택한 포맷에 따라 다운로드 버튼 렌더링
                # PDF와 ZIP 둘 다 선택했으면 둘 중 하나를 메인으로 보여주거나 둘 다 표시
                
                # 1. PDF 다운로드 버튼
                if "PDF" in selected_formats:
                    pdf_buffer = io.BytesIO()
                    pil_images = [item[2] for item in st.session_state.processed_results]
                    if pil_images:
                        pil_images[0].save(
                            pdf_buffer, 
                            format="PDF", 
                            save_all=True, 
                            append_images=pil_images[1:],
                            resolution=100.0
                        )
                        st.download_button(
                            label="📕 PDF 다운로드",
                            data=pdf_buffer.getvalue(),
                            file_name="split_book.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )

                # 2. ZIP 다운로드 버튼 (PDF와 ZIP 동시 선택 시 아래에 추가 표시)
                if "ZIP" in selected_formats:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zf:
                        for fname, zip_buf, _ in st.session_state.processed_results:
                            zf.writestr(fname, zip_buf.getvalue())
                    
                    st.download_button(
                        label="🗂️ ZIP 다운로드",
                        data=zip_buffer.getvalue(),
                        file_name="split_images.zip",
                        mime="application/zip",
                        use_container_width=True
                    )

    # 변환 완료 상태일 때만 '처음으로' 버튼 표시
    if st.session_state.processed_results is not None:
        st.write("")
        if st.button("🔄 처음으로 (초기화)", on_click=reset_app, use_container_width=True):
            pass
