import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import io
import urllib.parse
import base64
import re

st.set_page_config(page_title="Celvia Smart Print Portal", layout="wide", page_icon="📦")

# Helper function to create clean download links
def get_pdf_download_link(pdf_doc, filename, label, btn_color="#3b82f6"):
    pdf_bytes = pdf_doc.write()
    b64 = base64.b64encode(pdf_bytes).decode()
    return f'''
    <a href="data:application/pdf;base64,{b64}" download="{filename}" style="text-decoration: none;">
        <div style="background: {btn_color}; color: white; padding: 5px 12px; border-radius: 8px; font-size: 12px; font-weight: 800; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            {label}
        </div>
    </a>
    '''

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
uploaded_pdfs = st.file_uploader("📥 Upload Flipkart PDF(s)", type=["pdf"], accept_multiple_files=True)

if uploaded_pdfs:
    with st.spinner("Processing & Merging PDFs... 🚀"):
        try:
            map_df = pd.read_csv(mapping_url)
            prod_df = pd.read_csv(products_url)
            
            map_df['Flipkart_SKU'] = map_df['Flipkart_SKU'].astype(str).str.strip()
            prod_df['SKU'] = prod_df['SKU'].astype(str).str.strip()
            
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
                    
                    qty_match = re.search(r'(?i)Total\s+Qty\s*:\s*(\d+)', text)
                    if not qty_match: qty_match = re.search(r'(?i)(?:Quantity|Qty)\s*:\s*(\d+)', text)
                    item_qty = int(qty_match.group(1)) if qty_match else 1
                    
                    if found_master_sku not in master_sku_grouped:
                        master_sku_grouped[found_master_sku] = {}
                    if item_qty not in master_sku_grouped[found_master_sku]:
                        master_sku_grouped[found_master_sku][item_qty] = fitz.open()
                    
                    rect = page.rect
                    # Crop 1: Label
                    page.set_cropbox(fitz.Rect(rect.width * 0.30, rect.height * 0.03, rect.width * 0.70, rect.height * 0.46))
                    master_sku_grouped[found_master_sku][item_qty].insert_pdf(doc, from_page=page_num, to_page=page_num)
                    # Crop 2: Product Info
                    page.set_cropbox(fitz.Rect(0, rect.height * 0.46, rect.width, rect.height * 0.92))
                    page.set_rotation(90)
                    master_sku_grouped[found_master_sku][item_qty].insert_pdf(doc, from_page=page_num, to_page=page_num)

            # Sort SKUs by total orders
            sorted_master_skus = sorted(master_sku_grouped.items(), key=lambda x: sum(len(p)//2 for p in x[1].values()), reverse=True)

            cols = st.columns(3)
            bg_gradients = ["linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%)", "linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)", "linear-gradient(135deg, #d4fc79 0%, #96e6a1 100%)"]

            for idx, (m_sku, qty_dict) in enumerate(sorted_master_skus):
                prod_name = prod_df[prod_df['SKU'] == m_sku].iloc[0]['Product Name'] if m_sku in prod_df['SKU'].values else "Unknown SKU"
                img_path = str(prod_df[prod_df['SKU'] == m_sku].iloc[0].get('Product Image', '')) if m_sku in prod_df['SKU'].values else ""
                img_url = f"https://www.appsheet.com/template/gettablefileurl?appName={app_id.strip()}&tableName=Products&fileName={urllib.parse.quote(img_path)}" if img_path and img_path != 'nan' else "https://via.placeholder.com/150"

                sku_total_orders, sku_total_pcs = 0, 0
                links_html = ""
                total_sku_pdf = fitz.open() # Master PDF for this SKU

                for qty in sorted(qty_dict.keys()):
                    pdf_doc = qty_dict[qty]
                    order_count = len(pdf_doc) // 2
                    sku_total_orders += order_count
                    sku_total_pcs += (order_count * qty)
                    total_sku_pdf.insert_pdf(pdf_doc) # Add to master
                    
                    label = "Single" if qty == 1 else "Double" if qty == 2 else "Triple" if qty == 3 else f"{qty} Pcs"
                    btn_color = "#3b82f6" if qty == 1 else "#f59e0b" if qty == 2 else "#ef4444"
                    
                    links_html += f'''
                    <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.6); padding: 8px; border-radius: 10px; margin-bottom: 5px;">
                        <span style="font-size: 12px; font-weight: 700;">{label}: {order_count} ord, {order_count*qty} pcs</span>
                        {get_pdf_download_link(pdf_doc, f"{m_sku}_Qty{qty}.pdf", "📥 PDF", btn_color)}
                    </div>'''

                # Add Total Download Button at the end
                total_link = get_pdf_download_link(total_sku_pdf, f"TOTAL_{m_sku}.pdf", f"📥 DOWNLOAD ALL {sku_total_orders} ORDERS", "#1e293b")

                card_html = f'''
                <div style="background: {bg_gradients[idx % 3]}; border-radius: 20px; padding: 15px; border: 2px solid rgba(255,255,255,0.5); margin-bottom: 20px;">
                    <div style="display: flex; align-items: center; gap: 10px; background: rgba(255,255,255,0.8); padding: 10px; border-radius: 15px; margin-bottom: 10px;">
                        <img src="{img_url}" style="width: 60px; height: 60px; object-fit: contain; border-radius: 8px;">
                        <div>
                            <div style="font-size: 13px; font-weight: 900; line-height: 1.1;">{prod_name[:30]}...</div>
                            <div style="font-size: 11px; background: #1e293b; color: white; display: inline-block; padding: 2px 6px; border-radius: 4px; margin-top: 4px;">{m_sku}</div>
                        </div>
                    </div>
                    {links_html}
                    <div style="background: #1e293b; color: white; padding: 8px; border-radius: 10px; margin-top: 5px; font-size: 13px; font-weight: 800; text-align: center;">
                        Total: {sku_total_orders} ord, {sku_total_pcs} pcs
                    </div>
                    <div style="margin-top: 10px;">{total_link}</div>
                </div>
                '''
                with cols[idx % 3]:
                    st.markdown(card_html, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Error: {e}")
