import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import json
from datetime import datetime
import pytz # เพิ่ม Library จัดการเวลา

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
    # โชว์เวลาตัวใหญ่ๆ ให้เห็นความเป็น Real-time
    st.metric("Live Time (BKK)", get_thai_time())

st.divider()

if sh:
    try:
        sheet_logs = sh.worksheet("Surgical_Logs")
        sheet_inv = sh.worksheet("Inventory")
        
        # Cache Inventory
        inv_data = sheet_inv.get_all_records()
        df_inv = pd.DataFrame(inv_data)

        # Layout แบ่ง 2 ฝั่ง (ซ้าย: Input, ขวา: Dashboard)
        col1, col2 = st.columns([1.5, 1])

        # === LEFT COLUMN: ACTION CENTER ===
        with col1:
            st.subheader("🎮 Control Center")
            
            # ใช้ Tabs เพื่อความ Clean
            tab1, tab2, tab3 = st.tabs(["🎙️ Voice Command", "🛡️ Safety Count", "⏱️ Workflow Stamp"])

            with tab1:
                st.info("💡 Tip: พูดชื่อยาหรือวัสดุเพื่อตัดสต็อกทันที")
                user_input = st.chat_input("Ex. 'ใช้ Propofol 1 amp และ Vicryl 2 เส้น'...")
                
                if user_input:
                    with st.status("🔄 AI Processing & Inventory Matching..."):
                        # ... (Logic เดิม - เพิ่มการใช้ get_thai_time()) ...
                        try:
                            inv_list = ", ".join(df_inv['Item_Name'].tolist()) if not df_inv.empty else ""
                            prompt_extract = f"จากข้อความ: '{user_input}'. สกัด Item และ Qty แมตช์กับ: [{inv_list}]. ตอบ JSON Array: [{{'Item':'..', 'Qty':..}}]"
                            res = model.generate_content(prompt_extract)
                            items = json.loads(res.text.strip().replace("```json", "").replace("```", ""))
                            
                            for item in items:
                                match = df_inv[df_inv['Item_Name'] == item.get('Item')]
                                if not match.empty:
                                    # ตัดสต็อก logic
                                    idx = match.index[0] + 2
                                    sheet_inv.update_cell(idx, 4, float(match.iloc[0]['Stock_Qty']) - float(item['Qty']))
                                    # บันทึก log
                                    cost = float(match.iloc[0]['Price']) * float(item['Qty'])
                                    sheet_logs.append_row([get_thai_time(), case_id, item['Item'], item['Qty'], match.iloc[0]['Unit'], match.iloc[0]['Category'], cost, "Voice"])
                                else:
                                    sheet_logs.append_row([get_thai_time(), case_id, item['Item'], item['Qty'], "?", "General", 0, "Not Found"])
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

            with tab2:
                c1, c2 = st.columns(2)
                c1.number_input("Gauze Count", 0, 100, 10, key='g_cnt')
                c2.number_input("Needle Count", 0, 50, 2, key='n_cnt')
                if st.checkbox("✅ Confirm Safety Count"):
                    if st.button("Save Safety Record"):
                        sheet_logs.append_row([get_thai_time(), case_id, "Safety Count", 1, "Check", "Safety", 0, "Correct"])
                        st.success("Safety Check Recorded!")

            with tab3:
                col_t1, col_t2, col_t3 = st.columns(3)
                if col_t1.button("Patients In"):
                    t = get_thai_time()
                    sheet_logs.append_row([t, case_id, "Patient In", 1, "Time", "Workflow", 0, ""])
                    st.toast(f"Patient In: {t}")
                if col_t2.button("🔪 Incision"):
                    t = get_thai_time()
                    sheet_logs.append_row([t, case_id, "Incision", 1, "Time", "Workflow", 0, ""])
                    st.toast(f"Incision: {t}")
                if col_t3.button("Close Skin"):
                    t = get_thai_time()
                    sheet_logs.append_row([t, case_id, "Close Skin", 1, "Time", "Workflow", 0, ""])
                    st.toast(f"Finished: {t}")

            # Recent Logs Table
            st.markdown("### 📝 Live Logs")
            logs = sheet_logs.get_all_records()
            if logs:
                df_l = pd.DataFrame(logs)
                # Show only current case & essential columns
                df_show = df_l[df_l['Case_ID'] == case_id].tail(5).iloc[::-1]
                st.dataframe(df_show[['Timestamp', 'Item', 'Qty', 'Total_Cost']], use_container_width=True, hide_index=True)

        # === RIGHT COLUMN: ANALYTICS DASHBOARD ===
        with col2:
            st.subheader("📊 Live Analytics")
            
            if logs:
                df_all = pd.DataFrame(logs)
                df_all['Total_Cost'] = pd.to_numeric(df_all['Total_Cost'], errors='coerce').fillna(0)
                df_case = df_all[df_all['Case_ID'] == case_id]
                
                # Big Metrics Cards
                total = df_case['Total_Cost'].sum()
                items = len(df_case)
                
                m1, m2 = st.columns(2)
                m1.metric("Total Cost", f"฿{total:,.0f}", delta="Real-time")
                m2.metric("Items Used", f"{items} pcs")
                
                # Chart
                if not df_case.empty:
                    fig = px.pie(df_case, values='Total_Cost', names='Category', hole=0.6, title="Cost Breakdown")
                    fig.update_layout(showlegend=False, margin=dict(t=30, b=0, l=0, r=0), height=250)
                    st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            if st.button("🏁 End Case & Auto-Code", type="primary"):
                with st.status("🚀 AI Generating Summary & ICD Codes..."):
                    # (Code AI Summary เดิม)
                    summary = f"Case: {case_id}, Procedure: {procedure}\nItems: {len(df_case)} items used."
                    prompt = f"Summarize case: {summary}. Provide ICD-10, ICD-9-CM & Billing Note."
                    res = model.generate_content(prompt)
                    st.markdown(res.text)
                    st.balloons()

    except Exception as e:
        st.error(f"System Error: {e}")

else:
    st.stop()
