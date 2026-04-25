import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import io
import urllib.parse
import base64
import re  # Text se quantity nikalne ke liye

st.set_page_config(page_title="Celvia Smart Print Portal", layout="wide", page_icon="📦")

# 👇 DEFAULTS (PRE-FILLED DATA) 👇
DEFAULT_MAPPING_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=158825893&single=true&output=csv"
DEFAULT_PRODUCTS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=0&single=true&output=csv"
DEFAULT_APP_ID = "Untitledspreadsheet-306094028"

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuration")
mapping_url = st.sidebar.text_input("Mapping CSV Link", value=DEFAULT_MAPPING_URL)
products_url = st.sidebar.text_input("Products CSV Link", value=DEFAULT_PRODUCTS_URL)
app_id = st.sidebar.text_input("AppSheet App ID", value=DEFAULT_APP_ID)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh / Sync Data"):
    st.rerun()

# --- MAIN UI HEADER ---
st.title("📦 Celvia Smart Label WMS (Ultra Pro UI)")
st.markdown("<p style='color: #64748b; font-size: 16px; font-weight: bold;'>Upload PDFs -> Auto-Sort by SKU & Quantity -> Print Safely.</p>", unsafe_allow_html=True)

# --- MULTIPLE PDF UPLOADER ---
uploaded_pdfs = st.file_uploader("📥 Upload Flipkart PDF(s) Here", type=["pdf"], accept_multiple_files=True)

if uploaded_pdfs:
    with st.spinner("Analyzing PDFs, Extracting Quantities & Sorting... 🚀"):
        try:
            map_df = pd.read_csv(mapping_url)
            prod_df = pd.read_csv(products_url)
            
            map_df['Flipkart_SKU'] = map_df['Flipkart_SKU'].astype(str).str.strip()
            prod_df['SKU'] = prod_df['SKU'].astype(str).str.strip()
            
            master_sku_pdfs = {}
            
            # Smart PDF Aggregation & Quantity Extraction
            for uploaded_file in uploaded_pdfs:
                doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    text = page.get_text()
                    
                    # 1. Master SKU Dhoondna
                    found_master_sku = "Unmapped_SKU"
                    for index, row in map_df.iterrows():
                        if row['Flipkart_SKU'] in text:
                            found_master_sku = row['Master_SKU']
                            break
                    
                    # 2. Quantity Dhoondna (Updated Regex Scanner for "Total Qty: X")
                    item_qty = 1 # Default 1 manenge
                    
                    # Pehle strictly "Total Qty: X" dhoondhega
                    qty_match = re.search(r'(?i)Total\s+Qty\s*:\s*(\d+)', text)
                    
                    # Agar Flipkart kal ko wapas purana format bhej de, toh uske liye backup:
                    if not qty_match:
                        qty_match = re.search(r'(?i)(?:Quantity|Qty)\s*:\s*(\d+)', text)
                        
                    if qty_match:
                        item_qty = int(qty_match.group(1))
                    
                    # 3. PDF ko naye group mein daalna (SKU + Qty combination)
                    group_key = (found_master_sku, item_qty)
                    
                    if group_key not in master_sku_pdfs:
                        master_sku_pdfs[group_key] = fitz.open()
                    
                    # Crop & Rotate Magic
                    rect = page.rect
                    page.set_cropbox(fitz.Rect(rect.width * 0.30, rect.height * 0.03, rect.width * 0.70, rect.height * 0.46))
                    page.set_rotation(0)
                    master_sku_pdfs[group_key].insert_pdf(doc, from_page=page_num, to_page=page_num)
                    
                    page.set_cropbox(fitz.Rect(0, rect.height * 0.46, rect.width, rect.height * 0.92))
                    page.set_rotation(90)
                    master_sku_pdfs[group_key].insert_pdf(doc, from_page=page_num, to_page=page_num)

            # --- SORTING (SKU phir Packet size ke hisaab se) ---
            sorted_skus = sorted(master_sku_pdfs.items(), key=lambda x: len(x[1]), reverse=True)

            # --- GRAND TOTAL BANNER (Packets & Items) ---
            total_packets = sum(len(pdf) // 2 for pdf in master_sku_pdfs.values())
            total_items = sum((len(pdf) // 2) * key[1] for key, pdf in master_sku_pdfs.items())

            grand_total_html = f"""
            <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 25px; border-radius: 20px; text-align: center; margin-bottom: 35px; border: 2px solid #334155;">
                <h1 style="color: white; margin: 0; font-size: 2.2rem; font-weight: 900;">
                    📦 Total Packets to Pack: <span style="color: #38bdf8;">{total_packets}</span> 
                    <span style="color: #94a3b8; font-size: 1.8rem; margin: 0 15px;">|</span> 
                    🛒 Total Items Inside: <span style="color: #10b981;">{total_items}</span>
                </h1>
            </div>
            """
            st.markdown(grand_total_html, unsafe_allow_html=True)
            
            # --- UI CARDS RENDERING ---
            cols = st.columns(3)
            loop_counter = 0
            
            for (m_sku, item_qty), pdf_doc in sorted_skus:
                packet_count = len(pdf_doc) // 2
                prod_name = "Product Not Found"
                img_url = "https://via.placeholder.com/150?text=No+Photo"
                
                if m_sku in prod_df['SKU'].values:
                    p_row = prod_df[prod_df['SKU'] == m_sku].iloc[0]
                    prod_name = p_row['Product Name']
                    img_path = str(p_row.get('Product Image', ''))
                    
                    if img_path and img_path != 'nan' and app_id:
                        encoded_img = urllib.parse.quote(img_path)
                        img_url = f"https://www.appsheet.com/template/gettablefileurl?appName={app_id.strip()}&tableName=Products&fileName={encoded_img}"
                
                # Highlight Badges based on Quantity
                if item_qty > 1:
                    qty_badge = f"""<div style="background: #ef4444; color: white; padding: 6px 12px; border-radius: 8px; font-size: 14px; font-weight: 900; margin-top: 8px; display: inline-block; box-shadow: 0 2px 5px rgba(239, 68, 68, 0.4); animation: pulse 2s infinite;">
                    🚨 MULTIPLE QTY: PACK {item_qty} ITEMS
                    </div>"""
                    border_color = "#ef4444"
                else:
                    qty_badge = f"""<div style="background: #10b981; color: white; padding: 6px 12px; border-radius: 8px; font-size: 14px; font-weight: 900; margin-top: 8px; display: inline-block;">
                    ✅ SINGLE ITEM
                    </div>"""
                    border_color = "#e2e8f0"

                pdf_bytes = pdf_doc.write()
                b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                download_filename = f"{m_sku}_QTY_{item_qty}_Total_{packet_count}Orders.pdf"
                
                card_html = f"""
                <div style="background: white; border-radius: 20px; padding: 18px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); display: flex; flex-direction: column; gap: 15px; border: 3px solid {border_color}; margin-bottom: 25px;">
                    <div style="display: flex; align-items: center; gap: 15px;">
                        <div style="background: #f8fafc; padding: 4px; border-radius: 12px; border: 1px solid #e2e8f0; flex-shrink: 0; width: 88px; height: 88px; display: flex; justify-content: center; align-items: center;">
                            <img src="{img_url}" style="max-width: 80px; max-height: 80px; border-radius: 8px; object-fit: contain;">
                        </div>
                        <div style="flex-grow: 1;">
                            <h4 style="margin: 0 0 6px 0; font-size: 16px; color: #0f172a; font-weight: 900; line-height: 1.2;">{prod_name}</h4>
                            <span style="background: #1e293b; color: white; padding: 3px 8px; border-radius: 6px; font-size: 12px; font-weight: 800;">
                                {m_sku}
                            </span>
                            <br>
                            {qty_badge}
                        </div>
                    </div>
                    
                    <a href="data:application/pdf;base64,{b64_pdf}" download="{download_filename}" style="text-decoration: none;">
                        <div style="background: #3b82f6; color: white; padding: 12px; border-radius: 14px; text-align: center; font-weight: 900; font-size: 16px; display: flex; justify-content: center; align-items: center; gap: 12px;">
                            📥 DOWNLOAD LABELS 
                            <span style="background: white; color: #3b82f6; padding: 2px 14px; border-radius: 10px; font-size: 18px;">
                                {packet_count}
                            </span>
                        </div>
                    </a>
                </div>
                """
                with cols[loop_counter % 3]:
                    st.markdown(card_html, unsafe_allow_html=True)
                
                loop_counter += 1
                
        except Exception as e:
            st.error(f"❌ Error Processing PDFs: {e}")
