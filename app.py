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
# [설정] 세션 상태 초기화 (새로고침 기능용)
# ==========================================
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    """업로더 키를 변경하여 파일 선택을 초기화하는 콜백"""
    st.session_state.uploader_key += 1

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
# [설정] 모바일 화면 & UI 최적화 CSS
# ==========================================
mobile_style = """
<style>
    html, body, [class*="css"] {
        font-family: 'Suit', sans-serif;
    }

    /* 체크박스 정렬 보정 */
    div[data-testid="stCheckbox"] {
        margin-top: 10px; /* 버튼과 높이 맞추기 */
    }

    /* 📱 모바일 환경 설정 */
    @media only screen and (max-width: 640px) {
        .block-container {
            padding-top: 2rem !important;
            padding-left: 1rem !important; 
            padding-right: 1rem !important;
            max-width: 100% !important;
        }
        h1 { font-size: 26px !important; margin-bottom: 0.5rem !important; }
        h3 { font-size: 20px !important; }
        .stMarkdown p, .stMarkdown li, p { font-size: 16px !important; line-height: 1.5 !important; }
        
        [data-testid="stFileUploader"] section { padding: 1rem !important; }
        [data-testid="stFileUploader"] div, [data-testid="stFileUploader"] span, [data-testid="stFileUploader"] small {
            font-size: 14px !important; 
        }

        /* 버튼 및 다운로드 버튼 */
        .stButton button, .stDownloadButton button {
            width: 100% !important;
            font-size: 18px !important;
            padding: 0.6rem !important;
        }
    }
</style>
"""
st.markdown(mobile_style, unsafe_allow_html=True)

# ==========================================
# [로직] 이미지 처리 함수들
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
    """
    브라우저 보기 편하도록 PDF용 이미지는 너비를 줄임 (A4 화면 최적화)
    원본 비율 유지, 너비 최대 1240px (약 150dpi 수준)
    """
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
        
    # ZIP용 원본 화질 버퍼
    buf_l = io.BytesIO()
    img_l.save(buf_l, format="JPEG", quality=95)
    
    buf_r = io.BytesIO()
    img_r.save(buf_r, format="JPEG", quality=95)
    
    # PDF용 리사이징 이미지 (객체 반환)
    img_l_pdf = resize_for_pdf(img_l)
    img_r_pdf = resize_for_pdf(img_r)
    
    return [(fname_l, buf_l, img_l_pdf), (fname_r, buf_r, img_r_pdf)]

# ==========================================
# [UI] 화면 구성
# ==========================================
st.title("📖 책 스캔 이미지 반반 분할")

st.markdown("""
### 🃏 사용 설명
양쪽을 한 판에 스캔한 이미지(JPG, PNG, HEIC, BMP)를 업로드하면:
1. 일괄 반으로 자르고 🀱
2. 하나의 PDF로 묶거나 ZIP으로 다운로드할 수 있습니다.
""")

st.write("---")

# 파일 업로더 (key를 설정하여 초기화 가능하게 함)
uploaded_files = st.file_uploader(
    "👇 아래 영역을 터치하여 사진을 선택하세요", 
    accept_multiple_files=True, 
    type=['png', 'jpg', 'jpeg', 'heic', 'bmp'],
    key=f"uploader_{st.session_state.uploader_key}" # 동적 키 할당
)

if uploaded_files:
    # 옵션 선택 및 실행 버튼 UI 구성
    st.write("#### ⚙️ 저장 옵션 선택")
    
    # 모바일 보기 편하게 컬럼 비율 조정
    col_opt1, col_opt2, col_btn = st.columns([1, 1, 2])
    
    with col_opt1:
        use_pdf = st.checkbox("📕 PDF", value=True)
    with col_opt2:
        use_zip = st.checkbox("🗂️ ZIP", value=False)
    
    with col_btn:
        start_btn = st.button(f"🚀 {len(uploaded_files)}장 변환 시작", type="primary")

    if start_btn:
        if not use_pdf and not use_zip:
            st.warning("⚠️ 최소 하나의 저장 방식을 선택해주세요 (PDF 또는 ZIP)")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            processed_data_list = []
            
            try:
                for i, file in enumerate(uploaded_files):
                    status_text.text(f"⏳ 처리 중... ({i+1}/{len(uploaded_files)})")
                    
                    results = process_image_in_memory(file)
                    
                    for fname, zip_buf, pdf_img in results:
                        base, ext = os.path.splitext(fname)
                        if any(x[0] == fname for x in processed_data_list):
                            fname = f"{base}_{i}{ext}"
                        
                        processed_data_list.append((fname, zip_buf, pdf_img))
                    
                    progress_bar.progress((i + 1) / len(uploaded_files))
                
                status_text.success("✅ 변환 완료! 아래 버튼을 눌러 저장하세요.")
                progress_bar.progress(100)
                
                st.write("---") # 결과 구분선

                # --- [다운로드 버튼 영역] ---
                down_cols = st.columns(2)
                
                # 1. PDF 생성 및 다운로드 버튼
                if use_pdf:
                    pdf_buffer = io.BytesIO()
                    if processed_data_list:
                        pil_images = [item[2] for item in processed_data_list] # 리사이징된 이미지 사용
                        pil_images[0].save(
                            pdf_buffer, 
                            format="PDF", 
                            save_all=True, 
                            append_images=pil_images[1:],
                            resolution=100.0
                        )
                    with down_cols[0]:
                        st.download_button(
                            label="📕 PDF 다운로드",
                            data=pdf_buffer.getvalue(),
                            file_name="split_book.pdf",
                            mime="application/pdf",
                            type="primary"
                        )

                # 2. ZIP 생성 및 다운로드 버튼
                if use_zip:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zf:
                        for fname, zip_buf, _ in processed_data_list:
                            zf.writestr(fname, zip_buf.getvalue()) # 원본 화질 버퍼 사용
                    
                    with down_cols[1]:
                        st.download_button(
                            label="🗂️ ZIP 다운로드",
                            data=zip_buffer.getvalue(),
                            file_name="split_images.zip",
                            mime="application/zip"
                        )
                
                # --- [초기화 버튼] ---
                st.write("") 
                st.write("") 
                if st.button("🔄 업로드 목록 초기화", on_click=reset_app):
                    pass # 콜백에서 처리되므로 여기는 비워둠

            except Exception as e:
                st.error(f"⚠️ 오류 발생: {e}")

# 파일이 없을 때 안내 문구 (깔끔하게)
elif not uploaded_files:
    st.info("👆 위 박스를 눌러 파일을 불러와주세요.")
