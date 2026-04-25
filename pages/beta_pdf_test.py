import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import io
import urllib.parse
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
    with st.spinner("Processing, Grouping & Securing PDFs... 🚀"):
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
                    
                    # Regex logic for finding "Total Qty: X"
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

            # --- GRAND TOTAL BANNER (RESTORED) ---
            grand_total_orders = sum(sum(len(p)//2 for p in data.values()) for sku, data in master_sku_grouped.items())
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

            # --- NATIVE STREAMLIT UI GRID ---
            cols = st.columns(3)

            for idx, (m_sku, qty_dict) in enumerate(sorted_master_skus):
                with cols[idx % 3]:
                    # Native Streamlit Container (100% crash proof)
                    with st.container(border=True):
                        prod_name = prod_df[prod_df['SKU'] == m_sku].iloc[0]['Product Name'] if m_sku in prod_df['SKU'].values else "Unknown SKU"
                        img_path = str(prod_df[prod_df['SKU'] == m_sku].iloc[0].get('Product Image', '')) if m_sku in prod_df['SKU'].values else ""
                        img_url = f"https://www.appsheet.com/template/gettablefileurl?appName={app_id.strip()}&tableName=Products&fileName={urllib.parse.quote(img_path)}" if img_path and img_path != 'nan' else "https://via.placeholder.com/150"

                        # Card Header HTML
                        st.markdown(f'''
                        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 15px;">
                            <img src="{img_url}" style="width: 60px; height: 60px; object-fit: contain; border-radius: 8px; border: 1px solid #cbd5e1;">
                            <div>
                                <div style="font-size: 14px; font-weight: 900; line-height: 1.2; color: #0f172a;">{prod_name[:35]}...</div>
                                <div style="font-size: 12px; background: #334155; color: white; display: inline-block; padding: 2px 6px; border-radius: 4px; margin-top: 4px;">{m_sku}</div>
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)

                        sku_total_orders, sku_total_pcs = 0, 0
                        total_sku_pdf = fitz.open()

                        # Lines for Qty 1, Qty 2, etc. (Native Buttons)
                        for qty in sorted(qty_dict.keys()):
                            pdf_doc = qty_dict[qty]
                            order_count = len(pdf_doc) // 2
                            sku_total_orders += order_count
                            sku_total_pcs += (order_count * qty)
                            total_sku_pdf.insert_pdf(pdf_doc)
                            
                            label = "Single" if qty == 1 else "Double" if qty == 2 else "Triple" if qty == 3 else f"{qty} Items"
                            
                            r1, r2 = st.columns([0.65, 0.35])
                            with r1:
                                st.markdown(f"<div style='font-size:13px; font-weight:700; margin-top:8px;'>{label}: {order_count} ord, {order_count*qty} pcs</div>", unsafe_allow_html=True)
                            with r2:
                                st.download_button(label="📥 PDF", data=pdf_doc.write(), file_name=f"{m_sku}_Qty{qty}.pdf", mime="application/pdf", key=f"btn_{m_sku}_{qty}")

                        st.markdown("<hr style='margin: 10px 0;'>", unsafe_allow_html=True)

                        # Footer Total & Master Download Button
                        st.markdown(f"<div style='text-align:center; font-size: 14px; font-weight: 800; color: #0f172a; margin-bottom: 8px;'>Total: {sku_total_orders} order, {sku_total_pcs} pcs</div>", unsafe_allow_html=True)
                        st.download_button(label=f"📥 DOWNLOAD ALL ({sku_total_orders})", data=total_sku_pdf.write(), file_name=f"TOTAL_{m_sku}.pdf", mime="application/pdf", use_container_width=True, type="primary", key=f"btn_all_{m_sku}")

        except Exception as e:
            st.error(f"Error: {e}")
