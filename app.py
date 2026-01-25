import streamlit as st
import streamlit.components.v1 as components
import os
import re
import zipfile
import io
import base64
import pytesseract
from PIL import Image, ImageOps
from pytesseract import Output
from pillow_heif import register_heif_opener

# HEIC 파일 지원
register_heif_opener()

# ==========================================
# [설정] 세션 상태 초기화
# ==========================================
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# ==========================================
# [기능] 자동 다운로드 트리거 함수 (JS 주입)
# ==========================================
def auto_download(data_bytes, file_name, mime_type):
    """
    Python 변환 데이터를 Base64로 인코딩하여
    브라우저가 즉시 다운로드하도록 JavaScript를 실행합니다.
    """
    b64 = base64.b64encode(data_bytes).decode()
    payload = f'<a id="download_link" href="data:{mime_type};base64,{b64}" download="{file_name}" style="display:none">Download</a>'
    
    # 링크를 생성하고 자동으로 클릭하는 스크립트
    js_code = f"""
    <script>
        var a = document.createElement('a');
        a.href = 'data:{mime_type};base64,{b64}';
        a.download = '{file_name}';
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    </script>
    """
    # Streamlit 컴포넌트로 JS 실행 (높이 0으로 숨김)
    components.html(js_code, height=0)

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

    /* 변환 버튼 (오른쪽) 스타일 - 붉은색 강조 */
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

    /* 멀티 셀렉트 박스 (왼쪽) 스타일 */
    .stMultiSelect div[data-baseweb="select"] {
        background-color: white !important;
        border-color: #d1d5db !important;
    }

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
    스캔한 이미지를 업로드하면 자동으로 반으로 자르고<br>
    페이지 번호를 인식해 파일명을 정리해 드립니다.
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

# 파일이 업로드 되면 -> 컨트롤 박스 표시
if uploaded_files:
    st.write("") 
    
    # 2. 컨트롤 박스 (점선 테두리)
    with st.container(border=True):
        col_menu, col_btn = st.columns([1, 1], gap="medium")
        
        with col_menu:
            selected_formats = st.multiselect(
                "저장 포맷 선택",
                ["PDF", "ZIP"],
                default=["PDF"],
                label_visibility="collapsed",
                placeholder="저장 포맷 선택 (PDF/ZIP)"
            )
            
        with col_btn:
            # "SPLIT IMAGE" 버튼
            start_btn = st.button(
                f"SPLIT IMAGE ({len(uploaded_files)}장)", 
                type="primary", 
                use_container_width=True
            )

    # 버튼 클릭 시 -> 변환 -> 즉시 다운로드 실행
    if start_btn:
        if not selected_formats:
            st.warning("⚠️ 저장 포맷을 최소 하나 선택해주세요.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            processed_data_list = []
            
            try:
                # 1. 변환 작업 수행
                for i, file in enumerate(uploaded_files):
                    status_text.text(f"⏳ 열심히 자르는 중... ({i+1}/{len(uploaded_files)})")
                    results = process_image_in_memory(file)
                    
                    for fname, zip_buf, pdf_img in results:
                        base, ext = os.path.splitext(fname)
                        if any(x[0] == fname for x in processed_data_list):
                            fname = f"{base}_{i}{ext}"
                        processed_data_list.append((fname, zip_buf, pdf_img))
                    
                    progress_bar.progress((i + 1) / len(uploaded_files))
                
                status_text.success("✅ 완료! 다운로드가 자동으로 시작됩니다.")
                progress_bar.progress(100)
                
                # 2. 결과물 생성 및 자동 다운로드 트리거
                
                # (A) PDF 자동 다운로드
                if "PDF" in selected_formats:
                    pdf_buffer = io.BytesIO()
                    if processed_data_list:
                        pil_images = [item[2] for item in processed_data_list]
                        pil_images[0].save(
                            pdf_buffer, 
                            format="PDF", 
                            save_all=True, 
                            append_images=pil_images[1:],
                            resolution=100.0
                        )
                        # JS로 다운로드 실행
                        auto_download(pdf_buffer.getvalue(), "split_book.pdf", "application/pdf")

                # (B) ZIP 자동 다운로드
                if "ZIP" in selected_formats:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zf:
                        for fname, zip_buf, _ in processed_data_list:
                            zf.writestr(fname, zip_buf.getvalue())
                    
                    # JS로 다운로드 실행
                    auto_download(zip_buffer.getvalue(), "split_images.zip", "application/zip")
                
                # 안내 메시지
                st.toast("파일 다운로드가 시작되었습니다! 🚀", icon="📥")
                
                # 초기화 버튼
                st.write("") 
                if st.button("🔄 처음으로 (초기화)", on_click=reset_app, use_container_width=True):
                    pass

            except Exception as e:
                st.error(f"⚠️ 오류 발생: {e}")
