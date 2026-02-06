import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import json
from datetime import datetime

# --- 1. ตั้งค่าหน้าจอ (UI Configuration) ---
st.set_page_config(page_title="Smart OR App", layout="wide", page_icon="🏥")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stDataFrame { background-color: white; border-radius: 10px; padding: 10px; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; color: #007bff; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏥 Smart OR: Technology & Innovation")
st.markdown("##### ระบบติดตามผล วิเคราะห์ และช่วยตัดสินใจในงานห้องผ่าตัด")
st.divider()

# --- 2. การเชื่อมต่อข้อมูล (Connection Setup) ---
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def init_connection():
    try:
        # ดึง Credentials และจัดการ Format ของ Private Key
        service_info = dict(st.secrets["gcp_service_account"])
        service_info["private_key"] = service_info["private_key"].replace("\\n", "\n")
        
        creds = Credentials.from_service_account_info(service_info, scopes=scope)
        client = gspread.authorize(creds)
        
        # เปิดไฟล์ Google Sheet (ชื่อไฟล์ต้องตรงกับใน Drive)
        return client.open("Smart_OR_Database")
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None

sh = init_connection()

# ตั้งค่า AI Gemini
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.0-flash')

# --- 3. Sidebar (Setup) ---
st.sidebar.header("📋 Case Setup")
# สร้าง Case ID อัตโนมัติตามเวลา
default_case_id = f"CASE-{datetime.now().strftime('%Y%m%d-%H%M')}"
case_id = st.sidebar.text_input("Case ID", default_case_id)
doctor_name = st.sidebar.selectbox("ศัลยแพทย์", ["นพ.สมชาย", "พญ.วิภา", "นพ.มานพ"])
procedure = st.sidebar.text_input("หัตถการ", "Laparoscopic Appendectomy")

if st.sidebar.button("🤖 AI Suggestion (แนะนำของ)"):
    with st.sidebar.status("AI กำลังวิเคราะห์ Preference Card..."):
        prompt = f"หมอ {doctor_name} ทำ {procedure} แนะนำวัสดุและยาที่ต้องเตรียม (Pick List) พร้อมรหัส ICD-10"
        try:
            res = model.generate_content(prompt)
            st.sidebar.info(res.text)
        except Exception as e:
            st.sidebar.error(f"AI Error: {e}")

# --- 4. Main App Logic ---
if sh:
    try:
        # เชื่อมต่อ Worksheet
        sheet_logs = sh.worksheet("Surgical_Logs")
        sheet_inv = sh.worksheet("Inventory")
        
        # โหลดข้อมูล Inventory มาเก็บไว้ (Cache) เพื่อความเร็ว
        inv_data = sheet_inv.get_all_records()
        df_inv = pd.DataFrame(inv_data)

        # แบ่งหน้าจอซ้าย-ขวา
        col1, col2 = st.columns([1.2, 0.8])

        # === COLUMN 1: TRACKING & RECORDING ===
        with col1:
            st.header("📝 1. Intra-operative Record")
            st.info(f"📍 Current Case: **{case_id}**")
            
            # สร้าง Tabs ย่อย
            tab1, tab2, tab3 = st.tabs(["🎙️ Material & Voice", "🧽 Surgical Count", "⏱️ Time & Staff"])

            # --- TAB 1: ตัดสต็อกด้วยเสียง ---
            with tab1:
                user_input = st.chat_input("สั่งการด้วยเสียงหรือพิมพ์ เช่น 'ใช้ Propofol 2 amp และ Vicryl 3-0 2 เส้น'...")
                
                if user_input:
                    with st.status("AI กำลังประมวลผลและตัดสต็อก..."):
                        try:
                            # 1. เตรียมรายการสินค้าให้ AI รู้จัก
                            inv_list = ", ".join(df_inv['Item_Name'].tolist()) if not df_inv.empty else ""
                            
                            # 2. ยิง Prompt หา Gemini
                            prompt_extract = f"""
                            จากข้อความ: '{user_input}' 
                            สกัดชื่อวัสดุ(Item) และจำนวน(Qty) โดยพยายามแมตช์ชื่อกับรายการเหล่านี้: [{inv_list}]
                            ตอบเป็น JSON Array เท่านั้น: [{{'Item': '...', 'Qty': ...}}]
                            """
                            res = model.generate_content(prompt_extract)
                            
                            # 3. แปลง Text เป็น JSON
                            clean_json = res.text.strip().replace("```json", "").replace("```", "")
                            extracted_items = json.loads(clean_json)
                            
                            # 4. วนลูปบันทึกและตัดสต็อก
                            for item in extracted_items:
                                item_name = item.get('Item')
                                qty_used = float(item.get('Qty', 0))
                                
                                # ค้นหาใน Inventory DF
                                match = df_inv[df_inv['Item_Name'] == item_name]
                                
                                if not match.empty:
                                    # เจอของในคลัง -> ตัดสต็อก
                                    current_stock = float(match.iloc[0]['Stock_Qty'])
                                    price = float(match.iloc[0]['Price'])
                                    unit = match.iloc[0]['Unit']
                                    category = match.iloc[0]['Category']
                                    
                                    # หาตำแหน่งแถวใน Sheet (Index + 2 เพราะมี Header และเริ่มที่ 1)
                                    row_idx = match.index[0] + 2 
                                    
                                    # อัปเดตสต็อกใหม่
                                    new_stock = current_stock - qty_used
                                    sheet_inv.update_cell(row_idx, 4, new_stock) # คอลัมน์ 4 คือ Stock_Qty
                                    
                                    # คำนวณราคารวม
                                    total_cost = price * qty_used
                                    
                                    # บันทึก Log
                                    log_row = [
                                        datetime.now().strftime("%H:%M:%S"),
                                        case_id, item_name, qty_used, unit, category, total_cost, "Auto-Deduct"
                                    ]
                                    sheet_logs.append_row(log_row)
                                else:
                                    # ไม่เจอของ -> บันทึกชื่อตามที่พูด
                                    sheet_logs.append_row([
                                        datetime.now().strftime("%H:%M:%S"),
                                        case_id, item_name, qty_used, "unknown", "General", 0, "Item not found in Inv"
                                    ])

                            st.success(f"บันทึกเรียบร้อย: {user_input}")
                            # Rerun เพื่ออัปเดตตาราง
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error Processing: {e}")

            # --- TAB 2: นับของ (Safety) ---
            with tab2:
                st.subheader("Surgical Count Check")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.number_input("Gauze/Ray-tec", 0, 100, 10, key="cnt_gauze")
                with c2:
                    st.number_input("Sharps/Needles", 0, 50, 0, key="cnt_sharp")
                with c3:
                    st.number_input("Instruments", 0, 200, 0, key="cnt_inst")
                
                st.write("---")
                is_correct = st.checkbox("✅ Closing Count Correct (นับครบถูกต้อง)")
                if is_correct:
                    if st.button("บันทึกผลการนับ"):
                        sheet_logs.append_row([
                            datetime.now().strftime("%H:%M:%S"),
                            case_id, "Surgical Count", 1, "Check", "Safety", 0, "Count Correct"
                        ])
                        st.success("บันทึกความปลอดภัยเรียบร้อย")

            # --- TAB 3: ลงเวลาและทีม ---
            with tab3:
                st.subheader("Time Stamping")
                t1, t2, t3 = st.columns(3)
                
                if t1.button("Patients In Room"):
                    time_now = datetime.now().strftime("%H:%M:%S")
                    sheet_logs.append_row([time_now, case_id, "Patient In", 1, "Time", "Workflow", 0, ""])
                    st.toast(f"Patient In: {time_now}")
                    
                if t2.button("🔪 Incision (ลงมีด)"):
                    time_now = datetime.now().strftime("%H:%M:%S")
                    sheet_logs.append_row([time_now, case_id, "Incision Start", 1, "Time", "Workflow", 0, ""])
                    st.toast(f"Incision: {time_now}")
                    
                if t3.button("Dressing Done"):
                    time_now = datetime.now().strftime("%H:%M:%S")
                    sheet_logs.append_row([time_now, case_id, "Operation End", 1, "Time", "Workflow", 0, ""])
                    st.toast(f"Finished: {time_now}")
                
                st.divider()
                st.selectbox("Scrub Nurse", ["พยาบาล A", "พยาบาล B"])
                st.selectbox("Circulate Nurse", ["พยาบาล C", "พยาบาล D"])

            # --- แสดงรายการ Log ล่าสุด (Recent Logs) ---
            st.write("---")
            st.subheader("📋 Recent Activity Logs")
            
            # ดึงข้อมูล Log
            logs_data = sheet_logs.get_all_records()
            if logs_data:
                df_logs = pd.DataFrame(logs_data)
                # กรองเฉพาะเคสปัจจุบัน
                df_show = df_logs[df_logs['Case_ID'] == case_id].tail(8)
                # เรียงลำดับเอาอันใหม่สุดขึ้นบน (กลับด้าน)
                df_show = df_show.iloc[::-1]
                
                st.dataframe(
                    df_show[['Timestamp', 'Item', 'Qty', 'Unit', 'Category', 'Total_Cost']], 
                    use_container_width=True, 
                    hide_index=True
                )
            else:
                st.info("Waiting for data...")

        # === COLUMN 2: ANALYSIS & SUMMARY ===
        with col2:
            st.header("📊 2. Analysis")
            
            if logs_data:
                df_all = pd.DataFrame(logs_data)
                
                # แปลงข้อมูลตัวเลข (กัน Error)
                df_all['Total_Cost'] = pd.to_numeric(df_all['Total_Cost'], errors='coerce').fillna(0)
                
                # Filter ข้อมูลเฉพาะเคสนี้
                df_case = df_all[df_all['Case_ID'] == case_id]
                
                # 1. Metrics
                total_cost = df_case['Total_Cost'].sum()
                items_count = len(df_case)
                
                m1, m2 = st.columns(2)
                m1.metric("Total Cost (THB)", f"{total_cost:,.0f}")
                m2.metric("Items Used", f"{items_count}")
                
                # 2. Pie Chart (Cost Breakdown)
                if not df_case.empty:
                    st.markdown("###### Cost Breakdown by Category")
                    fig = px.pie(df_case, values='Total_Cost', names='Category', hole=0.4, 
                                 color_discrete_sequence=px.colors.sequential.RdBu)
                    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300)
                    st.plotly_chart(fig, use_container_width=True)
                
            # --- ปุ่มจบเคส ---
            st.divider()
            if st.button("🏁 Finish Case & Code ICD"):
                with st.status("Generating Case Summary..."):
                    # รวบรวมข้อมูลสรุปส่ง AI
                    summary_text = f"Case: {case_id}, Procedure: {procedure}, Doctor: {doctor_name}\n"
                    if logs_data and not df_case.empty:
                         items_summary = df_case.groupby('Item')['Qty'].sum().to_string()
                         summary_text += f"Items Used:\n{items_summary}"
                    
                    prompt_final = f"""
                    สรุปเคสผ่าตัดจากข้อมูลนี้:
                    {summary_text}
                    
                    ขอ Output เป็นตารางสรุป:
                    1. Diagnosis (ICD-10)
                    2. Procedure (ICD-9-CM)
                    3. Total Cost Estimate
                    4. Note for Billing
                    """
                    try:
                        res_final = model.generate_content(prompt_final)
                        st.markdown(res_final.text)
                        st.balloons()
                    except Exception as e:
                        st.error(f"Summary Error: {e}")

    except Exception as e:
        st.error(f"Application Error: {e}")
        st.warning("กรุณาตรวจสอบชื่อ Sheet: 'Inventory' และ 'Surgical_Logs' ว่าถูกต้องหรือไม่")

else:
    st.stop()
