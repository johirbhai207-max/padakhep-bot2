import streamlit as st
import google.generativeai as genai
import os
import PyPDF2

# ১. এপিআই এবং মডেল সেটিংস
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Secrets-এ API Key পাওয়া যায়নি!")
    st.stop()

# ২. পিডিএফ থেকে টেক্সট এক্সট্রাক্ট করার ফাংশন
def get_pdf_text():
    all_text = ""
    knowledge_dir = "knowledge"
    if os.path.exists(knowledge_dir):
        for filename in os.listdir(knowledge_dir):
            if filename.endswith(".pdf"):
                path = os.path.join(knowledge_dir, filename)
                try:
                    with open(path, "rb") as f:
                        reader = PyPDF2.PdfReader(f)
                        for page in reader.pages:
                            all_text += page.extract_text() + "\n"
                except Exception as e:
                    continue
    return all_text

# ৩. ইন্টারফেস এবং সেশন
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖")
st.title("🤖 পদক্ষেপ মিত্র (Official Assistant)")

if "messages" not in st.session_state:
    st.session_state.messages = []

# নলেজ বেস একবারই লোড হবে
if "context" not in st.session_state:
    with st.spinner("গাইডলাইনগুলো লোড হচ্ছে..."):
        raw_text = get_pdf_text()
        # টেক্সট খুব বড় হলে প্রথম ১ লাখ ক্যারেক্টার নেবে (ফ্রি টায়ারের জন্য নিরাপদ)
        st.session_state.context = raw_text[:100000] 

# মডেল সেটআপ
model = genai.GenerativeModel('gemini-1.5-flash')

# চ্যাট হিস্ট্রি প্রদর্শন
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ৪. ইউজার ইনপুট প্রসেসিং
if prompt := st.chat_input("গাইডলাইন সম্পর্কে প্রশ্ন করুন..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # সরাসরি কনটেক্সট সহ প্রম্পট পাঠানো
            full_prompt = f"নিচের গাইডলাইন থেকে উত্তর দাও:\n\n{st.session_state.context}\n\nপ্রশ্ন: {prompt}"
            response = model.generate_content(full_prompt)
            
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except Exception as e:
            st.error("দুঃখিত, গুগল এপিআই কোটা শেষ হয়ে গেছে বা সংযোগ বিচ্ছিন্ন হয়েছে।")
