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
# [기본 설정] HEIC 지원 및 페이지 설정
# ==========================================
register_heif_opener()

st.set_page_config(
    page_title="책 스캔 분할기", 
    page_icon="📚",
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# ==========================================
# [상태 관리] 세션 데이터 초기화
# ==========================================
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.processed_data = None
    st.session_state.uploader_key += 1
    st.rerun()

# ==========================================
# [스타일] CSS (웹 도구 스타일 적용)
# ==========================================
custom_style = """
<style>
    /* 기본 폰트 및 배경 */
    html, body, [class*="css"] {
        font-family: 'Suit', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #333;
    }

    /* 1. 상단 헤더 숨기기 & 여백 조정 (앱 느낌 나게) */
    header[data-testid="stHeader"] {
        visibility: hidden;
    }
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        max-width: 700px;
    }

    /* 2. 타이틀 및 설명 중앙 정렬 */
    .main-title {
        font-size: 26px; /* 요청하신대로 크기 축소 (-1) */
        font-weight: 700;
        text-align: center;
        margin-bottom: 0.5rem;
        color: #111;
    }
    .sub-description {
        text-align: center;
        color: #666;
        font-size: 15px;
        margin-bottom: 30px;
        line-height: 1.6;
    }

    /* 3. 업로드 박스 디자인 (스크린샷처럼 점선 박스) */
    [data-testid="stFileUploader"] section {
        border: 2px dashed #ccc !important;
        background-color: #fafafa !important;
        border-radius: 10px !important;
        padding: 40px 20px !important;
        text-align: center;
    }
    [data-testid="stFileUploader"] section:hover {
        border-color: #d9534f !important; /* 호버 시 포인트 컬러 */
        background-color: #fff !important;
    }

    /* 4. 버튼 디자인 (꽉 찬 버튼) */
    div.stButton > button[kind="primary"] {
        background-color: #d9534f !important; /* 포인트 컬러 (붉은 계열) */
        border: none;
        color: white;
        width: 100%;
        padding: 0.7rem;
        font-size: 16px;
        font-weight: 600;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #c9302c !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    /* 다운로드 버튼 (초록색) */
    div.stDownloadButton > button {
        background-color: #28a745 !important;
        border: none;
        color: white;
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
    }

    /* 5. 네비게이션 바 시뮬레이션 (상단 로고 영역) */
    .navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 15px;
        border-bottom: 1px solid #eee;
        margin-bottom: 30px;
    }
    .logo {
        font-weight: 800;
        font-size: 18px;
        color: #333;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .menu-icon {
        font-size: 20px;
        color: #999;
        cursor: pointer;
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

# 1. 상단 네비게이션 바 (가짜 메뉴)
st.markdown("""
<div class="navbar">
    <div class="logo">책 스캔 이미지 반반 분할기</div>
    <div class="menu-icon">☰</div>
</div>
""", unsafe_allow_html=True)

# 2. 메인 타이틀 & 설명 (중앙 정렬)
st.markdown('<div class="main-title">책 스캔 이미지 분할기</div>', unsafe_allow_html=True)
st.markdown("""
<div class="sub-description">
    📖 두 쪽을 한 판에 스캔한 이미지를 업로드하면<br>
    반반 잘라서 하나의 PDF로 합치거나 ZIP으로 다운로드를 제공합니다.
</div>
""", unsafe_allow_html=True)

# 3. 파일 업로더
uploaded_files = st.file_uploader(
    "이미지 파일 선택 (JPG, PNG, HEIC)",
    accept_multiple_files=True, 
    type=['png', 'jpg', 'jpeg', 'heic', 'bmp'],
    key=f"uploader_{st.session_state.uploader_key}",
    label_visibility="collapsed" # 라벨 숨김 (깔끔하게)
)

# 4. 기능 컨트롤 영역 (파일이 올라오면 표시)
if uploaded_files:
    st.write("") # 여백
    
    # 박스 형태로 감싸기
    with st.container(border=True):
        col_opt, col_act = st.columns([1, 1.2], gap="large")
        
        # [옵션] 체크박스 (No results 문제 해결)
        with col_opt:
            st.markdown("**저장 형식**", help="원하는 포맷을 선택하세요.")
            c1, c2 = st.columns(2)
            with c1:
                opt_pdf = st.checkbox("PDF", value=True)
            with c2:
                opt_zip = st.checkbox("ZIP", value=False)
        
        # [액션] 변환 or 다운로드
        with col_act:
            st.write("") # 줄맞춤용 빈 공간
            
            # (A) 아직 처리 전 -> 변환 버튼
            if st.session_state.processed_data is None:
                if st.button(f"✂️ SPLIT IMAGE ({len(uploaded_files)}장)", type="primary", use_container_width=True):
                    if not opt_pdf and not opt_zip:
                        st.warning("⚠️ 저장할 형식을 선택해주세요 (PDF 또는 ZIP)")
                    else:
                        # 변환 로직 시작
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        processed_list = []
                        
                        try:
                            total = len(uploaded_files)
                            for i, file in enumerate(uploaded_files):
                                status_text.text(f"처리 중... {i+1} / {total}")
                                results = process_image_in_memory(file)
                                
                                for fname, zip_buf, pdf_img in results:
                                    # 중복 방지
                                    base, ext = os.path.splitext(fname)
                                    if any(x[0] == fname for x in processed_list):
                                        fname = f"{base}_{i}{ext}"
                                    processed_list.append((fname, zip_buf, pdf_img))
                                
                                progress_bar.progress((i + 1) / total)
                            
                            # 완료 후 상태 저장 및 리로드
                            st.session_state.processed_data = processed_list
                            status_text.empty()
                            progress_bar.empty()
                            st.rerun() # 화면 갱신 -> 다운로드 버튼 표시
                            
                        except Exception as e:
                            st.error(f"오류 발생: {e}")

            # (B) 처리 완료 -> 다운로드 버튼
            else:
                data_list = st.session_state.processed_data
                
                # PDF 다운로드
                if opt_pdf:
                    pdf_buffer = io.BytesIO()
                    pil_imgs = [item[2] for item in data_list]
                    if pil_imgs:
                        pil_imgs[0].save(pdf_buffer, format="PDF", save_all=True, append_images=pil_imgs[1:], resolution=100.0)
                        st.download_button(
                            label="📕 PDF 다운로드",
                            data=pdf_buffer.getvalue(),
                            file_name="split_book.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )

                # ZIP 다운로드
                if opt_zip:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zf:
                        for fname, z_buf, _ in data_list:
                            zf.writestr(fname, z_buf.getvalue())
                    
                    st.download_button(
                        label="🗂️ ZIP 다운로드",
                        data=zip_buffer.getvalue(),
                        file_name="split_images.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
    
    # 초기화 버튼
    if st.session_state.processed_data is not None:
        st.write("")
        if st.button("🔄 처음으로 (새로고침)", on_click=reset_app, use_container_width=True):
            pass
