import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import json
from datetime import datetime
import pytz

# --- 1. ตั้งค่าหน้าจอ & Premium UI ---
st.set_page_config(page_title="Smart OR Pro", layout="wide", page_icon="🏥")

# CSS ตกแต่ง
st.markdown("""
    <style>
    .stApp { background-color: #f0f2f6; }
    div.block-container { padding-top: 2rem; }
    .stDataFrame, .stPlotlyChart { background-color: white; border-radius: 15px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    div[data-testid="stMetric"] { background-color: white; padding: 15px; border-radius: 12px; border-left: 5px solid #007bff; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    div[data-testid="stMetricValue"] { font-size: 24px !important; color: #2c3e50; }
    div[data-testid="stMetricLabel"] { font-size: 14px !important; color: #7f8c8d; }
    div.stButton > button { border-radius: 8px; border: none; box-shadow: 0 2px 5px rgba(0,0,0,0.1); transition: all 0.3s; }
    div.stButton > button:hover { transform: translateY(-2px); box-shadow: 0 5px 10px rgba(0,0,0,0.15); }
    h1 { color: #2c3e50; font-family: 'Helvetica Neue', sans-serif; }
    h2, h3 { color: #34495e; }
    </style>
    """, unsafe_allow_html=True)

# ฟังก์ชันเวลาไทย
def get_thai_time():
    tz = pytz.timezone('Asia/Bangkok')
    return datetime.now(tz).strftime("%H:%M:%S")

# --- 2. Connection ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def init_connection():
    try:
        service_info = dict(st.secrets["gcp_service_account"])
        service_info["private_key"] = service_info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(service_info, scopes=scope)
        client = gspread.authorize(creds)
        return client.open("Smart_OR_Database")
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None

sh = init_connection()

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.0-flash')

# --- 3. Sidebar ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3063/3063176.png", width=60)
    st.title("OR Management")
    st.markdown("---")
    
    tz = pytz.timezone('Asia/Bangkok')
    default_case = f"CASE-{datetime.now(tz).strftime('%Y%m%d')}-001"
    
    st.subheader("📋 Case Info")
    case_id = st.text_input("Case ID", default_case)
    doctor_name = st.selectbox("Surgeon", ["ศ.นพ.สมชาย (General)", "รศ.พญ.วิภา (OB-GYN)", "ผศ.นพ.มานพ (Ortho)"])
    
    # แก้ไขจุดที่มักเกิด Error บ่อย: เขียนให้อยู่บรรทัดเดียวกันชัดเจน
    procedure = st.text_input("Procedure", "Laparoscopic Appendectomy")
    
    st.markdown("---")
    if st.button("✨ AI Suggestion (Pick List)"):
        with st.status("AI Analyzing Preference Card..."):
            prompt = f"Surgeon: {doctor_name}, Procedure: {procedure}. Suggest surgical items & ICD-10."
            try:
                res = model.generate_content(prompt)
                st.info(res.text)
            except:
                st.error("AI Busy")

# --- 4. Main Layout ---
col_header1, col_header2 = st.columns([3, 1])
with col_header1:
    st.title("Smart Operating Room")
    st.caption(f"Real-time Data Driven & Decision Support System • {datetime.now(tz).strftime('%d %B %Y')}")
with col_header2:
    st.metric("Live Time (BKK)", get_thai_time())

st.divider()

if sh:
    try:
        sheet_logs = sh.worksheet("Surgical_Logs")
        sheet_inv = sh.worksheet("Inventory")
        
        inv_data = sheet_inv.get_all_records()
        df_inv = pd.DataFrame(inv_data)

        col1, col2 = st.columns([1.5, 1])

        # === LEFT: CONTROL CENTER ===
        with col1:
            st.subheader("🎮 Control Center")
            tab1, tab2, tab3 = st.tabs(["🎙️ Voice Command", "🛡️ Safety Count", "⏱️ Workflow Stamp"])

            with tab1:
                st.info("💡 Tip: พูดชื่อยาหรือวัสดุเพื่อตัดสต็อกทันที")
                user_input = st.chat_input("Ex. 'ใช้ Propofol 1 amp และ Vicryl 2 เส้น'...")
                
                if user_input:
                    with st.status("🔄 AI Processing & Inventory Matching..."):
                        try:
                            inv_list = ", ".join(df_inv['Item_Name'].tolist()) if not df_inv.empty else ""
                            prompt_extract = f"จากข้อความ: '{user_input}'. สกัด Item และ Qty แมตช์กับ: [{inv_list}]. ตอบ JSON Array: [{{'Item':'..', 'Qty':..
