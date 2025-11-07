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


# ====== CẤU HÌNH API ======
OPENAI_API_KEY = "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"  # ⚠️ KHÔNG public khóa thật ra ngoài
openai.api_key = OPENAI_API_KEY  # Gán trực tiếp API key tại đây


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
        # Lấy text sạch, ngắt dòng bằng newline
        text = soup.get_text(separator='\n')
        return text[:5000]  # Giới hạn lấy 5000 ký tự
    except Exception as e:
        st.error(f"Lỗi khi lấy nội dung từ URL: {e}")
        return ""


# ====== TẠO CÂU HỎI BẰNG AI (OpenAI API) ======
def generate_quiz_questions(content, num_questions=20):
    prompt = f"""
Hãy tạo {num_questions} câu hỏi trắc nghiệm LỊCH SỬ dựa trên nội dung sau.
Mỗi câu hỏi có 4 lựa chọn (A, B, C, D) và chỉ có 1 đáp án đúng.
Định dạng JSON:
{{
  "questions": [
    {{
      "question": "Câu hỏi",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "correct_answer": "A"
    }}
  ]
}}

Nội dung:
{content[:3000]}
"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500,
        )
        content = response['choices'][0]['message']['content']
        # Cố gắng trích xuất JSON trong response
        start_idx = content.find('{')
        end_idx = content.rfind('}') + 1
        json_str = content[start_idx:end_idx]
        return json.loads(json_str)
    except Exception as e:
        st.error(f"Lỗi khi tạo câu hỏi: {e}")
        return generate_sample_questions()


def generate_sample_questions():
    return {
        "questions": [
            {"question": "Ai là vị vua đầu tiên của nhà Nguyễn?",
             "options": ["A. Gia Long", "B. Minh Mạng", "C. Thiệu Trị", "D. Tự Đức"],
             "correct_answer": "A"},
            {"question": "Chiến thắng Điện Biên Phủ vào năm nào?",
             "options": ["A. 1953", "B. 1954", "C. 1955", "D. 1956"],
             "correct_answer": "B"}
        ]
    }


# ====== GỬI EMAIL ======
def send_email(receiver_email, subject, body, attachment_data=None, filename="quiz.json"):
    try:
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

    source_type = st.radio("Chọn nguồn tài liệu:",
                          ["📄 Tải lên file PDF", "📝 Tải lên file Word", "🌐 Nhập URL bài giảng"])

    content = ""

    if source_type == "📄 Tải lên file PDF":
        pdf_file = st.file_uploader("Tải lên file PDF", type=["pdf"])
        if pdf_file:
            with st.spinner("Đang trích xuất nội dung từ PDF..."):
                content = extract_text_from_pdf(pdf_file)

    elif source_type == "📝 Tải lên file Word":
        docx_file = st.file_uploader("Tải lên file Word", type=["docx"])
        if docx_file:
            with st.spinner("Đang trích xuất nội dung từ Word..."):
                content = extract_text_from_docx(docx_file)

    else:  # URL
        url = st.text_input("Nhập URL bài giảng:")
        if url:
            with st.spinner("Đang lấy nội dung từ URL..."):
                content = extract_text_from_url(url)

    if content:
        st.subheader("Nội dung đã trích xuất:")
        st.text_area("Nội dung", content[:1000] + "..." if len(content) > 1000 else content, height=200)

    if st.button("🎯 Tạo 20 Câu Hỏi Trắc nghiệm", type="primary"):
        if not content:
            st.warning("Vui lòng cung cấp nội dung bài giảng trước!")
        else:
            with st.spinner("AI đang tạo câu hỏi trắc nghiệm... (có thể mất 1-2 phút)"):
                quiz_data = generate_quiz_questions(content, 20)

            if quiz_data and "questions" in quiz_data:
                st.session_state.quiz_data = quiz_data
                st.success("✅ Đã tạo thành công 20 câu hỏi trắc nghiệm!")

                st.subheader("📋 Câu hỏi đã tạo:")
                for i, q in enumerate(quiz_data["questions"], 1):
                    with st.expander(f"Câu {i}: {q['question']}"):
                        for option in q["options"]:
                            st.write(option)
                        st.write(f"**Đáp án đúng: {q['correct_answer']}**")

    if "quiz_data" in st.session_state:
        st.markdown("---")
        st.subheader("📤 Xuất file & Chia sẻ")

        col1, col2, col3 = st.columns(3)

        with col1:
            json_data = json.dumps(st.session_state.quiz_data, ensure_ascii=False, indent=2)
            st.download_button(
                label="💾 Tải file JSON",
                data=json_data,
                file_name="cau_hoi_trac_nghiem.json",
                mime="application/json"
            )

        with col2:
            email = st.text_input("📧 Nhập email nhận file:")
            if st.button("Gửi qua Email"):
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


# ====== TAB 2: THAM GIA THI (BỔ SUNG TỰ ĐỘNG TẠO CÂU HỎI TỪ BÀI GIẢNG) ======
with tab2:
    st.header("Tham Gia Thi Trắc nghiệm")

    quiz_source = st.radio("Nguồn câu hỏi:",
                          ["📁 Sử dụng câu hỏi đã tạo",
                           "📤 Tải lên file câu hỏi JSON",
                           "📄 Tải lên bài giảng PDF/DOCX",
                           "🌐 Nhập URL bài giảng"])

    quiz_data = None

    if quiz_source == "📁 Sử dụng câu hỏi đã tạo":
        if "quiz_data" in st.session_state:
            quiz_data = st.session_state.quiz_data
            st.success("Đã tải câu hỏi từ bộ nhớ!")
        else:
            st.warning("Chưa có câu hỏi nào được tạo. Vui lòng tạo câu hỏi ở tab bên trái.")

    elif quiz_source == "📤 Tải lên file câu hỏi JSON":
        uploaded_file = st.file_uploader("Tải lên file câu hỏi JSON", type=["json"])
        if uploaded_file:
            try:
                quiz_data = json.load(uploaded_file)
                st.success("✅ Đã tải file câu hỏi thành công!")
            except Exception as e:
                st.error(f"Lỗi khi đọc file: {e}")

    elif quiz_source == "📄 Tải lên bài giảng PDF/DOCX":
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
                    st.success("✅ Đã tạo câu hỏi từ bài giảng!")
                else:
                    st.error("Không thể trích xuất nội dung bài giảng.")

    else:  # Nhập URL
        url = st.text_input("Nhập URL bài giảng:")
        if url:
            with st.spinner("Đang lấy nội dung và tạo câu hỏi..."):
                content = extract_text_from_url(url)
                if content:
                    quiz_data = generate_quiz_questions(content, 20)
                    st.success("✅ Đã tạo câu hỏi từ URL!")
                else:
                    st.error("Không thể lấy nội dung từ URL.")

    # Hiển thị bài thi nếu có dữ liệu
    if quiz_data and "questions" in quiz_data:
        st.markdown("---")
        st.subheader("📝 Bài Thi Trắc nghiệm")

        if "user_answers" not in st.session_state or len(st.session_state.user_answers) != len(quiz_data["questions"]):
            st.session_state.user_answers = [None] * len(quiz_data["questions"])
        if "submitted" not in st.session_state:
            st.session_state.submitted = False

        for i, question in enumerate(quiz_data["questions"]):
            st.markdown(f"### Câu {i+1}: {question['question']}")
            options = question["options"]
            user_answer = st.radio(
                f"Chọn đáp án cho câu {i+1}:",
                options,
                key=f"q2_{i}",
                index=st.session_state.user_answers[i] if st.session_state.user_answers[i] is not None else None
            )
            if user_answer:
                st.session_state.user_answers[i] = options.index(user_answer)

        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("📤 Nộp Bài", type="primary"):
                st.session_state.submitted = True

        if st.session_state.submitted:
            st.markdown("---")
            st.subheader("📊 Kết Quả Bài Thi")

            correct_count = 0
            for i, question in enumerate(quiz_data["questions"]):
                user_answer_index = st.session_state.user_answers[i]
                correct_answer = question["correct_answer"]

                if user_answer_index is not None:
                    user_answer_letter = question["options"][user_answer_index][0]  # Lấy chữ cái A/B/C/D
                    is_correct = (user_answer_letter == correct_answer)

                    if is_correct:
                        correct_count += 1

                    if is_correct:
                        st.success(f"✅ Câu {i+1}: ĐÚNG - Đáp án của bạn: {user_answer_letter}")
                    else:
                        st.error(f"❌ Câu {i+1}: SAI - Đáp án của bạn: {user_answer_letter}, Đáp án đúng: {correct_answer}")

            total_questions = len(quiz_data["questions"])
            score_percent = (correct_count / total_questions) * 100

            st.metric("Số câu đúng", f"{correct_count}/{total_questions}")
            st.metric("Tỷ lệ đúng", f"{score_percent:.1f}%")

            if score_percent >= 90:
                st.success("🎉 Xuất sắc! Bạn có kiến thức lịch sử rất tốt!")
            elif score_percent >= 70:
                st.info("👍 Khá tốt! Tiếp tục phát huy nhé!")
            elif score_percent >= 50:
                st.warning("💪 Cố gắng hơn nữa!")
            else:
                st.error("📚 Cần ôn tập lại kiến thức!")

# ====== FOOTER ======
st.markdown("---")
st.markdown("Ứng dụng được phát triển bởi [Le Thi Ngoc Duyen] - Sử dụng AI để tạo câu hỏi trắc nghiệm")
