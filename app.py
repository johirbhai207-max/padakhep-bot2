import streamlit as st
import google.generativeai as genai
from groq import Groq
from openai import OpenAI
import os
import time
import PyPDF2

# ১. পেজ কনফিগারেশন
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")

# ২. টাইটেল ও স্টাইল (আপনার সফল ভার্সন অনুযায়ী হুবহু)
st.markdown("""
    <style>
    .main-title { font-size: 2.8rem; font-weight: 700; text-align: center; color: white; margin-bottom: 0px; }
    .instruction { text-align: center; color: #B0B0B0; font-size: 1.1rem; margin-bottom: 30px; }
    </style>
    <div class="main-title">🤖 পদক্ষেপ মিত্র (Official Assistant)</div>
    <div class="instruction">তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করে নিন</div>
    """, unsafe_allow_html=True)

# ৩. এপিআই কী সেটিংস
API_KEYS = [st.secrets.get(f"GEMINI_API_KEY_{i}") for i in range(1, 6) if st.secrets.get(f"GEMINI_API_KEY_{i}")]
GROQ_KEYS = [st.secrets.get(f"GROQ_API_KEY_{i}") for i in range(1, 6) if st.secrets.get(f"GROQ_API_KEY_{i}")]
OPENROUTER_KEYS = [st.secrets.get(f"OPENROUTER_API_KEY_{i}") for i in range(1, 6) if st.secrets.get(f"OPENROUTER_API_KEY_{i}")]

if "key_index" not in st.session_state: st.session_state.key_index = 0
if "groq_idx" not in st.session_state: st.session_state.groq_idx = 0

# আপনার সেই সফল জেমিনি কনফিগারেশন ফাংশন
def configure_gemini():
    if API_KEYS:
        key = API_KEYS[st.session_state.key_index % len(API_KEYS)]
        # ট্রান্সপোর্ট সরিয়ে দেওয়া হয়েছে যেন ভার্সন এরর না আসে
        genai.configure(api_key=key)
        return key
    return None

# পিডিএফ থেকে টেক্সট বের করার ফাংশন (ব্যাকআপের জন্য)
def get_pdf_text(folder_path):
    text = ""
    for f in os.listdir(folder_path):
        if f.lower().endswith(".pdf"):
            with open(os.path.join(folder_path, f), "rb") as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
    return text[:20000] # লিমিট বজায় রাখতে

# আপনার সফল ফাইল আপলোড ফাংশন
def upload_to_gemini(path):
    try:
        file = genai.upload_file(path)
        while file.state.name == "PROCESSING":
            time.sleep(1)
            file = genai.get_file(file.name)
        return file
    except:
        return None

# ৪. সাইডবার
st.sidebar.title("📚 টপিক সিলেকশন")
knowledge_dir = "knowledge"
subfolders = [f for f in os.listdir(knowledge_dir) if os.path.isdir(os.path.join(knowledge_dir, f))] if os.path.exists(knowledge_dir) else []
selected_folder = st.sidebar.selectbox("একটি টপিক নির্বাচন করুন:", options=["সিলেক্ট করুন"] + subfolders)

if "messages" not in st.session_state: st.session_state.messages = []
for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

# ৫. মূল চ্যাট লজিক (কাঠামো আগের মতো রাখা হয়েছে)
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    if selected_folder == "সিলেক্ট করুন":
        st.warning("⚠️ আগে বাম পাশের সেকশন থেকে একটি টপিক সিলেক্ট করুন।")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("গাইডলাইন বিশ্লেষণ করছি..."):
                success = False
                attempts = 0
                folder_path = os.path.join(knowledge_dir, selected_folder)

                # --- প্রথম ধাপ: জেমিনি (আপনার আগের সেই সফল লজিক) ---
                while not success and attempts < len(API_KEYS):
                    try:
                        configure_gemini()
                        current_files = []
                        for f in os.listdir(folder_path):
                            if f.lower().endswith(".pdf"):
                                res = upload_to_gemini(os.path.join(folder_path, f))
                                if res: current_files.append(res)
                        
                        # মডেলের নাম আপডেট করা হয়েছে
                        model = genai.GenerativeModel(model_name="gemini-1.5-flash")
                        response = model.generate_content(current_files + [prompt])
                        
                        if response.text:
                            st.markdown(response.text)
                            st.session_state.messages.append({"role": "assistant", "content": response.text})
                            success = True
                    except Exception as e:
                        st.session_state.key_index += 1
                        attempts += 1

                # --- দ্বিতীয় ধাপ: জেমিনি ফেইল করলে Groq (মডেল এরর সমাধানসহ) ---
                if not success and GROQ_KEYS:
                    pdf_context = get_pdf_text(folder_path)
                    for _ in range(len(GROQ_KEYS)):
                        try:
                            g_key = GROQ_KEYS[st.session_state.groq_idx % len(GROQ_KEYS)]
                            client = Groq(api_key=g_key)
                            # বন্ধ হওয়া llama3-8b-8192 এর বদলে নতুন llama-3.1-8b-instant ব্যবহার করা হয়েছে
                            completion = client.chat.completions.create(
                                model="llama-3.1-8b-instant", 
                                messages=[{"role": "system", "content": f"Context: {pdf_context}"}, {"role": "user", "content": prompt}]
                            )
                            ans = completion.choices[0].message.content + "\n\n*(Answered by Groq Backup)*"
                            st.markdown(ans)
                            st.session_state.messages.append({"role": "assistant", "content": ans})
                            success = True
                            break
                        except:
                            st.session_state.groq_idx += 1

                if not success:
                    st.error("❌ সব সার্ভিস এই মুহূর্তে ওভারলোডেড। দয়া করে ১০ মিনিট পর চেষ্টা করুন।")
