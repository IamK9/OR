import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import google.generativeai as genai
import json
from datetime import datetime

# --- 1. UI Configuration ---
st.set_page_config(page_title="Smart OR App", layout="wide", page_icon="🏥")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stDataFrame { background-color: white; border-radius: 10px; padding: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏥 Smart OR: Technology & Innovation")
st.markdown("##### ระบบติดตามผล วิเคราะห์ และช่วยตัดสินใจในงานห้องผ่าตัด")
st.divider()

# --- 2. Connection Setup ---
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

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

# --- 3. Sidebar (Setup) ---
st.sidebar.header("📋 Case Setup")
case_id = st.sidebar.text_input("Case ID", f"CASE-{datetime.now().strftime('%Y%m%d-%H%M')}")
doctor_name = st.sidebar.selectbox("ศัลยแพทย์", ["นพ.สมชาย", "พญ.วิภา", "นพ.มานพ"])
procedure = st.sidebar.text_input("หัตถการ", "Laparoscopic Appendectomy")

if st.sidebar.button("AI Suggestion (แนะนำของ)"):
    with st.sidebar.status("AI กำลังวิเคราะห์ Preference Card..."):
        prompt = f"หมอ {doctor_name} ทำ {procedure} แนะนำวัสดุและยาที่ต้องเตรียม (Pick List) พร้อมรหัส ICD-10"
        try:
            res = model.generate_content(prompt)
            st.sidebar.info(res.text)
        except:
            st.sidebar.error("AI ไม่ตอบสนอง")

# --- 4. Main App ---
if sh:
    try:
        sheet_logs = sh.worksheet("Surgical_Logs")
        sheet_inv = sh.worksheet("Inventory")
        
        # โหลดข้อมูล Inventory มาเก็บไว้ใน Cache เพื่อความเร็วในการค้นหา
        inv_data = sheet_inv.get_all_records()
        df_inv = pd.DataFrame(inv_data)

        col1, col2 = st.columns([1.2, 0.8])

        with col1:
            st.header("🎙️ 1. Tracking (บันทึกข้อมูล & ตัดสต็อก)")
            st.info(f"📍 กำลังบันทึกข้อมูลของ: **{case_id}**")
            
            # Input รับเสียง/ข้อความ
            user_input = st.chat_input("สั่งการด้วยเสียงหรือพิมพ์ เช่น 'ใช้ Propofol 2 amp และ Gauze 5 ชิ้น'...")
            
            if user_input:
                # 1. ให้ AI สกัดของและจำนวนออกมาเป็น JSON
                with st.status("AI กำลังประมวลผลและตัดสต็อก..."):
                    try:
                        # Prompt ให้ AI แมตช์ของกับ Inventory
                        inv_list = ", ".join(df_inv['Item_Name'].tolist()) if not df_inv.empty else ""
                        prompt_extract = f"""
                        จากข้อความ: '{user_input}' 
                        ให้สกัดชื่อวัสดุ(Item) และจำนวน(Qty) โดยพยายามแมตช์กับรายการในคลังนี้: [{inv_list}]
                        ตอบเป็น JSON Array เท่านั้น: [{{'Item': '...', 'Qty': ...}}]
                        """
                        res = model.generate_content(prompt_extract)
                        extracted_items = json.loads(res.text.strip().replace("```json", "").replace("```", ""))
                        
                        # 2. วนลูปบันทึกทีละรายการ และตัดสต็อก
                        for item in extracted_items:
                            item_name = item.get('Item')
                            qty_used = float(item.get('Qty', 0))
                            
                            # ค้นหาข้อมูลใน Inventory (ราคา, หน่วย, หมวดหมู่)
                            match = df_inv[df_inv['Item_Name'] == item_name]
                            
                            if not match.empty:
                                current_stock = float(match.iloc[0]['Stock_Qty'])
                                price = float(match.iloc[0]['Price'])
                                unit = match.iloc[0]['Unit']
                                category = match.iloc[0]['Category']
                                row_idx = match.index[0] + 2 # +2 เพราะ gspread เริ่มแถว 1 และมี header
                                
                                # คำนวณ
                                new_stock = current_stock - qty_used
                                total_cost = price * qty_used
                                
                                # อัปเดตสต็อกใน Sheet Inventory (เฉพาะ Cell ที่เปลี่ยน)
                                sheet_inv.update_cell(row_idx, 4, new_stock) # สมมติ Stock อยู่คอลัมน์ 4
                                
                                # บันทึกลง Surgical_Logs
                                log_row = [
                                    datetime.now().strftime("%H:%M:%S"),
                                    case_id,
                                    item_name,
                                    qty_used,
                                    unit,
                                    category,
                                    total_cost
                                ]
                                sheet_logs.append_row(log_row)
                            else:
                                # กรณีไม่เจอในคลัง บันทึกแบบทั่วไป
                                sheet_logs.append_row([datetime.now().strftime("%H:%M:%S"), case_id, item_name, qty_used, "unknown", "General", 0])

                        st.success(f"บันทึกและตัดสต็อกเรียบร้อย: {user_input}")
                        
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาด: {e}")

            # --- ส่วนแสดงตาราง Log เหมือน Smart Anesthesia ---
            st.subheader("📋 Recent Logs (รายการล่าสุด)")
            # ดึงข้อมูล Log ล่าสุดมาโชว์
            logs_data = sheet_logs.get_all_records()
            if logs_data:
                df_logs = pd.DataFrame(logs_data)
                # กรองดูเฉพาะ Case ปัจจุบัน
                df_current_case = df_logs[df_logs['Case_ID'] == case_id].tail(10) # โชว์ 10 รายการล่าสุด
                
                # จัดเรียงคอลัมน์ให้สวยงาม
                if not df_current_case.empty:
                    st.dataframe(
                        df_current_case[['Timestamp', 'Item', 'Qty', 'Unit', 'Category', 'Total_Cost']],
                        use_container_width=True,
                        hide_index=True
                    )
            else:
                st.info("ยังไม่มีรายการบันทึก")

        with col2:
            st.header("📊 2. Analysis (วิเคราะห์ผล)")
            
            if logs_data:
                df_all = pd.DataFrame(logs_data)
                # แปลงข้อมูลตัวเลข
                df_all['Total_Cost'] = pd.to_numeric(df_all['Total_Cost'], errors='coerce').fillna(0)
                
                # Metrics Dashboard
                total_cost = df_all[df_all['Case_ID'] == case_id]['Total_Cost'].sum()
                item_count = len(df_all[df_all['Case_ID'] == case_id])
                
                m1, m2 = st.columns(2)
                m1.metric("ยอดรวมเคสนี้ (บาท)", f"{total_cost:,.0f}")
                m2.metric("จำนวนรายการ", f"{item_count}")
                
                # Chart
                st.markdown("###### สัดส่วนค่าใช้จ่ายตามหมวดหมู่")
                if 'Category' in df_all.columns:
                    df_chart = df_all[df_all['Case_ID'] == case_id]
                    if not df_chart.empty:
                        fig = px.pie(df_chart, values='Total_Cost', names='Category', hole=0.4)
                        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
                        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Data Error: {e}")
        st.warning("กรุณาตรวจสอบว่ามี Sheet ชื่อ 'Inventory' และ 'Surgical_Logs' และหัวตารางถูกต้อง")
else:
    st.stop()
