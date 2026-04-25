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

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuration")
mapping_url = st.sidebar.text_input("Mapping CSV Link (Tab 1)", value=DEFAULT_MAPPING_URL)
products_url = st.sidebar.text_input("Products CSV Link (Tab 2)", value=DEFAULT_PRODUCTS_URL)
app_id = st.sidebar.text_input("AppSheet App ID", value=DEFAULT_APP_ID)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh / Sync Data"):
    st.rerun()

# --- MAIN UI HEADER ---
st.title("📦 Celvia Smart Label WMS (Ultra Pro UI)")
st.markdown("<p style='color: #64748b; font-size: 16px; font-weight: bold;'>Upload PDFs to process, sort, and print.</p>", unsafe_allow_html=True)

# --- MULTIPLE PDF UPLOADER ---
uploaded_pdfs = st.file_uploader("📥 Upload Flipkart PDF(s) Here", type=["pdf"], accept_multiple_files=True)

if uploaded_pdfs:
    with st.spinner("Analyzing PDFs, Sorting by Quantity & Preparing Unified UI... 🚀"):
        try:
            map_df = pd.read_csv(mapping_url)
            prod_df = pd.read_csv(products_url)
            
            map_df['Flipkart_SKU'] = map_df['Flipkart_SKU'].astype(str).str.strip()
            prod_df['SKU'] = prod_df['SKU'].astype(str).str.strip()
            
            master_sku_grouped = {}
            
            # Smart PDF Aggregation & Quantity Regex
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

            # SORTING (Descending)
            sorted_master_skus = sorted(master_sku_grouped.items(), key=lambda x: sum(len(p)//2 for p in x[1].values()), reverse=True)

            # --- ORIGINAL GRAND TOTAL BANNER ---
            total_grand_orders = sum(sum(len(p)//2 for p in data.values()) for sku, data in master_sku_grouped.items())

            grand_total_html = f"""
<div style="background: linear-gradient(135deg, #5ab08e 0%, #755ab0 100%); padding: 25px; border-radius: 25px; text-align: center; box-shadow: 0 15px 35px rgba(255, 75, 43, 0.4); margin-top: 15px; margin-bottom: 40px; border: 3px solid rgba(255,255,255,0.3);">
<h1 style="color: white; margin: 0; font-size: 2.8rem; font-weight: 900; letter-spacing: 2px; text-transform: uppercase;">
🚀 Total Packets: 
<span style="background: white; color: #755ab0; padding: 5px 30px; border-radius: 20px; font-size: 3.5rem; margin-left: 20px; box-shadow: inset 0 5px 10px rgba(0,0,0,0.15);">
{total_grand_orders}
</span>
</h1>
</div>
"""         
            # .replace used to safely load HTML without markdown corruption
            st.markdown(grand_total_html.replace('\n', ''), unsafe_allow_html=True)
            
            # --- VIBRANT COLOR PALETTE (ORIGINAL) ---
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

                sku_total_orders = 0
                sku_total_pcs = 0
                total_sku_pdf = fitz.open()
                rows_html = ""

                # --- INNER ROWS FOR QUANTITIES ---
                for qty in sorted(qty_dict.keys()):
                    pdf_doc = qty_dict[qty]
                    order_count = len(pdf_doc) // 2
                    pcs_count = order_count * qty
                    sku_total_orders += order_count
                    sku_total_pcs += pcs_count
                    total_sku_pdf.insert_pdf(pdf_doc)
                    
                    # Auto Naming setup
                    if qty == 1: lbl = "Single"
                    elif qty == 2: lbl = "Double"
                    elif qty == 3: lbl = "Triple"
                    else: lbl = f"{qty}_Qty"
                        
                    file_name = f"{m_sku}_Labels_{lbl}_ord_{order_count}.pdf"
                    b64_pdf = base64.b64encode(pdf_doc.write()).decode('utf-8')
                    
                    # Frosted glass row (Transparent White), NO Black
                    row = f"""
<div style="display: flex; align-items: center; justify-content: space-between; background: rgba(255,255,255,0.4); padding: 8px 12px; border-radius: 10px; margin-bottom: 8px;">
<span style="font-size: 14px; font-weight: 800; color: #0f172a;">{lbl}: {order_count} ord, {pcs_count} pcs</span>
<a href="data:application/pdf;base64,{b64_pdf}" download="{file_name}" style="text-decoration: none;">
<div style="background: rgba(255,255,255,0.9); color: #0f172a; padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 900; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">📥 PDF</div>
</a>
</div>
"""
                    rows_html += row

                total_file_name = f"{m_sku}_Labels_TOTAL_ord_{sku_total_orders}.pdf"
                total_b64_pdf = base64.b64encode(total_sku_pdf.write()).decode('utf-8')

                # --- UNIFIED CARD HTML (EVERYTHING INSIDE ONE DIV) ---
                card_html = f"""
<div style="background: {card_bg}; padding: 18px; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.12); display: flex; flex-direction: column; gap: 15px; border: 2px solid rgba(255,255,255,0.6); margin-bottom: 25px;">
<div style="display: flex; align-items: center; gap: 15px; background: rgba(255,255,255,0.6); padding: 12px; border-radius: 15px;">
<div style="background: white; padding: 4px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); flex-shrink: 0; width: 75px; height: 75px; display: flex; justify-content: center; align-items: center;">
<img src="{img_url}" style="max-width: 65px; max-height: 65px; border-radius: 8px; object-fit: contain;">
</div>
<div style="flex-grow: 1;">
<h4 style="margin: 0 0 6px 0; font-size: 16px; color: #0f172a; font-weight: 900; line-height: 1.2;">{prod_name[:40]}</h4>
<span style="background: rgba(255,255,255,0.8); color: #0f172a; padding: 4px 10px; border-radius: 8px; font-size: 11px; font-weight: 900; border: 1px solid rgba(0,0,0,0.1);">
{m_sku}
</span>
</div>
</div>
<div>
{rows_html}
</div>
<hr style="margin: 0; border: none; border-top: 1.5px dashed rgba(0,0,0,0.2);">
<div style="text-align: center; font-size: 15px; font-weight: 900; color: #0f172a; margin-bottom: 5px;">
Total: {sku_total_orders} ord, {sku_total_pcs} pcs
</div>
<a href="data:application/pdf;base64,{total_b64_pdf}" download="{total_file_name}" style="text-decoration: none;">
<div style="background: rgba(255,255,255,0.95); color: #0f172a; padding: 12px; border-radius: 14px; text-align: center; font-weight: 900; font-size: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
📥 DOWNLOAD ALL
</div>
</a>
</div>
"""
                with cols[loop_counter % 3]:
                    # CRITICAL: .replace('\n', '') totally disables Streamlit's base64 code spillage bug!
                    st.markdown(card_html.replace('\n', ''), unsafe_allow_html=True)
                
                loop_counter += 1
                
        except Exception as e:
            st.error(f"❌ Error Processing PDFs: {e}")
