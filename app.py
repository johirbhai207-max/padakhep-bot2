import streamlit as st
import google.generativeai as genai
import os
import PyPDF2
import re

# --- ১. এপিআই সেটিংস ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Secrets-এ 'GEMINI_API_KEY' পাওয়া যায়নি।")
    st.stop()

# --- ২. পিডিএফ ডেটা লোড ---
@st.cache_data(show_spinner=False)
def get_guideline_paragraphs():
    paragraphs = []
    knowledge_dir = "knowledge"
    if os.path.exists(knowledge_dir):
        for file in os.listdir(knowledge_dir):
            if file.lower().endswith(".pdf"):
                try:
                    path = os.path.join(knowledge_dir, file)
                    with open(path, "rb") as f:
                        pdf_reader = PyPDF2.PdfReader(f)
                        full_text = ""
                        for page in pdf_reader.pages:
                            text = page.extract_text()
                            if text:
                                full_text += text + "\n"
                        raw_paragraphs = full_text.split('\n\n')
                        for p in raw_paragraphs:
                            clean_p = p.strip()
                            if len(clean_p) > 25:
                                paragraphs.append(clean_p)
                except Exception:
                    continue
    return paragraphs

# --- ৩. ইন্টারফেস ---
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖")

with st.sidebar:
    st.title("কন্ট্রোল প্যানেল")
    if st.button("মেমোরি পরিষ্কার করুন"):
        st.session_state.messages = []
        st.rerun()

st.title("🤖 পদক্ষেপ মিত্র (Official Assistant)")
st.caption("পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের নীতিমালা বিষয়ক এআই সহকারী")

with st.spinner("গাইডলাইন ডাটাবেস চেক করা হচ্ছে..."):
    all_paragraphs = get_guideline_paragraphs()

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- ৪. মাল্টি-মডেল লোডার (এরর কমানোর জন্য) ---
def get_ai_response(final_prompt):
    # ট্রাই ১: লেটেস্ট ফ্ল্যাশ মডেল
    # ট্রাই ২: স্ট্যান্ডার্ড ফ্ল্যাশ মডেল
    # ট্রাই ৩: প্রো মডেল (সবচেয়ে শক্তিশালী)
    model_names = [
        'models/gemini-1.5-flash-latest', 
        'gemini-1.5-flash', 
        'models/gemini-1.5-pro-latest'
    ]
    
    last_error = ""
    for name in model_names:
        try:
            model = genai.GenerativeModel(name)
            response = model.generate_content(
                final_prompt,
                safety_settings={
                    'HATE': 'BLOCK_NONE', 'HARASSMENT': 'BLOCK_NONE',
                    'SEXUAL' : 'BLOCK_NONE', 'DANGEROUS' : 'BLOCK_NONE'
                }
            )
            return response.text
        except Exception as e:
            last_error = str(e)
            continue # পরের মডেলে চলে যাবে
    
    return f"দুঃখিত, কোনো মডেলই কানেক্ট হচ্ছে না। এরর: {last_error}"

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- ৫. চ্যাট লজিক ---
if prompt := st.chat_input("গাইডলাইন সম্পর্কে জিজ্ঞাসা করুন..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # কি-ওয়ার্ড সার্চ
        search_words = set(re.findall(r'\w+', prompt.lower()))
        scored_paragraphs = []
        for p in all_paragraphs:
            score = sum(1 for word in search_words if word in p.lower())
            if score > 0:
                scored_paragraphs.append((score, p))
        
        scored_paragraphs.sort(key=lambda x: x[0], reverse=True)
        top_context = "\n\n".join([p for score, p in scored_paragraphs[:5]])

        final_prompt = (
            f"তুমি পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের একজন দাপ্তরিক সহকারী। "
            f"নিচের তথ্যের ভিত্তিতে প্রশ্নের উত্তর দাও।\n\n"
            f"তথ্য:\n{top_context}\n\n"
            f"প্রশ্ন: {prompt}"
        )
        
        with st.spinner("উত্তর তৈরি হচ্ছে..."):
            full_response = get_ai_response(final_prompt)
            st.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
