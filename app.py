import streamlit as st
import google.generativeai as genai
from groq import Groq
from openai import OpenAI
import os
import time
import PyPDF2

st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")

# টাইটেল ও স্টাইল
st.markdown("""
    <style>
    .main-title { font-size: 2.8rem; font-weight: 700; text-align: center; color: white; margin-bottom: 0px; }
    .instruction { text-align: center; color: #B0B0B0; font-size: 1.1rem; margin-bottom: 30px; }
    </style>
    <div class="main-title">🤖 পদক্ষেপ মিত্র (Hybrid v2)</div>
    <div class="instruction">তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করে নিন</div>
    """, unsafe_allow_html=True)

# কী ম্যানেজমেন্ট
def get_keys(prefix):
    return [st.secrets.get(f"{prefix}_{i}") for i in range(1, 6) if st.secrets.get(f"{prefix}_{i}")]

GEMINI_KEYS = get_keys("GEMINI_API_KEY")
GROQ_KEYS = get_keys("GROQ_API_KEY")
OPENROUTER_KEYS = get_keys("OPENROUTER_API_KEY")

if "gemini_idx" not in st.session_state: st.session_state.gemini_idx = 0
if "groq_idx" not in st.session_state: st.session_state.groq_idx = 0
if "or_idx" not in st.session_state: st.session_state.or_idx = 0

# পিডিএফ রিডার (স্মার্টলি এরর হ্যান্ডেল করবে)
def get_pdf_text_context(folder_path):
    all_text = ""
    if os.path.exists(folder_path):
        for f in os.listdir(folder_path):
            if f.lower().endswith(".pdf"):
                try:
                    with open(os.path.join(folder_path, f), "rb") as pdf_file:
                        reader = PyPDF2.PdfReader(pdf_file)
                        for page in reader.pages:
                            text = page.extract_text()
                            if text: all_text += text + "\n"
                except Exception as e:
                    st.error(f"পিডিএফ পড়তে সমস্যা: {f}")
    return all_text[:15000] # টোকেন লিমিট বাঁচাতে প্রথম ১৫০০০ ক্যারেক্টার নেওয়া হচ্ছে

# জেমিনি আপলোড লজিক
def upload_to_gemini(path, api_key):
    try:
        genai.configure(api_key=api_key)
        file = genai.upload_file(path)
        while file.state.name == "PROCESSING":
            time.sleep(1)
            file = genai.get_file(file.name)
        return file
    except:
        return None

# সাইডবার
st.sidebar.title("📚 টপিক সিলেকশন")
knowledge_dir = "knowledge"
subfolders = [f for f in os.listdir(knowledge_dir) if os.path.isdir(os.path.join(knowledge_dir, f))] if os.path.exists(knowledge_dir) else []
selected_folder = st.sidebar.selectbox("একটি টপিক নির্বাচন করুন:", options=["সিলেক্ট করুন"] + subfolders)

if "messages" not in st.session_state: st.session_state.messages = []
for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    if selected_folder == "সিলেক্ট করুন":
        st.warning("⚠️ আগে টপিক সিলেক্ট করুন।")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("গাইডলাইন বিশ্লেষণ করছি..."):
                response_text = ""
                success = False
                folder_path = os.path.join(knowledge_dir, selected_folder)
                diag_logs = []

                # ১. জেমিনি ট্রাই
                if GEMINI_KEYS:
                    for _ in range(len(GEMINI_KEYS)):
                        key = GEMINI_KEYS[st.session_state.gemini_idx % len(GEMINI_KEYS)]
                        try:
                            files = [upload_to_gemini(os.path.join(folder_path, f), key) for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
                            model = genai.GenerativeModel("gemini-1.5-flash")
                            resp = model.generate_content([f for f in files if f] + [prompt])
                            response_text = resp.text
                            success = True
                            break
                        except Exception as e:
                            diag_logs.append(f"Gemini Key {st.session_state.gemini_idx+1} failed: {str(e)}")
                            st.session_state.gemini_idx += 1

                # ২. গ্রক ট্রাই
                if not success and GROQ_KEYS:
                    pdf_context = get_pdf_text_context(folder_path)
                    for _ in range(len(GROQ_KEYS)):
                        key = GROQ_KEYS[st.session_state.groq_idx % len(GROQ_KEYS)]
                        try:
                            client = Groq(api_key=key)
                            completion = client.chat.completions.create(
                                model="llama3-8b-8192",
                                messages=[{"role": "system", "content": f"Use context: {pdf_context}"}, {"role": "user", "content": prompt}]
                            )
                            response_text = completion.choices[0].message.content + "\n\n*(Answered by Groq)*"
                            success = True
                            break
                        except Exception as e:
                            diag_logs.append(f"Groq Key {st.session_state.groq_idx+1} failed: {str(e)}")
                            st.session_state.groq_idx += 1

                if success:
                    st.markdown(response_text)
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                else:
                    st.error("❌ সব সার্ভিস ওভারলোডেড।")
                    with st.expander("🛠️ এরর লোগ দেখুন"):
                        for log in diag_logs: st.write(log)
