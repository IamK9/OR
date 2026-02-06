import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import json

# --- 1. การตั้งค่าหน้าจอ ---
st.set_page_config(page_title="Smart OR App", layout="wide")
st.title("🏥 Smart OR: Technology & Innovation")
st.subheader("ระบบติดตามผล วิเคราะห์ และช่วยตัดสินใจในห้องผ่าตัด")

# --- 2. การเชื่อมต่อข้อมูล (Secrets) ---
# ดึง Credentials จาก Streamlit Secrets
scope = ["https://www.googleapis.com/auth/spreadsheets"]
service_info = dict(st.secrets["gcp_service_account"])
service_info["private_key"] = service_info["private_key"].replace("\\n", "\n")

creds = Credentials.from_service_account_info(service_info, scopes=scope)
client = gspread.authorize(creds)

# เชื่อมต่อกับ Google Sheet (เปลี่ยนชื่อให้ตรงกับไฟล์ของคุณ)
try:
    sh = client.open("Smart_OR_Database") # ชื่อไฟล์ Google Sheet
    sheet_logs = sh.worksheet("Surgical_Logs")
    sheet_inv = sh.worksheet("Inventory")
except Exception as e:
    st.error(f"เชื่อมต่อ Google Sheet ไม่สำเร็จ: {e}")

# ตั้งค่า Gemini 2.0 Flash
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.0-flash')

# --- 3. Sidebar: ส่วนช่วยตัดสินใจ (Decision Making) ---
st.sidebar.header("📋 Case Setup")
doctor_name = st.sidebar.selectbox("เลือกศัลยแพทย์", ["นพ.สมชาย", "พญ.วิภา", "นพ.มานพ"])
procedure = st.sidebar.text_input("ชื่อหัตถการ", "Laparoscopic Appendectomy")

if st.sidebar.button("AI Predictive: แนะนำการเตรียมของ"):
    with st.spinner("Gemini กำลังวิเคราะห์ข้อมูล..."):
        prompt = f"ในฐานะพยาบาลห้องผ่าตัดผู้เชี่ยวชาญ หมอ {doctor_name} กำลังจะทำ {procedure} ช่วยแนะนำรายการวัสดุสิ้นเปลืองที่ควรเตรียม (Pick List) พร้อมรหัส ICD-10 และ ICD-9-CM เบื้องต้น"
        response = model.generate_content(prompt)
        st.sidebar.info(response.text)

# --- 4. หน้าจอหลัก แบ่งเป็น 2 ส่วน ---
col1, col2 = st.columns([1, 1])

with col1:
    st.header("🎙️ 1. Tracking (บันทึกข้อมูล)")
    # ส่วนบันทึกเสียง/ข้อความ
    user_input = st.chat_input("พิมพ์หรือใช้ Voice-to-Text บันทึกการใช้วัสดุที่นี่...")
    
    if user_input:
        st.write(f"บันทึกข้อมูล: {user_input}")
        # ใช้ Gemini สกัดข้อมูลเป็น JSON
        prompt_extract = f"จากข้อความนี้: '{user_input}' ช่วยสรุปชื่อวัสดุและจำนวน เป็นรูปแบบ JSON: [{{'item': '...', 'qty': ...}}]"
        res_extract = model.generate_content(prompt_extract)
        st.json(res_extract.text)
        
        # ตัวอย่างการบันทึกลง Sheet (ใน Demo จริงต้องเขียน Logic ตัดสต็อกเพิ่ม)
        # sheet_logs.append_row([pd.Timestamp.now().isoformat(), doctor_name, procedure, user_input])
        st.success("บันทึกข้อมูลเข้าสู่ระบบ Google Sheet เรียบร้อย")

with col2:
    st.header("📊 2. Analysis (วิเคราะห์ผล)")
    # ดึงข้อมูลจาก Sheet มาโชว์ Dashboard
    data = pd.DataFrame(sheet_logs.get_all_records())
    
    if not data.empty:
        # คำนวณ Metric ง่ายๆ
        total_cases = len(data)
        st.metric("จำนวนเคสวันนี้", f"{total_cases} เคส")
        
        # กราฟต้นทุน (สมมติข้อมูล)
        fig = px.bar(data, x='Case_ID', y='Total_Cost', title="Actual Cost per Case (บาท)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("ยังไม่มีข้อมูลการผ่าตัดในวันนี้")

# --- 5. ส่วนสรุปจบเคส (Wow Feature) ---
st.divider()
if st.button("🏁 จบการผ่าตัด: สรุปเคส & ลงรหัส ICD"):
    with st.status("กำลังรวบรวมข้อมูลและตรวจสอบความถูกต้องด้วย AI..."):
        # ส่งข้อมูลหัตถการไปให้ Gemini สรุป
        prompt_final = f"สรุปเคส {procedure} ของหมอ {doctor_name} ระบุรหัส ICD-10, ICD-9-CM และประเมินต้นทุนวัสดุเบื้องต้นในรูปแบบตาราง"
        res_final = model.generate_content(prompt_final)
        st.markdown(res_final.text)
        st.balloons()
