import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import json

# --- 1. ตั้งค่าหน้าจอ (UI Configuration) ---
st.set_page_config(page_title="Smart OR App", layout="wide", page_icon="🏥")

# ตกแต่ง CSS เล็กน้อยเพื่อให้ดูสะอาดตา
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("🏥 Smart OR: Technology & Innovation")
st.markdown("##### ระบบติดตามผล วิเคราะห์ และช่วยตัดสินใจในงานห้องผ่าตัด")
st.divider()

# --- 2. การเชื่อมต่อข้อมูล (Authentication & Connectivity) ---
# กำหนด Scopes ให้ครอบคลุมทั้ง Sheets และ Drive เพื่อป้องกัน Error 403
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def init_connection():
    try:
        # ดึง Credentials จาก Secrets และจัดการเรื่องขึ้นบรรทัดใหม่ใน Private Key
        service_info = dict(st.secrets["gcp_service_account"])
        service_info["private_key"] = service_info["private_key"].replace("\\n", "\n")
        
        creds = Credentials.from_service_account_info(service_info, scopes=scope)
        client = gspread.authorize(creds)
        
        # เปิดไฟล์ Google Sheet (ต้องชื่อตรงกับใน Drive)
        sh = client.open("Smart_OR_Database") 
        return sh
    except Exception as e:
        st.error(f"❌ ไม่สามารถเชื่อมต่อฐานข้อมูลได้: {e}")
        return None

sh = init_connection()

# ตั้งค่า Gemini 2.0 Flash
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-2.0-flash')

# --- 3. ส่วนควบคุมด้านข้าง (Decision Making - Sidebar) ---
st.sidebar.header("📋 Case Setup")
doctor_name = st.sidebar.selectbox("เลือกศัลยแพทย์", ["นพ.สมชาย", "พญ.วิภา", "นพ.มานพ"])
procedure = st.sidebar.text_input("ชื่อหัตถการ", "Laparoscopic Appendectomy")

if st.sidebar.button("AI Predictive: แนะนำการเตรียมของ"):
    with st.sidebar.status("Gemini กำลังวิเคราะห์ Data..."):
        prompt = f"ในฐานะพยาบาลห้องผ่าตัดผู้เชี่ยวชาญ หมอ {doctor_name} กำลังจะทำ {procedure} ช่วยแนะนำรายการวัสดุสิ้นเปลืองที่ควรเตรียม (Pick List) พร้อมรหัส ICD-10 และ ICD-9-CM เบื้องต้น"
        response = model.generate_content(prompt)
        st.sidebar.info(response.text)

# --- 4. หน้าจอหลัก (Tracking & Analysis) ---
if sh:
    try:
        sheet_logs = sh.worksheet("Surgical_Logs")
        
        col1, col2 = st.columns([1, 1])

        with col1:
            st.header("🎙️ 1. Tracking (บันทึกข้อมูล)")
            user_input = st.chat_input("พิมพ์หรือใช้ Voice-to-Text บันทึกข้อมูลที่นี่...")
            
            if user_input:
                with st.status("AI กำลังสกัดข้อมูลวัสดุ..."):
                    prompt_extract = f"สกัดชื่อวัสดุและจำนวนจากข้อความนี้: '{user_input}' ให้เป็น JSON: [{{'item': '...', 'qty': ...}}]"
                    res_extract = model.generate_content(prompt_extract)
                    extracted_data = res_extract.text
                
                st.write(f"**บันทึกสำเร็จ:** {user_input}")
                st.json(extracted_data)
                
                # บันทึกลง Google Sheet
                new_row = [pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), doctor_name, procedure, user_input, 0, "AUTO-ID"]
                sheet_logs.append_row(new_row)
                st.success("อัปเดตข้อมูลลง Google Sheet เรียบร้อยแล้ว")

        with col2:
            st.header("📊 2. Analysis (วิเคราะห์ผล)")
            # ดึงข้อมูลมาทำ Dashboard
            raw_data = sheet_logs.get_all_records()
            if raw_data:
                df = pd.DataFrame(raw_data)
                
                # แสดง Metrics
                m1, m2 = st.columns(2)
                m1.metric("จำนวนเคสทั้งหมด", f"{len(df)} เคส")
                m2.metric("งบประมาณรวม (บาท)", f"{df['Total_Cost'].sum():,.0f}")
                
                # กราฟต้นทุน
                if 'Total_Cost' in df.columns and 'Case_ID' in df.columns:
                    fig = px.bar(df, x='Case_ID', y='Total_Cost', 
                                 title="ต้นทุนจริงรายเคส (Actual Cost per Case)",
                                 color='Total_Cost', color_continuous_scale='Viridis')
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("ยังไม่มีข้อมูลการผ่าตัดในระบบ")

    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลแผ่นชีต: {e}")

# --- 5. สรุปจบเคส (Wow Feature) ---
st.divider()
if st.button("🏁 จบการผ่าตัด: สรุปเคส & ลงรหัส ICD"):
    with st.status("Gemini 2.0 Flash กำลังสร้างบทสรุปอัจฉริยะ..."):
        # รวบรวมข้อมูลรายการวัสดุที่ใช้จริงจากบันทึก (ตัวอย่าง)
        prompt_final = f"สรุปเคส {procedure} ของหมอ {doctor_name} ระบุรหัส ICD-10, ICD-9-CM และประเมินต้นทุนวัสดุเบื้องต้นในรูปแบบตาราง"
        res_final = model.generate_content(prompt_final)
        st.markdown(res_final.text)
        st.balloons()
