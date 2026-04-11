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

# --- ২. ডাটাবেস প্রসেসিং ---
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
                        raw_parts = full_text.split('\n\n')
                        for p in raw_parts:
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

# --- ৪. পাওয়ারফুল রেসপন্স ফাংশন ---
def generate_ai_response(prompt_text):
    # এই পদ্ধতিটি সরাসরি মূল মডেলকে টার্গেট করবে
    try:
        # gemini-1.5-flash সবচেয়ে বেশি স্থিতিশীল
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(
            prompt_text,
            safety_settings={
                'HATE': 'BLOCK_NONE', 'HARASSMENT': 'BLOCK_NONE',
                'SEXUAL' : 'BLOCK_NONE', 'DANGEROUS' : 'BLOCK_NONE'
            }
        )
        return response.text
    except Exception as e:
        # যদি প্রথমটি কাজ না করে, বিকল্প ট্রাই করবে
        try:
            alt_model = genai.GenerativeModel('gemini-pro')
            response = alt_model.generate_content(prompt_text)
            return response.text
        except:
            return f"Error Detail: {str(e)}"

# হিস্ট্রি ডিসপ্লে
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- ৫. চ্যাট ইনপুট ---
user_input = st.chat_input("গাইডলাইন সম্পর্কে জিজ্ঞাসা করুন...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        # সার্চ লজিক
        search_words = set(re.findall(r'\w+', user_input.lower()))
        scored_p = []
        for p in all_paragraphs:
            score = sum(1 for word in search_words if word in p.lower())
            if score > 0:
                scored_p.append((score, p))
        
        scored_p.sort(key=lambda x: x[0], reverse=True)
        context = "\n\n".join([item[1] for item in scored_p[:5]])

        final_prompt = (
            f"তুমি পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের একজন বিশেষজ্ঞ সহকারী। "
            f"নিচের তথ্যের ভিত্তিতে উত্তর দাও।\n\n"
            f"তথ্যসমূহ: {context}\n\n"
            f"প্রশ্ন: {user_input}"
        )
        
        with st.spinner("পদক্ষেপ মিত্র উত্তর খুঁজছে..."):
            ai_reply = generate_ai_response(final_prompt)
            st.markdown(ai_reply)
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
