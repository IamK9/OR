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

# CSS สำหรับทำ UI ให้ดูแพง (Glassmorphism & Medical Clean Look)
st.markdown("""
    <style>
    /* พื้นหลังหลัก */
    .stApp {
        background-color: #f0f2f6;
    }
    
    /* การ์ดข้อมูล (White Card with Shadow) */
    div.block-container {
        padding-top: 2rem;
    }
    .stDataFrame, .stPlotlyChart {
        background-color: white;
        border-radius: 15px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    /* ตกแต่ง Metrics */
    div[data-testid="stMetric"] {
        background-color: white;
        padding: 15px;
        border-radius: 12px;
        border-left: 5px solid #007bff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetricValue"] {
        font-size: 24px !important;
        color: #2c3e50;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 14px !important; 
        color: #7f8c8d;
    }

    /* ปุ่มกด (Gradient Button) */
    div.stButton > button {
        border-radius: 8px;
        border: none;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        transition: all 0.3s;
    }
    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 10px rgba(0,0,0,0.15);
    }
    
    /* Header สวยๆ */
    h1 {
        color: #2c3e50;
        font-family: 'Helvetica Neue', sans-serif;
    }
    h2, h3 {
        color: #34495e;
    }
    </style>
    """, unsafe_allow_html=True)

# --- ฟังก์ชันเวลาประเทศไทย (สำคัญมากสำหรับการ Demo) ---
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

# --- 3. Sidebar (Medical Style) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3063/3063176.png", width=60) # ไอคอนแพทย์
    st.title("OR Management")
    st.markdown("---")
    
    # Case ID Auto Gen
    tz = pytz.timezone('Asia/Bangkok')
    default_case = f"CASE-{datetime.now(tz).strftime('%Y%m%d')}-001"
    
    st.subheader("📋 Case Info")
    case_id = st.text_input("Case ID", default_case)
    doctor_name = st.selectbox("Surgeon", ["ศ.นพ.สมชาย (General)", "รศ.พญ.วิภา (OB-GYN)", "ผศ.นพ.มานพ (Ortho)"])
    procedure = st.text_input("Procedure
