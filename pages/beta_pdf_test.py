import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import urllib.parse
import base64
import re

st.set_page_config(page_title="Celvia Smart Print Portal", layout="wide", page_icon="📦")

# --- DEFAULTS ---
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

uploaded_pdfs = st.file_uploader("📥 Upload Flipkart PDF(s)", type=["pdf"], accept_multiple_files=True)

if uploaded_pdfs:
    with st.spinner("Processing, Grouping & Designing Perfect Cards... 🚀"):
        try:
            map_df = pd.read_csv(mapping_url)
            prod_df = pd.read_csv(products_url)
            
            map_df['Flipkart_SKU'] = map_df['Flipkart_SKU'].astype(str).str.strip()
            prod_df['SKU'] = prod_df['SKU'].astype(str).str.strip()
            
            master_sku_grouped = {}
            
            # --- PDF PROCESSING & GROUPING ---
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
                    
                    qty_match = re.search(r'(?i)Total\s+Qty\s*:\s*(\d+)', text)
                    if not qty_match: 
                        qty_match = re.search(r'(?i)(?:Quantity|Qty)\s*:\s*(\d+)', text)
                    item_qty = int(qty_match.group(1)) if qty_match else 1
                    
                    if found_master_sku not in master_sku_grouped:
                        master_sku_grouped[found_master_sku] = {}
                    if item_qty not in master_sku_grouped[found_master_sku]:
                        master_sku_grouped[found_master_sku][item_qty] = fitz.open()
                    
                    rect = page.rect
                    # Crop 1: Label
                    page.set_cropbox(fitz.Rect(rect.width * 0.30, rect.height * 0.03, rect.width * 0.70, rect.height * 0.46))
                    page.set_rotation(0)
                    master_sku_grouped[found_master_sku][item_qty].insert_pdf(doc, from_page=page_num, to_page=page_num)
                    
                    # Crop 2: Product Info
                    page.set_cropbox(fitz.Rect(0, rect.height * 0.46, rect.width, rect.height * 0.92))
                    page.set_rotation(90)
                    master_sku_grouped[found_master_sku][item_qty].insert_pdf(doc, from_page=page_num, to_page=page_num)

            # --- SORTING ---
            sorted_master_skus = sorted(master_sku_grouped.items(), key=lambda x: sum(len(p)//2 for p in x[1].values()), reverse=True)

            # --- GRAND TOTAL BANNER ---
            grand_total_orders = sum(sum(len(p)//2 for p in data.values()) for sku, data in master_sku_grouped.items())
            grand_total_items = sum( sum((len(pdf)//2)*qty for qty, pdf in data.items()) for sku, data in master_sku_grouped.items())

            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 25px; border-radius: 20px; text-align: center; margin-bottom: 35px; box-shadow: 0 10px 30px rgba(0,0,0,0.15);">
                <h1 style="color: white; margin: 0; font-size: 2.2rem; font-weight: 900; letter-spacing: 1px;">
                    📦 Total Packets: <span style="color: #38bdf8; background: rgba(56, 189, 248, 0.15); padding: 5px 18px; border-radius: 12px;">{grand_total_orders}</span> 
                    <span style="color: #475569; font-size: 1.8rem; margin: 0 20px;">|</span> 
                    🛒 Total Items Inside: <span style="color: #10b981; background: rgba(16, 185, 129, 0.15); padding: 5px 18px; border-radius: 12px;">{grand_total_items}</span>
                </h1>
            </div>
            """, unsafe_allow_html=True)

            # --- THE JHAMAAJHAM UNIFIED UI GRID ---
            cols = st.columns(3)
            bg_gradients = [
                "linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%)", 
                "linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)", 
                "linear-gradient(135deg, #d4fc79 0%, #96e6a1 100%)", 
                "linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%)", 
                "linear-gradient(135deg, #fbc2eb 0%, #a6c1ee 100%)", 
                "linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%)"
            ]

            for idx, (m_sku, qty_dict) in enumerate(sorted_master_skus):
                prod_name = prod_df[prod_df['SKU'] == m_sku].iloc[0]['Product Name'] if m_sku in prod_df['SKU'].values else "Unknown SKU"
                img_path = str(prod_df[prod_df['SKU'] == m_sku].iloc[0].get('Product Image', '')) if m_sku in prod_df['SKU'].values else ""
                img_url = f"https://www.appsheet.com/template/gettablefileurl?appName={app_id.strip()}&tableName=Products&fileName={urllib.parse.quote(img_path)}" if img_path and img_path != 'nan' else "https://via.placeholder.com/150"
                card_bg = bg_gradients[idx % len(bg_gradients)]

                sku_total_orders, sku_total_pcs = 0, 0
                total_sku_pdf = fitz.open()

                # Build Rows HTML for each Quantity inside the loop
                rows_html = ""
                for qty in sorted(qty_dict.keys()):
                    pdf_doc = qty_dict[qty]
                    order_count = len(pdf_doc) // 2
                    pcs_count = order_count * qty
                    
                    sku_total_orders += order_count
                    sku_total_pcs += pcs_count
                    total_sku_pdf.insert_pdf(pdf_doc)
                    
                    if qty == 1: lbl = "Single"
                    elif qty == 2: lbl = "Double"
                    elif qty == 3: lbl = "Triple"
                    else: lbl = f"{qty}_Qty"
                        
                    file_name = f"{m_sku}_Labels_{lbl}_ord_{order_count}.pdf"
                    
                    # Encode Base64 safely without newlines
                    pdf_bytes = pdf_doc.write()
                    b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                    
                    rows_html += f"""
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 5px 0;">
                        <div style="font-size: 14px; font-weight: 900; color: #0f172a;">
                            {lbl}: {order_count} ord, {pcs_count} pcs
                        </div>
                        <a href="data:application/pdf;base64,{b64_pdf}" download="{file_name}" style="text-decoration: none;">
                            <div style="background: rgba(255,255,255,0.95); color: #0f172a; padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 900; box-shadow: 0 4px 6px rgba(0,0,0,0.1); border: 1px solid rgba(0,0,0,0.05); transition: transform 0.2s;">
                                📥 Download PDF
                            </div>
                        </a>
                    </div>
                    """

                # Encode Base64 for the Grand Total Button
                total_file_name = f"{m_sku}_Labels_TOTAL_ord_{sku_total_orders}.pdf"
                total_pdf_bytes = total_sku_pdf.write()
                total_b64_pdf = base64.b64encode(total_pdf_bytes).decode('utf-8')

                # --- THE SINGLE UNIFIED CARD HTML ---
                card_html = f"""
                <div style="background: {card_bg}; padding: 20px; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border: 2px solid rgba(255,255,255,0.7); display: flex; flex-direction: column; gap: 15px; margin-bottom: 25px;">
                    
                    <div style="display: flex; align-items: center; gap: 15px;">
                        <div style="background: white; padding: 6px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); flex-shrink: 0;">
                            <img src="{img_url}" style="width: 70px; height: 70px; object-fit: contain; border-radius: 8px;">
                        </div>
                        <div style="flex-grow: 1;">
                            <div style="font-size: 16px; font-weight: 900; line-height: 1.2; color: #0f172a; margin-bottom: 6px;">{prod_name[:35]}...</div>
                            <div style="font-size: 12px; background: rgba(255,255,255,0.6); color: #0f172a; display: inline-block; padding: 4px 12px; border-radius: 20px; font-weight: 900; border: 1px solid rgba(255,255,255,0.9); letter-spacing: 0.5px;">
                                {m_sku}
                            </div>
                        </div>
                    </div>

                    <hr style="margin: 0; border: none; border-top: 2px solid rgba(255,255,255,0.6);">

                    <div style="display: flex; flex-direction: column; gap: 8px;">
                        {rows_html}
                    </div>

                    <hr style="margin: 0; border: none; border-top: 2px dashed rgba(255,255,255,0.7);">

                    <div style="display: flex; flex-direction: column; gap: 10px;">
                        <a href="data:application/pdf;base64,{total_b64_pdf}" download="{total_file_name}" style="text-decoration: none; width: 100%;">
                            <div style="background: rgba(255,255,255,0.95); color: #0f172a; text-align: center; padding: 12px; border-radius: 12px; font-size: 16px; font-weight: 900; box-shadow: 0 6px 12px rgba(0,0,0,0.15); border: 1px solid rgba(0,0,0,0.05); width: 100%;">
                                📥 DOWNLOAD ALL
                            </div>
                        </a>
                        <div style="text-align: center; font-size: 17px; font-weight: 900; color: #0f172a;">
                            Total: {sku_total_orders} ord, {sku_total_pcs} pcs
                        </div>
                    </div>

                </div>
                """
                
                with cols[idx % 3]:
                    st.markdown(card_html, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"❌ Execution Error: {e}")
