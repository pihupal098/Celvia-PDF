import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import urllib.parse
import re

st.set_page_config(page_title="Celvia Smart Print Portal", layout="wide", page_icon="📦")

# --- DEFAULTS ---
DEFAULT_MAPPING_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=158825893&single=true&output=csv"
DEFAULT_PRODUCTS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=0&single=true&output=csv"
DEFAULT_APP_ID = "Untitledspreadsheet-306094028"

# --- SIDEBAR ---
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
                    
                    # Regex logic for "Total Qty: X"
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
            <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 25px; border-radius: 20px; text-align: center; margin-bottom: 35px; border: 2px solid #334155; box-shadow: 0 10px 20px rgba(0,0,0,0.15);">
                <h1 style="color: white; margin: 0; font-size: 2.2rem; font-weight: 900;">
                    📦 Total Packets: <span style="color: #38bdf8; background: rgba(56, 189, 248, 0.1); padding: 5px 15px; border-radius: 10px;">{grand_total_orders}</span> 
                    <span style="color: #475569; font-size: 1.8rem; margin: 0 15px;">|</span> 
                    🛒 Total Items Inside: <span style="color: #10b981; background: rgba(16, 185, 129, 0.1); padding: 5px 15px; border-radius: 10px;">{grand_total_items}</span>
                </h1>
            </div>
            """, unsafe_allow_html=True)

            # --- UI GRID ---
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
                with cols[idx % 3]:
                    # Create the physical card container
                    with st.container(border=True):
                        prod_name = prod_df[prod_df['SKU'] == m_sku].iloc[0]['Product Name'] if m_sku in prod_df['SKU'].values else "Unknown SKU"
                        img_path = str(prod_df[prod_df['SKU'] == m_sku].iloc[0].get('Product Image', '')) if m_sku in prod_df['SKU'].values else ""
                        img_url = f"https://www.appsheet.com/template/gettablefileurl?appName={app_id.strip()}&tableName=Products&fileName={urllib.parse.quote(img_path)}" if img_path and img_path != 'nan' else "https://via.placeholder.com/150"
                        card_bg = bg_gradients[idx % len(bg_gradients)]

                        # Header HTML (Image + SKU) 
                        st.markdown(f'''
                        <div style="background: {card_bg}; padding: 15px; border-radius: 12px; margin-bottom: 15px; border: 1px solid rgba(255,255,255,0.6); box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                            <div style="display: flex; align-items: center; gap: 12px; background: rgba(255,255,255,0.85); padding: 12px; border-radius: 10px;">
                                <div style="background: white; padding: 4px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                                    <img src="{img_url}" style="width: 65px; height: 65px; object-fit: contain; border-radius: 6px;">
                                </div>
                                <div style="flex-grow: 1;">
                                    <div style="font-size: 14px; font-weight: 900; line-height: 1.2; color: #0f172a; margin-bottom: 4px;">{prod_name[:35]}...</div>
                                    <div style="font-size: 11px; background: #1e293b; color: white; display: inline-block; padding: 3px 8px; border-radius: 6px; font-weight: bold; letter-spacing: 0.5px;">{m_sku}</div>
                                </div>
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)

                        sku_total_orders, sku_total_pcs = 0, 0
                        total_sku_pdf = fitz.open()

                        # --- INLINE ROWS FOR EACH QUANTITY ---
                        for qty in sorted(qty_dict.keys()):
                            pdf_doc = qty_dict[qty]
                            order_count = len(pdf_doc) // 2
                            pcs_count = order_count * qty
                            
                            sku_total_orders += order_count
                            sku_total_pcs += pcs_count
                            total_sku_pdf.insert_pdf(pdf_doc)
                            
                            # Auto-Naming Logic
                            if qty == 1:
                                lbl = "Single"
                            elif qty == 2:
                                lbl = "Double"
                            elif qty == 3:
                                lbl = "Triple"
                            else:
                                lbl = f"{qty}_Qty"
                                
                            file_name = f"{m_sku}_Labels_{lbl}_ord_{order_count}.pdf"
                            
                            # Using Streamlit Columns to make Text and Button INLINE
                            col1, col2 = st.columns([0.6, 0.4], vertical_alignment="center")
                            
                            with col1:
                                st.markdown(f"<div style='font-size:13px; font-weight:800; color: #334155; margin-top: 8px;'>{lbl}: {order_count} ord, {pcs_count} pcs</div>", unsafe_allow_html=True)
                            
                            with col2:
                                st.download_button(
                                    label="📥 PDF", 
                                    data=pdf_doc.write(), 
                                    file_name=file_name, 
                                    mime="application/pdf", 
                                    key=f"btn_{m_sku}_{qty}",
                                    use_container_width=True
                                )

                        st.markdown("<hr style='margin: 5px 0; border-color: #e2e8f0;'>", unsafe_allow_html=True)

                        # --- FOOTER TOTAL & MASTER DOWNLOAD ---
                        st.markdown(f"""
                        <div style='background: #f1f5f9; padding: 6px; border-radius: 8px; text-align:center; font-size: 13px; font-weight: 800; color: #0f172a; margin-bottom: 10px; border: 1px solid #cbd5e1;'>
                            Total: {sku_total_orders} ord, {sku_total_pcs} pcs
                        </div>
                        """, unsafe_allow_html=True)
                        
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

        except Exception as e:
            st.error(f"❌ Execution Error: {e}")
