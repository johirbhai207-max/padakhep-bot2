import streamlit as st
import google.generativeai as genai
from groq import Groq
from openai import OpenAI
import os
import time
import PyPDF2

# ১. পেজ কনফিগারেশন
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖", layout="wide")

# ২. টাইটেল ও স্টাইল (আপনার কাজ করা সফল ভার্সন অনুযায়ী)
st.markdown("""
    <style>
    .main-title { font-size: 2.8rem; font-weight: 700; text-align: center; color: white; margin-bottom: 0px; }
    .instruction { text-align: center; color: #B0B0B0; font-size: 1.1rem; margin-bottom: 30px; }
    </style>
    <div class="main-title">🤖 পদক্ষেপ মিত্র (Official Assistant)</div>
    <div class="instruction">তথ্য খোঁজার আগে বাম পাশের সেকশন থেকে টপিক সিলেক্ট করে নিন</div>
    """, unsafe_allow_html=True)

# ৩. এপিআই কী সেটিংস
GEMINI_KEYS = [st.secrets.get(f"GEMINI_API_KEY_{i}") for i in range(1, 6)]
GROQ_KEYS = [st.secrets.get(f"GROQ_API_KEY_{i}") for i in range(1, 6)]
OPENROUTER_KEYS = [st.secrets.get(f"OPENROUTER_API_KEY_{i}") for i in range(1, 6)]

# কী রোটেশন ট্র্যাকিং
if "gemini_idx" not in st.session_state: st.session_state.gemini_idx = 0
if "groq_idx" not in st.session_state: st.session_state.groq_idx = 0
if "or_idx" not in st.session_state: st.session_state.or_idx = 0

# পিডিএফ থেকে টেক্সট পড়ার লজিক (Smart Context এর জন্য)
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
                    print(f"Error reading {f}: {e}")
    return all_text

# ৪. ফাইল আপলোড লজিক (শুধুমাত্র জেমিনির জন্য)
def upload_to_gemini(path, api_key):
    try:
        genai.configure(api_key=api_key, transport='rest')
        file = genai.upload_file(path)
        while file.state.name == "PROCESSING":
            time.sleep(1)
            file = genai.get_file(file.name)
        return file
    except:
        return None

# ৫. সাইডবার - Single Selection
st.sidebar.title("📚 টপিক সিলেকশন")
knowledge_dir = "knowledge"
subfolders = [f for f in os.listdir(knowledge_dir) if os.path.isdir(os.path.join(knowledge_dir, f))] if os.path.exists(knowledge_dir) else []
selected_folder = st.sidebar.selectbox("একটি টপিক নির্বাচন করুন:", options=["সিলেক্ট করুন"] + subfolders)

# চ্যাট হিস্ট্রি
if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ৬. মূল হাইব্রিড চ্যাট লজিক
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    if selected_folder == "সিলেক্ট করুন":
        st.warning("⚠️ আগে বাম পাশের সেকশন থেকে একটি টপিক সিলেক্ট করুন।")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("গাইডলাইন বিশ্লেষণ করছি..."):
                response_text = ""
                success = False
                folder_path = os.path.join(knowledge_dir, selected_folder)

                # --- ধাপ ১: জেমিনি দিয়ে চেষ্টা (৫টি কী রোটেশন) ---
                valid_gemini_keys = [k for k in GEMINI_KEYS if k]
                for _ in range(len(valid_gemini_keys)):
                    key = valid_gemini_keys[st.session_state.gemini_idx % len(valid_gemini_keys)]
                    try:
                        current_files = []
                        for f in os.listdir(folder_path):
                            if f.lower().endswith(".pdf"):
                                res = upload_to_gemini(os.path.join(folder_path, f), key)
                                if res: current_files.append(res)
                        
                        model = genai.GenerativeModel("gemini-1.5-flash")
                        resp = model.generate_content(current_files + [prompt])
                        if resp.text:
                            response_text = resp.text
                            success = True
                            break
                    except:
                        st.session_state.gemini_idx += 1

                # --- ধাপ ২: জেমিনি ফেইল করলে Groq দিয়ে চেষ্টা (৫টি কী রোটেশন) ---
                if not success:
                    pdf_context = get_pdf_text_context(folder_path)
                    valid_groq_keys = [k for k in GROQ_KEYS if k]
                    for _ in range(len(valid_groq_keys)):
                        g_key = valid_groq_keys[st.session_state.groq_idx % len(valid_groq_keys)]
                        try:
                            client = Groq(api_key=g_key)
                            completion = client.chat.completions.create(
                                model="llama3-70b-8192", # শক্তিশালী মডেল
                                messages=[
                                    {"role": "system", "content": f"You are a helpful assistant. Use this context to answer: {pdf_context}"},
                                    {"role": "user", "content": prompt}
                                ]
                            )
                            response_text = completion.choices[0].message.content + "\n\n*(Answered by Groq Backup)*"
                            success = True
                            break
                        except:
                            st.session_state.groq_idx += 1

                # --- ধাপ ৩: সবশেষে OpenRouter দিয়ে চেষ্টা (৫টি কী রোটেশন) ---
                if not success:
                    valid_or_keys = [k for k in OPENROUTER_KEYS if k]
                    for _ in range(len(valid_or_keys)):
                        or_key = valid_or_keys[st.session_state.or_idx % len(valid_or_keys)]
                        try:
                            client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=or_key)
                            completion = client.chat.completions.create(
                                model="meta-llama/llama-3-8b-instruct:free",
                                messages=[
                                    {"role": "system", "content": f"Context: {pdf_context}"},
                                    {"role": "user", "content": prompt}
                                ]
                            )
                            response_text = completion.choices[0].message.content + "\n\n*(Answered by OpenRouter Backup)*"
                            success = True
                            break
                        except:
                            st.session_state.or_idx += 1

                if success:
                    st.markdown(response_text)
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                else:
                    st.error("❌ সবকটি এপিআই সার্ভিস বর্তমানে ওভারলোডেড। দয়া করে ১০ মিনিট পর চেষ্টা করুন।")
