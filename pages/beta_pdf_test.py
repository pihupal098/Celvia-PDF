import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import io
import urllib.parse
import base64
import re

st.set_page_config(page_title="Celvia Smart Print Portal", layout="wide", page_icon="📦")

# --- 💎 THE CRYSTAL/MIRROR GLASSMORPHISM CSS 💎 ---
# Ye CSS saare tukdo ko hata kar ek seamless crystal glass look dega
st.markdown("""
<style>
/* Master Crystal Card Styling */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.7) 0%, rgba(240, 248, 255, 0.2) 100%) !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    border: 1px solid rgba(255, 255, 255, 0.9) !important;
    border-radius: 24px !important;
    box-shadow: 0 10px 30px rgba(31, 38, 135, 0.1), inset 0 1px 2px rgba(255, 255, 255, 0.6) !important;
    padding: 18px !important;
    transition: all 0.3s ease !important;
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    transform: translateY(-4px) !important;
    box-shadow: 0 15px 35px rgba(31, 38, 135, 0.15), inset 0 1px 2px rgba(255, 255, 255, 0.9) !important;
}

/* Native Download Buttons - Premium Glass Style */
button[data-testid="baseButton-secondary"] {
    background: rgba(255, 255, 255, 0.8) !important;
    color: #0f172a !important;
    border: 1px solid rgba(255, 255, 255, 0.9) !important;
    font-weight: 800 !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 10px rgba(0,0,0,0.05) !important;
}
button[data-testid="baseButton-secondary"]:hover {
    background: #ffffff !important;
    border: 1px solid #38bdf8 !important;
    color: #0369a1 !important;
    transform: translateY(-2px);
}

/* DOWNLOAD ALL Button - Solid Premium Dark */
button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important;
    color: #ffffff !important;
    font-weight: 900 !important;
    border-radius: 12px !important;
    border: none !important;
    box-shadow: 0 6px 15px rgba(15, 23, 42, 0.3) !important;
}
button[data-testid="baseButton-primary"]:hover {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important;
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.4) !important;
}

/* Customizing the native divider line */
hr {
    margin: 15px 0px !important;
    border-color: rgba(0,0,0,0.1) !important;
}
</style>
""", unsafe_allow_html=True)

# 👇 DEFAULTS 👇
DEFAULT_MAPPING_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=158825893&single=true&output=csv"
DEFAULT_PRODUCTS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=0&single=true&output=csv"
DEFAULT_APP_ID = "Untitledspreadsheet-306094028"

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuration")
mapping_url = st.sidebar.text_input("Mapping CSV Link (Tab 1)", value=DEFAULT_MAPPING_URL)
products_url = st.sidebar.text_input("Products CSV Link (Tab 2)", value=DEFAULT_PRODUCTS_URL)
app_id = st.sidebar.text_input("AppSheet App ID", value=DEFAULT_APP_ID)

if st.sidebar.button("🔄 Refresh / Sync Data"):
    st.rerun()

# --- MAIN UI HEADER ---
st.title("📦 Celvia Smart Label WMS (Ultra Pro UI)")
st.markdown("<p style='color: #64748b; font-size: 16px; font-weight: bold;'>Upload PDFs to process, sort, and print.</p>", unsafe_allow_html=True)

uploaded_pdfs = st.file_uploader("📥 Upload Flipkart PDF(s) Here", type=["pdf"], accept_multiple_files=True)

if uploaded_pdfs:
    with st.spinner("Analyzing PDFs & Building Crystal Cards... 🚀"):
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

            sorted_master_skus = sorted(master_sku_grouped.items(), key=lambda x: sum(len(p)//2 for p in x[1].values()), reverse=True)

            # --- ORIGINAL GRAND TOTAL BANNER ---
            total_grand_orders = sum(sum(len(p)//2 for p in data.values()) for sku, data in master_sku_grouped.items())
            total_grand_items = sum( sum((len(pdf)//2)*qty for qty, pdf in data.items()) for sku, data in master_sku_grouped.items())

            grand_total_html = f"""
            <div style="background: linear-gradient(135deg, #5ab08e 0%, #755ab0 100%); padding: 25px; border-radius: 20px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.15); margin-top: 15px; margin-bottom: 40px; border: 2px solid rgba(255,255,255,0.4);">
                <h1 style="color: white; margin: 0; font-size: 2.2rem; font-weight: 900; letter-spacing: 1px;">
                🚀 Total Packets: 
                <span style="background: white; color: #755ab0; padding: 4px 18px; border-radius: 12px; margin: 0 10px;">{total_grand_orders}</span>
                <span style="color: rgba(255,255,255,0.6); margin: 0 15px;">|</span>
                🛒 Items: 
                <span style="background: white; color: #5ab08e; padding: 4px 18px; border-radius: 12px; margin: 0 10px;">{total_grand_items}</span>
                </h1>
            </div>
            """
            st.markdown(grand_total_html, unsafe_allow_html=True)
            
            cols = st.columns(3)
            
            for idx, (m_sku, qty_dict) in enumerate(sorted_master_skus):
                with cols[idx % 3]:
                    # NATIVE CONTAINER - Picks up our Crystal Glass CSS automatically
                    with st.container(border=True):
                        
                        prod_name = prod_df[prod_df['SKU'] == m_sku].iloc[0]['Product Name'] if m_sku in prod_df['SKU'].values else "Unknown SKU"
                        img_path = str(prod_df[prod_df['SKU'] == m_sku].iloc[0].get('Product Image', '')) if m_sku in prod_df['SKU'].values else ""
                        img_url = f"https://www.appsheet.com/template/gettablefileurl?appName={app_id.strip()}&tableName=Products&fileName={urllib.parse.quote(img_path)}" if img_path and img_path != 'nan' else "https://via.placeholder.com/150"

                        # 1. Image and Title (No solid backgrounds, let the glass shine through)
                        st.markdown(f'''
                        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 10px;">
                            <div style="background: rgba(255,255,255,0.9); padding: 5px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08);">
                                <img src="{img_url}" style="width: 60px; height: 60px; object-fit: contain; border-radius: 8px;">
                            </div>
                            <div style="flex-grow: 1;">
                                <div style="font-size: 16px; font-weight: 900; line-height: 1.2; color: #0f172a; margin-bottom: 6px;">{prod_name[:35]}...</div>
                                <div style="font-size: 11px; background: rgba(15,23,42,0.06); color: #0f172a; display: inline-block; padding: 4px 12px; border-radius: 12px; font-weight: 900; border: 1px solid rgba(15,23,42,0.1); letter-spacing: 0.5px;">{m_sku}</div>
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)

                        sku_total_orders, sku_total_pcs = 0, 0
                        total_sku_pdf = fitz.open()

                        # 2. INLINE QUANTITY ROWS
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
                            
                            c1, c2 = st.columns([0.6, 0.4], vertical_alignment="center")
                            with c1:
                                st.markdown(f"<div style='font-size:14px; font-weight:800; color: #1e293b; margin-top: 8px;'>{lbl}: {order_count} ord, {pcs_count} pcs</div>", unsafe_allow_html=True)
                            with c2:
                                st.download_button(
                                    label="📥 Download PDF", 
                                    data=pdf_doc.write(), 
                                    file_name=file_name, 
                                    mime="application/pdf", 
                                    key=f"btn_{m_sku}_{qty}",
                                    use_container_width=True
                                )

                        st.divider()

                        # 3. FOOTER (DOWNLOAD ALL + TOTAL)
                        total_file_name = f"{m_sku}_Labels_TOTAL_ord_{sku_total_orders}.pdf"
                        
                        st.download_button(
                            label=f"📥 DOWNLOAD ALL", 
                            data=total_sku_pdf.write(), 
                            file_name=total_file_name, 
                            mime="application/pdf", 
                            use_container_width=True, 
                            type="primary", 
                            key=f"btn_all_{m_sku}"
                        )
                        
                        st.markdown(f"""
                        <div style='text-align:center; font-size: 16px; font-weight: 900; color: #ef4444; margin-top: 8px;'>
                            Total: {sku_total_orders} ord, {sku_total_pcs} pcs
                        </div>
                        """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"❌ Error: {e}")
