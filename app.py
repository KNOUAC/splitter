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
# [설정] 페이지 기본 설정 (가장 위에 있어야 함)
# ==========================================
st.set_page_config(
    page_title="책 스캔 분할기", 
    page_icon="📖",
    layout="centered", 
    initial_sidebar_state="collapsed"
)

# ==========================================
# [설정] 모바일 화면 최적화
# ==========================================
mobile_style = """
<style>
    /* 기본 폰트 적용 */
    html, body, [class*="css"] {
        font-family: 'Suit', sans-serif;
    }

    /* 📱 모바일 환경 (화면 너비 640px 이하) 설정 */
    @media only screen and (max-width: 640px) {
        
        /* 1. 레이아웃: 여백을 살짝 주어 답답하지 않게 */
        .block-container {
            padding-top: 2rem !important;
            padding-left: 1rem !important; 
            padding-right: 1rem !important;
            max-width: 100% !important;
        }

        /* 2. 제목: 적당히 강조 */
        h1 {
            font-size: 26px !important; 
            margin-bottom: 0.5rem !important;
        }
        
        h3 {
            font-size: 20px !important;
        }
        
        /* 3. 본문 텍스트: 모바일 표준 크기 */
        .stMarkdown p, .stMarkdown li, p {
            font-size: 16px !important;
            line-height: 1.5 !important;
        }

        /* 4. 파일 업로더 */
        [data-testid="stFileUploader"] section {
            padding: 1rem !important; 
        }
        
        /* 안내 문구 크기 줄임 */
        [data-testid="stFileUploader"] div, 
        [data-testid="stFileUploader"] span, 
        [data-testid="stFileUploader"] small {
            font-size: 14px !important; 
        }

        /* 5. 버튼: 터치하기 좋게 */
        .stButton button, .stDownloadButton button {
            width: 100% !important;
            font-size: 18px !important;
            padding: 0.6rem !important;
            margin-top: 0.5rem !important;
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
    except Exception:
        return None
    return None

def process_image_in_memory(uploaded_file):
    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img)
    
    # RGBA -> RGB 변환
    if img.mode in ('RGBA', 'P'):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == 'P': img = img.convert('RGBA')
        if img.mode == 'RGBA':
            background.paste(img, mask=img.split()[3])
            img = background
        else:
            img = img.convert('RGB')
    elif img.mode != 'RGB':
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
    
    # PDF 생성을 위해 PIL 이미지 객체 자체도 반환 (img_l, img_r)
    return [(fname_l, buf_l, img_l), (fname_r, buf_r, img_r)]

# ==========================================
# [UI] 화면 구성
# ==========================================
st.title("📖 책 스캔 이미지 반 잘라드려요~")

st.markdown("""
### 🃏 사용 설명
양쪽을 한 판에 스캔한 이미지(JPG, PNG, HEIC)를 업로드하면:
1. 일괄 **반으로 자르고** 🀱
2. **하나의 PDF**로 묶거나 **ZIP**으로 다운로드할 수 있습니다.
""")

st.write("---")

uploaded_files = st.file_uploader(
    "👇 아래 영역을 터치하여 사진을 선택하세요", 
    accept_multiple_files=True, 
    type=['png', 'jpg', 'jpeg', 'heic', 'bmp']
)

if uploaded_files:
    if st.button(f"🚀 총 {len(uploaded_files)}장 변환 시작하기", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 결과를 저장할 리스트 (순서 유지)
        processed_data_list = []
        
        try:
            for i, file in enumerate(uploaded_files):
                status_text.text(f"⏳ 처리 중... ({i+1}/{len(uploaded_files)})")
                
                # 이미지 처리 (파일명, 바이트버퍼, PIL이미지객체 반환)
                results = process_image_in_memory(file)
                
                for fname, img_buf, img_pil in results:
                    # 중복 파일명 방지 로직
                    base, ext = os.path.splitext(fname)
                    # 리스트에 이미 같은 이름이 있는지 확인
                    if any(x[0] == fname for x in processed_data_list):
                        fname = f"{base}_{i}{ext}"
                    
                    processed_data_list.append((fname, img_buf, img_pil))
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_text.success("✅ 변환 완료! 원하는 포맷으로 다운로드하세요.")
            progress_bar.progress(100)

            # --- [다운로드 옵션 준비] ---
            
            # 1. ZIP 생성
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for fname, img_buf, _ in processed_data_list:
                    zf.writestr(fname, img_buf.getvalue())
            
            # 2. PDF 생성
            pdf_buffer = io.BytesIO()
            if processed_data_list:
                # PIL 이미지 리스트 추출
                pil_images = [item[2] for item in processed_data_list]
                # 첫 번째 이미지를 기준으로 나머지를 append하여 PDF 저장
                pil_images[0].save(
                    pdf_buffer, 
                    format="PDF", 
                    save_all=True, 
                    append_images=pil_images[1:],
                    resolution=100.0
                )

            st.write("") # 여백
            
            # 모바일에서 버튼 두 개가 나란히 보이도록 컬럼 분할
            col1, col2 = st.columns(2)
            
            with col1:
                st.download_button(
                    label="📕 PDF로 받기",
                    data=pdf_buffer.getvalue(),
                    file_name="split_book.pdf",
                    mime="application/pdf",
                    type="primary"
                )
            
            with col2:
                st.download_button(
                    label="🗂️ ZIP으로 받기",
                    data=zip_buffer.getvalue(),
                    file_name="split_images.zip",
                    mime="application/zip"
                )

        except Exception as e:
            st.error(f"⚠️ 오류 발생: {e}")
