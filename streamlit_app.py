import streamlit as st
from openai import OpenAI
import os
import PyPDF2
import docx
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from io import BytesIO
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# ======================
# ⚙️ CONFIG
# ======================
st.set_page_config(page_title="AI Quiz Generator", layout="wide")

# Lấy API key từ secrets (Streamlit Cloud)
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# SMTP config (bạn đặt trong secrets)
SMTP_EMAIL = st.secrets.get("SMTP_EMAIL", "")
SMTP_PASSWORD = st.secrets.get("SMTP_PASSWORD", "")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# ======================
# 📘 HÀM HỖ TRỢ
# ======================

def extract_text(file):
    """Đọc nội dung từ file PDF hoặc DOCX"""
    text = ""
    if file.name.endswith(".pdf"):
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() or ""
    elif file.name.endswith(".docx"):
        doc = docx.Document(file)
        text = "\n".join([p.text for p in doc.paragraphs])
    return text.strip()

def generate_mcqs_from_openai(text, num_questions=10):
    prompt = f"""
    Hãy tạo {num_questions} câu hỏi trắc nghiệm từ nội dung sau.
    Mỗi câu có 4 đáp án (A, B, C, D) và chỉ rõ đáp án đúng.
    Trình bày rõ ràng theo định dạng:

    Câu X: ...
    A. ...
    B. ...
    C. ...
    D. ...
    Đáp án đúng: ...

    Nội dung: {text[:3000]}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Bạn là trợ lý tạo câu hỏi trắc nghiệm."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )

    return response.choices[0].message.content

def export_docx(mcq_text):
    """Xuất ra file Word"""
    doc = Document()
    doc.add_heading("Bộ câu hỏi trắc nghiệm", level=1)
    for line in mcq_text.split("\n"):
        doc.add_paragraph(line)
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

def export_pdf(mcq_text):
    """Xuất ra file PDF"""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    y = height - 50
    for line in mcq_text.split("\n"):
        c.drawString(50, y, line)
        y -= 15
        if y < 50:
            c.showPage()
            y = height - 50
    c.save()
    buf.seek(0)
    return buf

def send_email(recipient, subject, body, attachment=None, filename="quiz.docx"):
    """Gửi mail kèm file"""
    msg = MIMEMultipart()
    msg["From"] = SMTP_EMAIL
    msg["To"] = recipient
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))
    if attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.getvalue())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={filename}")
        msg.attach(part)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)

# ======================
# 🎯 GIAO DIỆN STREAMLIT
# ======================

st.title("📘 ỨNG DỤNG TẠO CÂU HỎI TRẮC NGHIỆM TỰ ĐỘNG")
mode = st.radio("Chọn chế độ:", ["Tạo và xuất file câu hỏi", "Làm bài trực tuyến"])

if mode == "Tạo và xuất file câu hỏi":
    uploaded_file = st.file_uploader("📤 Tải lên file PDF hoặc DOCX", type=["pdf", "docx"])
    link_input = st.text_input("Hoặc dán link tài liệu (nếu có):")
    email_input = st.text_input("📧 Nhập email để gửi file (tùy chọn):")

    if st.button("🚀 Tạo câu hỏi"):
        if uploaded_file:
            text = extract_text(uploaded_file)
        elif link_input:
            # Bạn có thể bổ sung xử lý tải và trích xuất text từ link ở đây
            text = link_input
        else:
            st.warning("Vui lòng tải lên file hoặc nhập link.")
            st.stop()

        with st.spinner("Đang tạo câu hỏi, vui lòng chờ..."):
            mcqs = generate_mcqs_from_openai(text)

        st.text_area("📚 Kết quả câu hỏi:", mcqs, height=400)

        # Xuất file Word & PDF
        docx_file = export_docx(mcqs)
        pdf_file = export_pdf(mcqs)

        st.download_button("📄 Tải file Word", docx_file, file_name="quiz.docx")
        st.download_button("📘 Tải file PDF", pdf_file, file_name="quiz.pdf")

        if email_input and SMTP_EMAIL and SMTP_PASSWORD:
            try:
                send_email(email_input, "Bộ câu hỏi trắc nghiệm tự động", "Đính kèm là bộ câu hỏi bạn yêu cầu.", docx_file)
                st.success(f"✅ Đã gửi file tới {email_input}")
            except Exception as e:
                st.error(f"❌ Gửi mail thất bại: {e}")

elif mode == "Làm bài trực tuyến":
    uploaded_file = st.file_uploader("📤 Tải lên file PDF hoặc DOCX", type=["pdf", "docx"])
    if st.button("🚀 Tạo bài trắc nghiệm"):
        if not uploaded_file:
            st.warning("Vui lòng tải lên tài liệu.")
            st.stop()
        text = extract_text(uploaded_file)
        with st.spinner("Đang tạo bài trắc nghiệm, vui lòng chờ..."):
            mcqs = generate_mcqs_from_openai(text)
        questions = [q for q in mcqs.split("\n\n") if "Câu" in q]

        score = 0
        for i, q in enumerate(questions):
            st.write(q.split("Đáp án đúng")[0])
            answer = st.radio(f"Chọn đáp án câu {i+1}:", ["A", "B", "C", "D"], key=i)
            correct = q.split("Đáp án đúng:")[-1].strip()[0]
            if answer == correct:
                score += 1

        if st.button("📊 Nộp bài"):
            st.success(f"🎯 Bạn đạt {score}/{len(questions)} điểm ({score/len(questions)*100:.1f}%).")
