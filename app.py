import streamlit as st
import os
import re
import zipfile
import io
import pytesseract
from PIL import Image, ImageOps
from pytesseract import Output
from pillow_heif import register_heif_opener

register_heif_opener()

# --- (기존 함수들: preprocess..., find_largest... 등 여기에 복사) ---

def process_image_in_memory(uploaded_file):
    """파일을 저장하지 않고 메모리 상에서 처리"""
    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img)
    
    w, h = img.size
    c_x = w // 2
    
    img_l = img.crop((0, 0, c_x, h))
    img_r = img.crop((c_x, 0, w, h))
    
    # 번호 인식 로직 호출 (기존 함수 재사용)
    # 여기서는 예시로 파일명만 생성합니다.
    # 실제로는 find_largest_number_across_corners 함수 사용
    
    name_only = os.path.splitext(uploaded_file.name)[0]
    
    # 메모리 버퍼에 저장
    buf_l = io.BytesIO()
    img_l.save(buf_l, format="JPEG", quality=95)
    
    buf_r = io.BytesIO()
    img_r.save(buf_r, format="JPEG", quality=95)
    
    return [
        (f"{name_only}_L.jpg", buf_l),
        (f"{name_only}_R.jpg", buf_r)
    ]

# --- Streamlit UI 구성 ---
st.title("📚 책 스캔 분할기 (Web)")
st.write("이미지를 업로드하면 자동으로 반으로 자르고 번호를 인식합니다.")

uploaded_files = st.file_uploader("이미지 선택 (여러 개 가능)", accept_multiple_files=True, type=['png', 'jpg', 'heic'])

if uploaded_files and st.button("변환 시작"):
    # ZIP 파일 생성을 위한 메모리 버퍼
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        progress_bar = st.progress(0)
        
        for i, file in enumerate(uploaded_files):
            results = process_image_in_memory(file)
            
            # ZIP에 추가
            for fname, img_data in results:
                zf.writestr(fname, img_data.getvalue())
            
            progress_bar.progress((i + 1) / len(uploaded_files))
            
    st.success("완료되었습니다!")
    
    # 다운로드 버튼 생성
    st.download_button(
        label="📥 결과물 다운로드 (ZIP)",
        data=zip_buffer.getvalue(),
        file_name="split_images.zip",
        mime="application/zip"
    )
