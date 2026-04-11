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

# --- ২. স্মার্ট টেক্সট এক্সট্রাকশন (প্যারাগ্রাফ আকারে) ---
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
                        
                        # ডাবল লাইনব্রেক দিয়ে প্যারাগ্রাফগুলো আলাদা করা
                        raw_paragraphs = full_text.split('\n\n')
                        for p in raw_paragraphs:
                            clean_p = p.strip()
                            if len(clean_p) > 20: # খুব ছোট লাইন বাদ দেওয়া
                                paragraphs.append(clean_p)
                except Exception:
                    continue
    return paragraphs

# --- ৩. ইন্টারফেস ---
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖")
st.title("🤖 পদক্ষেপ মিত্র (Official Assistant)")

with st.spinner("গাইডলাইন ডেটাবেস ইনডেক্স করা হচ্ছে..."):
    all_paragraphs = get_guideline_paragraphs()

if "messages" not in st.session_state:
    st.session_state.messages = []

model = genai.GenerativeModel('gemini-1.5-flash')

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- ৪. সার্চ ও চ্যাট লজিক ---
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন... (যেমন: অনিয়ম কী?)"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # ক) ইউজারের প্রশ্ন থেকে কি-ওয়ার্ড বের করা (যেমন: 'অনিয়ম', 'কী')
            search_words = set(re.findall(r'\w+', prompt))
            
            # খ) কোন প্যারাগ্রাফে এই শব্দগুলো সবচেয়ে বেশি আছে তা খোঁজা
            scored_paragraphs = []
            for p in all_paragraphs:
                score = sum(1 for word in search_words if word in p)
                scored_paragraphs.append((score, p))
            
            # গ) সবচেয়ে বেশি মিল থাকা সেরা ৫টি প্যারাগ্রাফ বেছে নেওয়া
            scored_paragraphs.sort(key=lambda x: x[0], reverse=True)
            top_context = "\n\n".join([p for score, p in scored_paragraphs[:5]])

            # ঘ) শুধু এই ছোট কনটেক্সটটুকু জেমিনিকে দেওয়া (টোকেন বাঁচবে)
            final_prompt = (
                f"তুমি পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের একজন সহকারী। "
                f"নিচের তথ্যের উপর ভিত্তি করে প্রশ্নের সঠিক উত্তর দাও। "
                f"তথ্যে উত্তর না থাকলে বানিয়ে কিছু বলবে না।\n\n"
                f"তথ্য:\n{top_context}\n\n"
                f"প্রশ্ন: {prompt}"
            )
            
            response = model.generate_content(final_prompt)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
        except Exception as e:
            st.error("দুঃখিত, কোনো একটি সমস্যা হয়েছে। দয়া করে আবার চেষ্টা করুন।")
            print(f"Error Details: {e}")
