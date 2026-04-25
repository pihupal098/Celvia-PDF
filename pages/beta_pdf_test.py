import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import io
import urllib.parse
import base64
import re

st.set_page_config(page_title="Celvia Smart Print Portal", layout="wide", page_icon="📦")

# 👇 DEFAULTS (PRE-FILLED DATA) 👇
DEFAULT_MAPPING_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=158825893&single=true&output=csv"
DEFAULT_PRODUCTS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=0&single=true&output=csv"
DEFAULT_APP_ID = "Untitledspreadsheet-306094028"

st.sidebar.header("⚙️ Configuration")
mapping_url = st.sidebar.text_input("Mapping CSV Link", value=DEFAULT_MAPPING_URL)
products_url = st.sidebar.text_input("Products CSV Link", value=DEFAULT_PRODUCTS_URL)
app_id = st.sidebar.text_input("AppSheet App ID", value=DEFAULT_APP_ID)

if st.sidebar.button("🔄 Refresh / Sync Data"):
    st.rerun()

st.title("📦 Celvia Smart Label WMS (Ultra Pro UI)")
st.markdown("<p style='color: #64748b; font-size: 16px; font-weight: bold;'>Upload PDFs -> Group by SKU -> Auto-Sort by Quantity -> Print Safely.</p>", unsafe_allow_html=True)

uploaded_pdfs = st.file_uploader("📥 Upload Flipkart PDF(s) Here", type=["pdf"], accept_multiple_files=True)

if uploaded_pdfs:
    with st.spinner("Analyzing PDFs, Grouping by Master SKU & Quantities... 🚀"):
        try:
            map_df = pd.read_csv(mapping_url)
            prod_df = pd.read_csv(products_url)
            
            map_df['Flipkart_SKU'] = map_df['Flipkart_SKU'].astype(str).str.strip()
            prod_df['SKU'] = prod_df['SKU'].astype(str).str.strip()
            
            # Data Structure: { "Master_SKU": { 1: [PDF_DOC], 2: [PDF_DOC], 3: [PDF_DOC] } }
            master_sku_grouped = {}
            
            for uploaded_file in uploaded_pdfs:
                doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    text = page.get_text()
                    
                    found_master_sku = "Unmapped_SKU"
                    for index, row in map_df.iterrows():
                        if row['Flipkart_SKU'] in text:
                            found_master_sku = row['Master_SKU']
                            break
                    
                    item_qty = 1 
                    qty_match = re.search(r'(?i)Total\s+Qty\s*:\s*(\d+)', text)
                    if not qty_match:
                        qty_match = re.search(r'(?i)(?:Quantity|Qty)\s*:\s*(\d+)', text)
                    if qty_match:
                        item_qty = int(qty_match.group(1))
                    
                    if found_master_sku not in master_sku_grouped:
                        master_sku_grouped[found_master_sku] = {}
                        
                    if item_qty not in master_sku_grouped[found_master_sku]:
                        master_sku_grouped[found_master_sku][item_qty] = fitz.open()
                    
                    rect = page.rect
                    page.set_cropbox(fitz.Rect(rect.width * 0.30, rect.height * 0.03, rect.width * 0.70, rect.height * 0.46))
                    page.set_rotation(0)
                    master_sku_grouped[found_master_sku][item_qty].insert_pdf(doc, from_page=page_num, to_page=page_num)
                    
                    page.set_cropbox(fitz.Rect(0, rect.height * 0.46, rect.width, rect.height * 0.92))
                    page.set_rotation(90)
                    master_sku_grouped[found_master_sku][item_qty].insert_pdf(doc, from_page=page_num, to_page=page_num)

            # Sort SKUs by total orders (Descending)
            def get_total_orders_for_sku(sku_data):
                return sum(len(pdf) // 2 for pdf in sku_data.values())
            
            sorted_master_skus = sorted(master_sku_grouped.items(), key=lambda x: get_total_orders_for_sku(x[1]), reverse=True)

            # Grand Total Banner
            grand_total_orders = sum(get_total_orders_for_sku(data) for sku, data in master_sku_grouped.items())
            grand_total_items = sum( sum((len(pdf)//2)*qty for qty, pdf in data.items()) for sku, data in master_sku_grouped.items())

            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 25px; border-radius: 20px; text-align: center; margin-bottom: 35px; border: 2px solid #334155;">
                <h1 style="color: white; margin: 0; font-size: 2.2rem; font-weight: 900;">
                    📦 Total Packets: <span style="color: #38bdf8;">{grand_total_orders}</span> 
                    <span style="color: #94a3b8; font-size: 1.8rem; margin: 0 15px;">|</span> 
                    🛒 Total Items Inside: <span style="color: #10b981;">{grand_total_items}</span>
                </h1>
            </div>
            """, unsafe_allow_html=True)
            
            # Background colors for cards
            bg_gradients = [
                "linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%)", 
                "linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)", 
                "linear-gradient(135deg, #d4fc79 0%, #96e6a1 100%)", 
                "linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%)", 
                "linear-gradient(135deg, #fbc2eb 0%, #a6c1ee 100%)", 
                "linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%)"  
            ]

            cols = st.columns(3)
            loop_counter = 0
            
            # Render One Master Card per SKU
            for m_sku, qty_dict in sorted_master_skus:
                prod_name = "Product Not Found"
                img_url = "https://via.placeholder.com/150?text=No+Photo"
                card_bg = bg_gradients[loop_counter % len(bg_gradients)]
                
                if m_sku in prod_df['SKU'].values:
                    p_row = prod_df[prod_df['SKU'] == m_sku].iloc[0]
                    prod_name = p_row['Product Name']
                    img_path = str(p_row.get('Product Image', ''))
                    
                    if img_path and img_path != 'nan' and app_id:
                        encoded_img = urllib.parse.quote(img_path)
                        img_url = f"https://www.appsheet.com/template/gettablefileurl?appName={app_id.strip()}&tableName=Products&fileName={encoded_img}"
                
                # --- Build the Nested Download Links HTML ---
                download_links_html = ""
                sku_total_orders = 0
                sku_total_pcs = 0
                
                # Sort keys so Qty 1 comes first, then 2, then 3
                for qty in sorted(qty_dict.keys()):
                    pdf_doc = qty_dict[qty]
                    order_count = len(pdf_doc) // 2
                    pcs_count = order_count * qty
                    
                    sku_total_orders += order_count
                    sku_total_pcs += pcs_count
                    
                    pdf_bytes = pdf_doc.write()
                    b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                    download_filename = f"{m_sku}_QTY_{qty}_{order_count}Orders.pdf"
                    
                    # Label changes based on Qty
                    if qty == 1:
                        qty_label = "Single item"
                        btn_color = "#3b82f6" # Blue
                    elif qty == 2:
                        qty_label = "Double item"
                        btn_color = "#f59e0b" # Orange
                    elif qty == 3:
                        qty_label = "Triple item"
                        btn_color = "#ef4444" # Red
                    else:
                        qty_label = f"{qty} Items"
                        btn_color = "#8b5cf6" # Purple
                        
                    download_links_html += f"""
                    <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.6); padding: 8px 12px; border-radius: 10px; margin-bottom: 8px;">
                        <div style="font-size: 13px; font-weight: 700; color: #334155;">
                            {qty_label}: {order_count} order, pcs: {pcs_count}
                        </div>
                        <a href="data:application/pdf;base64,{b64_pdf}" download="{download_filename}" style="text-decoration: none;">
                            <div style="background: {btn_color}; color: white; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 800; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                📥 PDF
                            </div>
                        </a>
                    </div>
                    """
                
                # Total Row for the SKU
                download_links_html += f"""
                <div style="display: flex; justify-content: space-between; align-items: center; background: #1e293b; padding: 8px 12px; border-radius: 10px; margin-top: 10px;">
                    <div style="font-size: 14px; font-weight: 800; color: white;">
                        Total: {sku_total_orders} order, pcs: {sku_total_pcs}
                    </div>
                </div>
                """
                
                # Master Card HTML Assembly
                card_html = f"""
                <div style="background: {card_bg}; border-radius: 20px; padding: 18px; box-shadow: 0 10px 25px rgba(0,0,0,0.12); display: flex; flex-direction: column; gap: 15px; border: 2px solid rgba(255,255,255,0.6); margin-bottom: 25px;">
                    <div style="display: flex; align-items: center; gap: 15px; background: rgba(255,255,255,0.7); padding: 12px; border-radius: 15px; backdrop-filter: blur(5px);">
                        <div style="background: white; padding: 4px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); flex-shrink: 0; width: 88px; height: 88px; display: flex; justify-content: center; align-items: center;">
                            <img src="{img_url}" style="max-width: 80px; max-height: 80px; border-radius: 8px; object-fit: contain;">
                        </div>
                        <div style="flex-grow: 1;">
                            <h4 style="margin: 0 0 6px 0; font-size: 15px; color: #0f172a; font-weight: 900; line-height: 1.2;">{prod_name}</h4>
                            <span style="background: #1e293b; color: white; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 800;">
                                {m_sku}
                            </span>
                        </div>
                    </div>
                    
                    <div style="display: flex; flex-direction: column;">
                        {download_links_html}
                    </div>
                </div>
                """
                
                with cols[loop_counter % 3]:
                    st.markdown(card_html, unsafe_allow_html=True)
                
                loop_counter += 1
                
        except Exception as e:
            st.error(f"❌ Error Processing PDFs: {e}")
