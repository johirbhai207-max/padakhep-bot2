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

# --- ২. পিডিএফ থেকে সরাসরি টেক্সট সংগ্রহের ফাংশন ---
def load_context_from_pdfs():
    combined_text = ""
    knowledge_dir = "knowledge"
    if os.path.exists(knowledge_dir):
        for file in os.listdir(knowledge_dir):
            if file.lower().endswith(".pdf"):
                try:
                    path = os.path.join(knowledge_dir, file)
                    with open(path, "rb") as f:
                        pdf_reader = PyPDF2.PdfReader(f)
                        for page in pdf_reader.pages:
                            text = page.extract_text()
                            if text:
                                combined_text += text + "\n"
                except Exception:
                    continue
    return combined_text

# --- ৩. ইন্টারফেস এবং সেশন ম্যানেজমেন্ট ---
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖")
st.title("🤖 পদক্ষেপ মিত্র (Official Assistant)")

# নলেজ বেস একবারই লোড হবে
if "pdf_context" not in st.session_state:
    with st.spinner("গাইডলাইনগুলো প্রসেস করা হচ্ছে..."):
        # জেমিনির ফ্রি টায়ারের জন্য আমরা ১.৫ লাখ ক্যারেক্টার পর্যন্ত ডাটা পাঠাবো
        full_text = load_context_from_pdfs()
        st.session_state.pdf_context = full_text[:150000] 

if "messages" not in st.session_state:
    st.session_state.messages = []

# মডেল ইনিশিয়ালাইজেশন
model = genai.GenerativeModel('gemini-1.5-flash')

# চ্যাট হিস্ট্রি প্রদর্শন
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- ৪. প্রশ্ন-উত্তর লজিক (Error-Free) ---
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # টেক্সট কনটেক্সট সরাসরি প্রম্পটের সাথে পাঠিয়ে দেওয়া
            final_prompt = (
                f"তুমি পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের একজন বিশেষজ্ঞ সহকারী। "
                f"নিচের তথ্যভাণ্ডার ব্যবহার করে ব্যবহারকারীর প্রশ্নের উত্তর দাও। "
                f"যদি উত্তর খুঁজে না পাও, তবে বিনয়ের সাথে বলো যে উত্তরটি জানা নেই।\n\n"
                f"তথ্যভাণ্ডার:\n{st.session_state.pdf_context}\n\n"
                f"প্রশ্ন: {prompt}"
            )
            
            response = model.generate_content(final_prompt)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
        except Exception as e:
            st.error("দুঃখিত, গুগল এপিআই কোটা শেষ হয়ে গেছে বা সংযোগ বিচ্ছিন্ন হয়েছে।")
