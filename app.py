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

st.markdown("""
    <style>
    .stApp { background-color: #f0f2f6; }
    div.block-container { padding-top: 2rem; }
    .stDataFrame, .stPlotlyChart { background-color: white; border-radius: 15px; padding: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    div[data-testid="stMetric"] { background-color: white; padding: 15px; border-radius: 12px; border-left: 5px solid #007bff; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    div[data-testid="stMetricValue"] { font-size: 24px !important; color: #2c3e50; }
    
    /* ปรับแต่งปุ่มอัดเสียงให้เด่น */
    div[data-testid="stAudioInput"] {
        border: 2px solid #007bff;
        border-radius: 10px;
        padding: 10px;
        background-color: #e3f2fd;
    }
    
    h1 { color: #2c3e50; font-family: 'Helvetica Neue', sans-serif; }
    </style>
    """, unsafe_allow_html=True)

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
    
    st.subheader("1. Case Info")
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
    st.caption("Step-by-Step Intelligent Workflow")
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

        # === LEFT: ACTION ZONE ===
        with col1:
            st.subheader("2. Action Zone (ปฏิบัติการ)")
            
            # ใช้ Tabs แยกงานให้ชัดเจน ไม่ตีกัน
            tab1, tab2, tab3 = st.tabs(["🗣️ Voice Command", "🛡️ Safety Count", "⏱️ Workflow"])

            with tab1:
                st.info("🎙️ **วิธีใช้:** กดปุ่มไมค์ > พูดรายการของ > กดปุ่ม Stop > **ระบบจะบันทึกเอง**")
                
                # เปลี่ยนจาก Text Input เป็น Audio Input (High Tech!)
                audio_val = st.audio_input("กดเพื่อเริ่มอัดเสียงสั่งงาน")
                
                if audio_val:
                    with st.status("🎧 AI กำลังฟังเสียงและตัดสต็อก..."):
                        try:
                            inv_list = ", ".join(df_inv['Item_Name'].tolist()) if not df_inv.empty else ""
                            
                            # ส่งไฟล์เสียงให้ Gemini 2.0 ฟังโดยตรง!
                            prompt_extract = f"""
                            ฟังเสียงนี้ แล้วสกัดรายการวัสดุ(Item) และจำนวน(Qty)
                            โดยพยายามแมตช์เสียงกับรายการในคลังนี้: [{inv_list}]
                            ตอบเป็น JSON Array เท่านั้น: [{{'Item':'..', 'Qty':..}}]
                            """
                            
                            # ส่งทั้ง Prompt และ ไฟล์เสียง
                            response = model.generate_content([
                                prompt_extract,
                                {"mime_type": "audio/wav", "data": audio_val.read()}
                            ])
                            
                            # แปลงผลลัพธ์
                            items = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
                            
                            for item in items:
                                match = df_inv[df_inv['Item_Name'] == item.get('Item')]
                                if not match.empty:
                                    idx = match.index[0] + 2
                                    sheet_inv.update_cell(idx, 4, float(match.iloc[0]['Stock_Qty']) - float(item['Qty']))
                                    cost = float(match.iloc[0]['Price']) * float(item['Qty'])
                                    sheet_logs.append_row([get_thai_time(), case_id, item['Item'], item['Qty'], match.iloc[0]['Unit'], match.iloc[0]['Category'], cost, "Voice (Audio)"])
                                else:
                                    sheet_logs.append_row([get_thai_time(), case_id, item['Item'], item['Qty'], "?", "General", 0, "Not Found"])
                            
                            st.success("✅ บันทึกเสียงเรียบร้อย!")
                            # ใช้เวลาหน่วงนิดนึงให้คนเห็น Success ก่อน Rerun
                            import time
                            time.sleep(1)
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error: {e}")

            with tab2:
                st.write("##### 🧽 Surgical Safety Count")
                c1, c2 = st.columns(2)
                gauze_val = c1.number_input("Gauze Count", 0, 200, 10, key='g_cnt')
                needle_val = c2.number_input("Needle Count", 0, 100, 2, key='n_cnt')
                
                if st.checkbox("✅ Confirm Correctness"):
                    if st.button("Save Count Record", type="primary"):
                        t = get_thai_time()
                        sheet_logs.append_row([t, case_id, "Safety: Gauze", gauze_val, "pcs", "Safety", 0, "Correct"])
                        sheet_logs.append_row([t, case_id, "Safety: Needles", needle_val, "pcs", "Safety", 0, "Correct"])
                        st.success("Safety Recorded!")
                        st.rerun()

            with tab3:
                st.write("##### ⏱️ Critical Time Stamps")
                ct1, ct2, ct3 = st.columns(3)
                if ct1.button("Patient In"):
                    t = get_thai_time()
                    sheet_logs.append_row([t, case_id, "Patient In", 1, "Time", "Workflow", 0, ""])
                    st.toast(f"Patient In: {t}")
                    st.rerun()
                if ct2.button("🔪 Incision"):
                    t = get_thai_time()
                    sheet_logs.append_row([t, case_id, "Incision", 1, "Time", "Workflow", 0, ""])
                    st.toast(f"Incision: {t}")
                    st.rerun()
                if ct3.button("Close Skin"):
                    t = get_thai_time()
                    sheet_logs.append_row([t, case_id, "Close Skin", 1, "Time", "Workflow", 0, ""])
                    st.toast(f"Finished: {t}")
                    st.rerun()

            # Live Logs
            st.markdown("### 📝 3. Live Logs (บันทึกล่าสุด)")
            logs = sheet_logs.get_all_records()
            if logs:
                df_l = pd.DataFrame(logs)
                df_show = df_l[df_l['Case_ID'] == case_id].tail(8).iloc[::-1]
                st.dataframe(df_show[['Timestamp', 'Item', 'Qty', 'Total_Cost']], use_container_width=True, hide_index=True)

        # === RIGHT: DASHBOARD ===
        with col2:
            st.subheader("📊 4. Analytics")
            if logs:
                df_all = pd.DataFrame(logs)
                df_all['Total_Cost'] = pd.to_numeric(df_all['Total_Cost'], errors='coerce').fillna(0)
                df_case = df_all[df_all['Case_ID'] == case_id]
                
                total = df_case['Total_Cost'].sum()
                items = len(df_case)
                
                m1, m2 = st.columns(2)
                m1.metric("Total Cost", f"฿{total:,.0f}")
                m2.metric("Items Used", f"{items}")
                
                if not df_case.empty:
                    fig = px.pie(df_case, values='Total_Cost', names='Category', hole=0.6, title="Cost Structure")
                    fig.update_layout(showlegend=False, margin=dict(t=30, b=0, l=0, r=0), height=250)
                    st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            if st.button("🏁 End Case & Auto-Code", type="primary"):
                with st.status("🚀 AI Generating Summary..."):
                    summary = f"Case: {case_id}, Procedure: {procedure}\nItems: {len(df_case)} items used."
                    prompt = f"Summarize case: {summary}. Provide ICD-10, ICD-9-CM & Billing Note."
                    try:
                        res = model.generate_content(prompt)
                        st.markdown(res.text)
                        st.balloons()
                    except:
                        st.error("AI Error")

    except Exception as e:
        st.error(f"System Error: {e}")

else:
    st.stop()
