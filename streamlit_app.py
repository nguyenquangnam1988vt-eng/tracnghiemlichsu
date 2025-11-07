import streamlit as st
import requests
import pypdf
import docx
import json
import smtplib
import qrcode
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from io import BytesIO
import openai
from bs4 import BeautifulSoup
import re

# ====== CẤU HÌNH API ======
# Sử dụng secrets của Streamlit thay vì hardcode
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "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")  # ⚠️ KHÔNG public khóa thật ra ngoài

if not OPENAI_API_KEY or OPENAI_API_KEY == "your-api-key-here":
    st.error("⚠️ Vui lòng cấu hình OpenAI API Key trong secrets.toml")
    st.stop()

client = openai.OpenAI(api_key=OPENAI_API_KEY)

# ====== HÀM XỬ LÝ FILE ======
def extract_text_from_pdf(pdf_file):
    try:
        pdf_reader = pypdf.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    except Exception as e:
        st.error(f"Lỗi khi đọc PDF: {e}")
        return ""

def extract_text_from_docx(docx_file):
    try:
        doc = docx.Document(docx_file)
        text = "\n".join(p.text for p in doc.paragraphs)
        return text
    except Exception as e:
        st.error(f"Lỗi khi đọc Word: {e}")
        return ""

def extract_text_from_url(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text(separator='\n')
        return text[:5000]
    except Exception as e:
        st.error(f"Lỗi khi lấy nội dung từ URL: {e}")
        return ""

# ====== TẠO CÂU HỎI BẰNG AI - ĐÃ SỬA ======
def generate_quiz_questions(content, num_questions=20):
    # Làm sạch nội dung
    clean_content = re.sub(r'\s+', ' ', content).strip()
    
    if len(clean_content) < 100:
        st.error("Nội dung quá ngắn để tạo câu hỏi. Vui lòng cung cấp nội dung dài hơn.")
        return generate_sample_questions()
    
    prompt = f"""
BẮT BUỘC: Bạn PHẢI trả về ĐÚNG định dạng JSON dưới đây, KHÔNG thêm bất kỳ text nào khác.

Hãy tạo {num_questions} câu hỏi trắc nghiệm môn LỊCH SỬ VIỆT NAM dựa trên nội dung được cung cấp.

YÊU CẦU:
- Mỗi câu hỏi phải dựa TRỰC TIẾP vào thông tin trong nội dung
- 4 lựa chọn A, B, C, D (chỉ 1 đáp án đúng duy nhất)
- Câu hỏi phải kiểm tra hiểu biết về sự kiện, nhân vật, thời gian lịch sử
- Đáp án phải CHÍNH XÁC theo nội dung được cung cấp

ĐỊNH DẠNG JSON BẮT BUỘC:
{{
  "questions": [
    {{
      "question": "Câu hỏi?",
      "options": ["A. Lựa chọn A", "B. Lựa chọn B", "C. Lựa chọn C", "D. Lựa chọn D"],
      "correct_answer": "A"
    }}
  ]
}}

NỘI DUNG BÀI GIẢNG:
{clean_content[:4000]}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Bạn là chuyên gia giáo dục Lịch sử Việt Nam. Luôn trả về đúng định dạng JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=3000,
        )
        
        text = response.choices[0].message.content.strip()
        
        # Tìm JSON trong response
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            quiz_data = json.loads(json_str)
            
            # Kiểm tra cấu trúc
            if "questions" in quiz_data and isinstance(quiz_data["questions"], list):
                if len(quiz_data["questions"]) > 0:
                    st.success(f"✅ Đã tạo thành công {len(quiz_data['questions'])} câu hỏi!")
                    return quiz_data
        
        # Nếu không được, thử phương pháp dự phòng
        st.warning("⚠️ Thử phương pháp dự phòng...")
        return generate_quiz_fallback(clean_content, num_questions)
        
    except Exception as e:
        st.error(f"❌ Lỗi khi tạo câu hỏi: {e}")
        return generate_sample_questions()

def generate_quiz_fallback(content, num_questions=10):
    """Phương pháp dự phòng nếu GPT không trả về đúng format"""
    try:
        # Tạo ít câu hỏi hơn để đảm bảo chất lượng
        prompt = f"""
Tạo {min(num_questions, 10)} câu hỏi trắc nghiệm Lịch sử từ nội dung này.
Trả về JSON: {{"questions": [{{"question": "...", "options": ["A...","B...","C...","D..."], "correct_answer": "A"}}]}}

Nội dung: {content[:3000]}
"""
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        text = response.choices[0].message.content
        # Xử lý response để tìm JSON
        start_idx = text.find('{')
        end_idx = text.rfind('}') + 1
        if start_idx != -1 and end_idx != 0:
            json_str = text[start_idx:end_idx]
            return json.loads(json_str)
    except:
        pass
    
    # Cuối cùng trả về mẫu
    return generate_sample_questions()

def generate_sample_questions():
    """Câu hỏi mẫu khi mọi thứ thất bại"""
    return {
        "questions": [
            {
                "question": "Vua nào dựng nước Văn Lang, nhà nước đầu tiên của Việt Nam?",
                "options": [
                    "A. Hùng Vương",
                    "B. An Dương Vương", 
                    "C. Lý Nam Đế",
                    "D. Ngô Quyền"
                ],
                "correct_answer": "A"
            },
            {
                "question": "Chiến thắng Bạch Đằng năm 938 do ai lãnh đạo?",
                "options": [
                    "A. Ngô Quyền",
                    "B. Lê Hoàn",
                    "C. Trần Hưng Đạo", 
                    "D. Lý Thường Kiệt"
                ],
                "correct_answer": "A"
            }
        ]
    }

# ====== GỬI EMAIL ======
def send_email(receiver_email, subject, body, attachment_data=None, filename="quiz.json"):
    try:
        # THAY ĐỔI THÔNG TIN EMAIL CỦA BẠN Ở ĐÂY
        sender_email = "your-email@gmail.com"
        sender_password = "your-app-password"

        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = receiver_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        if attachment_data:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment_data)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={filename}")
            message.attach(part)

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)
        return True
    except Exception as e:
        st.error(f"Lỗi khi gửi email: {e}")
        return False

# ====== GIAO DIỆN ỨNG DỤNG ======
st.set_page_config(page_title="Hệ thống Trắc nghiệm Lịch sử", layout="wide")

st.title("🎯 Hệ thống Tạo & Tham gia Thi Trắc nghiệm Lịch sử")
st.markdown("---")

tab1, tab2 = st.tabs(["📝 Tạo Câu Hỏi Trắc nghiệm", "🎮 Tham Gia Thi"])

# ====== TAB 1: TẠO CÂU HỎI ======
with tab1:
    st.header("Tạo Câu Hỏi Trắc nghiệm từ Bài Giảng")
    
    # Thêm hướng dẫn
    st.info("""
    **Hướng dẫn sử dụng:**
    1. Tải lên file PDF/DOCX hoặc nhập URL bài giảng Lịch sử
    2. Kiểm tra nội dung trích xuất
    3. Nhấn nút 'Tạo Câu Hỏi' 
    4. Câu hỏi sẽ được tạo dựa trên nội dung bài giảng
    """)
    
    source_type = st.radio("Chọn nguồn tài liệu:",
                          ["📄 Tải lên file PDF", "📝 Tải lên file Word", "🌐 Nhập URL bài giảng"])
    
    content = ""
    
    if source_type == " Tải lên file PDF":
        pdf_file = st.file_uploader("Tải lên file PDF", type=["pdf"])
        if pdf_file:
            with st.spinner("Đang trích xuất nội dung từ PDF..."):
                content = extract_text_from_pdf(pdf_file)
    
    elif source_type == " Tải lên file Word":
        docx_file = st.file_uploader("Tải lên file Word", type=["docx"])
        if docx_file:
            with st.spinner("Đang trích xuất nội dung từ Word..."):
                content = extract_text_from_docx(docx_file)
    
    else:
        url = st.text_input("Nhập URL bài giảng:")
        if url:
            with st.spinner("Đang lấy nội dung từ URL..."):
                content = extract_text_from_url(url)
    
    if content:
        st.subheader("Nội dung đã trích xuất:")
        st.text_area("Nội dung", content[:1000] + "..." if len(content) > 1000 else content, 
                    height=200, key="extracted_content")
        
        # Hiển thị thông tin về nội dung
        st.info(f"Độ dài nội dung: {len(content)} ký tự")
    
    if st.button(" Tạo Câu Hỏi Trắc nghiệm", type="primary"):
        if not content:
            st.warning("⚠️ Vui lòng cung cấp nội dung bài giảng trước!")
        elif len(content.strip()) < 50:
            st.warning("⚠️ Nội dung quá ngắn. Vui lòng cung cấp nội dung dài hơn.")
        else:
            with st.spinner("🤖 AI đang phân tích nội dung và tạo câu hỏi... (có thể mất 1-2 phút)"):
                quiz_data = generate_quiz_questions(content, 20)
            
            if quiz_data and "questions" in quiz_data and len(quiz_data["questions"]) > 0:
                st.session_state.quiz_data = quiz_data
                st.success(f"✅ Đã tạo thành công {len(quiz_data['questions'])} câu hỏi trắc nghiệm!")
                
                st.subheader("📋 Câu hỏi đã tạo:")
                for i, q in enumerate(quiz_data["questions"], 1):
                    with st.expander(f"Câu {i}: {q['question']}"):
                        for option in q["options"]:
                            st.write(option)
                        st.write(f"**Đáp án đúng: {q['correct_answer']}**")
            else:
                st.error("❌ Không thể tạo câu hỏi. Vui lòng thử lại với nội dung khác.")

    # PHẦN XUẤT FILE & CHIA SẺ
    if "quiz_data" in st.session_state:
        st.markdown("---")
        st.subheader(" Xuất file & Chia sẻ")

        col1, col2, col3 = st.columns(3)

        with col1:
            json_data = json.dumps(st.session_state.quiz_data, ensure_ascii=False, indent=2)
            st.download_button(
                label=" Tải file JSON",
                data=json_data,
                file_name="cau_hoi_trac_nghiem.json",
                mime="application/json"
            )

        with col2:
            email = st.text_input("📧 Nhập email nhận file:", key="email_input")
            if st.button("Gửi qua Email", key="send_email"):
                if email:
                    if send_email(email, "Câu hỏi trắc nghiệm Lịch sử",
                                  "Đính kèm file câu hỏi trắc nghiệm đã tạo.",
                                  json_data.encode()):
                        st.success("✅ Đã gửi email thành công!")
                else:
                    st.warning("Vui lòng nhập email!")

        with col3:
            st.info("📱 Chia sẻ đến Zalo/Message:")
            qr = qrcode.make(json_data)
            buf = BytesIO()
            qr.save(buf, format="PNG")
            st.image(buf.getvalue(), caption="Quét QR code để chia sẻ", width=200)

# ====== TAB 2: THAM GIA THI ======
with tab2:
    st.header("Tham Gia Thi Trắc nghiệm")

    quiz_source = st.radio("Nguồn câu hỏi:",
                          [" Sử dụng câu hỏi đã tạo",
                           " Tải lên file câu hỏi JSON",
                           " Tải lên bài giảng PDF/DOCX",
                           " Nhập URL bài giảng"])

    quiz_data = None

    if quiz_source == " Sử dụng câu hỏi đã tạo":
        if "quiz_data" in st.session_state:
            quiz_data = st.session_state.quiz_data
            st.success(" Đã tải câu hỏi từ bộ nhớ!")
        else:
            st.warning(" Chưa có câu hỏi nào được tạo. Vui lòng tạo câu hỏi ở tab bên trái.")

    elif quiz_source == " Tải lên file câu hỏi JSON":
        uploaded_file = st.file_uploader("Tải lên file câu hỏi JSON", type=["json"])
        if uploaded_file:
            try:
                quiz_data = json.load(uploaded_file)
                st.success(" Đã tải file câu hỏi thành công!")
            except Exception as e:
                st.error(f" Lỗi khi đọc file: {e}")

    elif quiz_source == " Tải lên bài giảng PDF/DOCX":
        file = st.file_uploader("Tải lên file bài giảng PDF hoặc DOCX", type=["pdf", "docx"])
        if file:
            with st.spinner("Đang trích xuất nội dung bài giảng và tạo câu hỏi..."):
                if file.type == "application/pdf":
                    content = extract_text_from_pdf(file)
                elif file.type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                   "application/msword"]:
                    content = extract_text_from_docx(file)
                else:
                    content = ""
                if content:
                    quiz_data = generate_quiz_questions(content, 20)
                    st.success(" Đã tạo câu hỏi từ bài giảng!")
                else:
                    st.error(" Không thể trích xuất nội dung bài giảng.")

    else:  # Nhập URL
        url = st.text_input("Nhập URL bài giảng:", key="url_input")
        if url:
            with st.spinner("Đang lấy nội dung và tạo câu hỏi..."):
                content = extract_text_from_url(url)
                if content:
                    quiz_data = generate_quiz_questions(content, 20)
                    st.success(" Đã tạo câu hỏi từ URL!")
                else:
                    st.error(" Không thể lấy nội dung từ URL.")

    # Hiển thị bài thi nếu có dữ liệu
    if quiz_data and "questions" in quiz_data:
        st.markdown("---")
        st.subheader(" Bài Thi Trắc nghiệm")

        # Khởi tạo session state
        if "user_answers" not in st.session_state:
            st.session_state.user_answers = [None] * len(quiz_data["questions"])
        if "submitted" not in st.session_state:
            st.session_state.submitted = False
        if "current_quiz" not in st.session_state:
            st.session_state.current_quiz = quiz_data

        # Hiển thị các câu hỏi
        for i, question in enumerate(quiz_data["questions"]):
            st.markdown(f"### Câu {i+1}: {question['question']}")
            options = question["options"]
            
            # Tạo key duy nhất cho mỗi câu hỏi
            user_answer = st.radio(
                f"Chọn đáp án cho câu {i+1}:",
                options,
                key=f"quiz_q_{i}",
                index=st.session_state.user_answers[i] if st.session_state.user_answers[i] is not None else None
            )
            
            if user_answer:
                st.session_state.user_answers[i] = options.index(user_answer)

        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button(" Nộp Bài", type="primary", key="submit_quiz"):
                st.session_state.submitted = True
                st.rerun()

        # Nút làm lại bài
        with col2:
            if st.button(" Làm lại bài", key="reset_quiz"):
                st.session_state.user_answers = [None] * len(quiz_data["questions"])
                st.session_state.submitted = False
                st.rerun()

        # Hiển thị kết quả sau khi nộp bài
        if st.session_state.submitted:
            st.markdown("---")
            st.subheader(" Kết Quả Bài Thi")

            correct_count = 0
            for i, question in enumerate(quiz_data["questions"]):
                user_answer_index = st.session_state.user_answers[i]
                correct_answer = question["correct_answer"]

                if user_answer_index is not None:
                    user_answer_letter = question["options"][user_answer_index][0]  # Lấy chữ cái A/B/C/D
                    is_correct = (user_answer_letter == correct_answer)

                    if is_correct:
                        correct_count += 1

                    # Hiển thị kết quả từng câu
                    if is_correct:
                        st.success(f" Câu {i+1}: ĐÚNG - Đáp án của bạn: {user_answer_letter}")
                    else:
                        st.error(f" Câu {i+1}: SAI - Đáp án của bạn: {user_answer_letter}, Đáp án đúng: {correct_answer}")
                else:
                    st.warning(f" Câu {i+1}: Chưa trả lời - Đáp án đúng: {correct_answer}")

            total_questions = len(quiz_data["questions"])
            score_percent = (correct_count / total_questions) * 100 if total_questions > 0 else 0

            st.metric("Số câu đúng", f"{correct_count}/{total_questions}")
            st.metric("Tỷ lệ đúng", f"{score_percent:.1f}%")

            # Đánh giá kết quả
            if score_percent >= 90:
                st.success(" Xuất sắc! Bạn có kiến thức lịch sử rất tốt!")
            elif score_percent >= 70:
                st.info(" Khá tốt! Tiếp tục phát huy nhé!")
            elif score_percent >= 50:
                st.warning(" Cố gắng hơn nữa!")
            else:
                st.error(" Cần ôn tập lại kiến thức!")

# ====== FOOTER ======
st.markdown("---")
st.markdown("Ứng dụng được phát triển bởi [Le Thi Ngoc Duyen] - Sử dụng AI để tạo câu hỏi trắc nghiệm")
