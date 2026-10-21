import io
import time

import streamlit as st
from google import genai

# If a model stops working, change the names in this list (best first).
MODELS = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-flash-latest"]

st.set_page_config(page_title="Question paper analyzer", page_icon="🩺", layout="wide")
st.title("🩺 Question paper analyzer")
st.write(
    "Upload past question papers (PDF). You get the most repeated questions, "
    "new practice questions, and answers."
)

with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Gemini API key", type="password").strip()
    qtype = st.selectbox(
        "Type of new questions",
        [
            "Same style as the papers",
            "MCQ (single best answer)",
            "Short answer (SAQ)",
            "Structured essay (SEQ)",
            "Viva",
        ],
    )
    n_new = st.slider("Number of new questions", 5, 40, 15)
    detail = st.selectbox("Answer detail", ["Short exam points", "Detailed"])
    model_name = st.text_input("Model name (leave empty for automatic)").strip()

subject = st.text_input("Subject (optional)", placeholder="Example: Anatomy, upper limb")
files = st.file_uploader("Past question papers", type="pdf", accept_multiple_files=True)


def upload_pdf(client, f):
    doc = client.files.upload(
        file=io.BytesIO(f.getvalue()), config=dict(mime_type="application/pdf")
    )
    for _ in range(30):  # wait until Google finishes processing the file
        if getattr(doc.state, "name", str(doc.state)) != "PROCESSING":
            break
        time.sleep(2)
        doc = client.files.get(name=doc.name)
    return doc


def build_prompt():
    about = f" for {subject}" if subject else ""
    return f"""You are an experienced MBBS exam tutor.
The attached PDFs are past question papers{about}. Some pages may be scanned images.

Reply in three parts, using these headings.

## 1. Most repeated questions
Group questions that ask the same thing in different words. List the most repeated first.
For each one, say how many times it appeared and in which paper or year, if visible.
Count only what is really in the PDFs. If you are unsure, say so.

## 2. New practice questions
Write {n_new} new questions an examiner is likely to ask. Cover topics the papers point to
but do not repeat exactly. Question type: {qtype}. Number them.

## 3. Answers
Answer every question from parts 1 and 2. Answer detail: {detail}.
Use clear exam-style points. If you are not fully sure of a fact, add "(verify in textbook)".
"""


if st.button("Analyze papers", type="primary"):
    if not api_key:
        st.error("Paste your Gemini API key in the sidebar first.")
        st.stop()
    if not files:
        st.error("Upload at least one PDF first.")
        st.stop()

    text, errors = "", []
    with st.spinner("Reading the papers. This can take a minute or two."):
        try:
            client = genai.Client(api_key=api_key)
            contents = [upload_pdf(client, f) for f in files] + [build_prompt()]
            for model in [model_name] if model_name else MODELS:
                try:
                    reply = client.models.generate_content(model=model, contents=contents)
                    text = reply.text or ""
                    if text:
                        break
                    errors.append(f"{model}: empty reply")
                except Exception as e:
                    errors.append(f"{model}: {e}")
        except Exception as e:
            errors.append(f"Upload failed: {e}")

    if text:
        st.session_state["result"] = text
    else:
        st.error("No answer yet. Wait a minute and try again. If it keeps failing, send the details below to Claude.")
        st.code("\n\n".join(errors))

if "result" in st.session_state:
    st.markdown(st.session_state["result"])
    st.download_button("Download as text file", st.session_state["result"], file_name="questions.md")
