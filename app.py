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

# --- ২. মেমোরি অপটিমাইজড পিডিএফ রিডার ---
@st.cache_data(show_spinner=False)
def get_guideline_text():
    combined_text = ""
    knowledge_dir = "knowledge"
    if os.path.exists(knowledge_dir):
        for file in os.listdir(knowledge_dir):
            if file.lower().endswith(".pdf"):
                try:
                    path = os.path.join(knowledge_dir, file)
                    with open(path, "rb") as f:
                        pdf_reader = PyPDF2.PdfReader(f)
                        # কোটা বাঁচাতে প্রথম ৫০ পেজ বা নির্দিষ্ট পরিমাণ টেক্সট পড়া
                        for page in pdf_reader.pages[:50]: 
                            text = page.extract_text()
                            if text:
                                combined_text += text + "\n"
                except Exception:
                    continue
    # ফ্রি টায়ারের কোটা বাঁচাতে সর্বোচ্চ ৫০,০০০ ক্যারেক্টার লিমিট
    return combined_text[:50000]

# --- ৩. ইন্টারফেস ---
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖")
st.title("🤖 পদক্ষেপ মিত্র (Official Assistant)")

# নলেজ বেস লোড
with st.spinner("গাইডলাইন ডেটাবেস প্রস্তুত করা হচ্ছে..."):
    context_text = get_guideline_text()

if "messages" not in st.session_state:
    st.session_state.messages = []

# মডেল সেটআপ
model = genai.GenerativeModel('gemini-1.5-flash')

# চ্যাট হিস্ট্রি
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- ৪. চ্যাট লজিক ---
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন... (যেমন: অনিয়ম কী?)"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # প্রম্পটের সাইজ ছোট রাখা হয়েছে
            final_prompt = (
                f"তুমি পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের সহকারী 'পদক্ষেপ মিত্র'। "
                f"নিচের তথ্যের ভিত্তিতে উত্তর দাও:\n\n{context_text}\n\n"
                f"প্রশ্ন: {prompt}"
            )
            
            response = model.generate_content(final_prompt)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
        except Exception as e:
            st.error("সার্ভার ওভারলোডেড। দয়া করে ১ মিনিট অপেক্ষা করে আবার প্রশ্ন করুন।")
            # ডেভেলপার হিসেবে আপনার বোঝার জন্য আসল এররটি প্রিন্ট করা হলো (স্ক্রিনে দেখাবে না)
            print(f"Error Details: {e}")
