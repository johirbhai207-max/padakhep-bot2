import streamlit as st
import google.generativeai as genai
import os
import PyPDF2

# --- ১. এপিআই সেটিংস ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Secrets-এ 'GEMINI_API_KEY' পাওয়া যায়নি।")
    st.stop()

# --- ২. ফাইল রিডিং (Diagnostic Mode) ---
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
                            if len(clean_p) > 20:
                                paragraphs.append(clean_p)
                except Exception as e:
                    st.warning(f"⚠️ {file} পড়তে সমস্যা হয়েছে: {e}")
                    continue
    return paragraphs

# --- ৩. ইন্টারফেস ---
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖")
st.title("🤖 পদক্ষেপ মিত্র (Diagnostic Mode)")

with st.spinner("গাইডলাইন ডেটাবেস ইনডেক্স করা হচ্ছে..."):
    all_paragraphs = get_guideline_paragraphs()

# 🚨 চেকিং: পিডিএফ থেকে আদৌ কোনো লেখা বের হয়েছে কি না!
if not all_paragraphs:
    st.error("🚨 'knowledge' ফোল্ডার থেকে কোনো টেক্সট পাওয়া যায়নি! আপনার ফোল্ডারের নাম বা পিডিএফ ফাইল ঠিক আছে তো?")

if "messages" not in st.session_state:
    st.session_state.messages = []

try:
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"🚨 মডেল লোড হতে সমস্যা: {e}")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- ৪. চ্যাট লজিক ---
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # বাংলা শব্দের জন্য স্প্লিট লজিক আপডেট করা হলো
            search_words = set(prompt.split())
            
            scored_paragraphs = []
            for p in all_paragraphs:
                score = sum(1 for word in search_words if word in p)
                scored_paragraphs.append((score, p))
            
            scored_paragraphs.sort(key=lambda x: x[0], reverse=True)
            top_context = "\n\n".join([p for score, p in scored_paragraphs[:5]])

            final_prompt = (
                f"তুমি পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের একজন সহকারী। "
                f"নিচের তথ্যের উপর ভিত্তি করে প্রশ্নের সঠিক উত্তর দাও। "
                f"তথ্য:\n{top_context}\n\n"
                f"প্রশ্ন: {prompt}"
            )
            
            response = model.generate_content(final_prompt)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
        except Exception as e:
            # 🚨 আসল জাদুকরী লাইন: এটি পেছনের আসল এররটি স্ক্রিনে দেখাবে 🚨
            st.error(f"❌ আসল এরর: {str(e)}")
