import streamlit as st
import google.generativeai as genai
import os
import PyPDF2
import re

# --- ১. এপিআই কনফিগারেশন ---
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("Streamlit Secrets-এ 'GEMINI_API_KEY' সেট করা নেই।")
    st.stop()

# --- ২. পিডিএফ থেকে নলেজ বেস তৈরি (স্মার্ট সার্চ লজিক) ---
@st.cache_data(show_spinner=False)
def load_knowledge_base():
    paragraphs = []
    knowledge_dir = "knowledge"
    
    if not os.path.exists(knowledge_dir):
        return []

    for file in os.listdir(knowledge_dir):
        if file.lower().endswith(".pdf"):
            try:
                path = os.path.join(knowledge_dir, file)
                with open(path, "rb") as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    text_content = ""
                    for page in pdf_reader.pages:
                        extracted = page.extract_text()
                        if extracted:
                            text_content += extracted + "\n"
                    
                    # প্যারাগ্রাফে ভাগ করা (খালি লাইন অনুযায়ী)
                    parts = text_content.split('\n\n')
                    for p in parts:
                        clean_p = p.strip()
                        if len(clean_p) > 30: # খুব ছোট টেক্সট বাদ
                            paragraphs.append(clean_p)
            except Exception as e:
                continue
    return paragraphs

# --- ৩. ইন্টারফেস ডিজাইন ---
st.set_page_config(page_title="পদক্ষেপ মিত্র", page_icon="🤖")

# সাইডবারে অ্যাপের অবস্থা দেখানো
with st.sidebar:
    st.image("https://www.padakhep.org/images/logo.png", width=200) # যদি লোগো থাকে
    st.title("কন্ট্রোল প্যানেল")
    if st.button("মেমোরি পরিষ্কার করুন"):
        st.session_state.messages = []
        st.rerun()

st.title("🤖 পদক্ষেপ মিত্র (Official Assistant)")
st.caption("পদক্ষেপ মানবিক উন্নয়ন কেন্দ্রের নীতিমালা বিষয়ক এআই সহকারী")

# নলেজ লোড করা
with st.spinner("গাইডলাইনগুলো যাচাই করা হচ্ছে..."):
    all_data = load_knowledge_base()

if not all_data:
    st.warning("⚠️ 'knowledge' ফোল্ডারে কোনো পিডিএফ পাওয়া যায়নি। সাধারণ চ্যাট মোড চালু আছে।")

# চ্যাট হিস্ট্রি বজায় রাখা
if "messages" not in st.session_state:
    st.session_state.messages = []

# মডেল ইনিশিয়ালাইজেশন (সঠিক পাথ সহ)
try:
    # 'models/' প্রিফিক্স ব্যবহার করা হয়েছে v1beta সাপোর্ট নিশ্চিত করতে
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except Exception:
    model = genai.GenerativeModel('gemini-1.5-flash')

# আগের মেসেজগুলো দেখানো
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- ৪. চ্যাট লজিক ---
if prompt := st.chat_input("গাইডলাইন সম্পর্কে জিজ্ঞাসা করুন..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # সিম্পল সার্চ লজিক: ইউজারের প্রশ্নের শব্দের সাথে মিল খোঁজা
            search_words = set(re.findall(r'\w+', prompt.lower()))
            scored_p = []
            
            for p in all_data:
                score = sum(1 for word in search_words if word in p.lower())
                if score > 0:
                    scored_p.append((score, p))
            
            # সেরা ৫টি অনুচ্ছেদ নেওয়া
            scored_p.sort(key=lambda x: x[0], reverse=True)
            context = "\n\n".join([item[1] for item in scored_p[:5]])

            # এপিআই কল
            final_prompt = f"""
            তুমি 'পদক্ষেপ মানবিক উন্নয়ন কেন্দ্র'-এর একজন বিশেষজ্ঞ এবং দাপ্তরিক সহকারী। 
            তোমার নাম 'পদক্ষেপ মিত্র'। নিচের তথ্যগুলো ব্যবহার করে ব্যবহারকারীর প্রশ্নের উত্তর দাও।
            তথ্যসূত্র না থাকলে নিজের থেকে ভুল তথ্য দেবে না।
            
            তথ্যসমূহ:
            {context if context else "কোনো নির্দিষ্ট তথ্য পাওয়া যায়নি।"}
            
            প্রশ্ন: {prompt}
            """
            
            response = model.generate_content(final_prompt)
            full_response = response.text
            
            st.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            error_msg = str(e)
            if "404" in error_msg:
                st.error("মডেল খুঁজে পাওয়া যায়নি। আপনার লাইব্রেরি ভার্সন চেক করুন।")
            elif "quota" in error_msg.lower():
                st.error("গুগল এপিআই কোটা শেষ হয়ে গেছে। দয়া করে ১ মিনিট পর চেষ্টা করুন।")
            else:
                st.error
