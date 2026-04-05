import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import io
import urllib.parse

st.set_page_config(page_title="Celvia Smart Print Portal", layout="wide", page_icon="📦")
st.title("📦 Celvia Smart Label WMS (Pro UI)")

# 👇 PERMANENT GOOGLE SHEET LINKS 👇
DEFAULT_MAPPING_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=158825893&single=true&output=csv"
DEFAULT_PRODUCTS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=0&single=true&output=csv"

# --- SIDEBAR SETTINGS ---
st.sidebar.header("⚙️ Settings")
mapping_url = st.sidebar.text_input("Mapping CSV Link", value=DEFAULT_MAPPING_URL)
products_url = st.sidebar.text_input("Products CSV Link", value=DEFAULT_PRODUCTS_URL)

st.sidebar.markdown("---")
st.sidebar.header("🖼️ Photo Configuration")
app_id = st.sidebar.text_input("AppSheet App ID", placeholder="e.g., CelviaWMS-1234567")

if st.sidebar.button("🔄 Sync Database"):
    st.rerun()

# --- MULTIPLE PDF UPLOADER ---
uploaded_pdfs = st.file_uploader("📥 Upload Multiple Flipkart PDFs", type=["pdf"], accept_multiple_files=True)

if uploaded_pdfs:
    with st.spinner("Analyzing all PDFs and Aggregating SKUs... 🚀"):
        try:
            map_df = pd.read_csv(mapping_url)
            prod_df = pd.read_csv(products_url)
            
            map_df['Flipkart_SKU'] = map_df['Flipkart_SKU'].astype(str).str.strip()
            prod_df['SKU'] = prod_df['SKU'].astype(str).str.strip()
            
            master_sku_pdfs = {}
            
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
                    
                    if found_master_sku not in master_sku_pdfs:
                        master_sku_pdfs[found_master_sku] = fitz.open()
                    
                    rect = page.rect
                    page.set_cropbox(fitz.Rect(rect.width * 0.30, rect.height * 0.03, rect.width * 0.70, rect.height * 0.46))
                    page.set_rotation(0)
                    master_sku_pdfs[found_master_sku].insert_pdf(doc, from_page=page_num, to_page=page_num)
                    
                    page.set_cropbox(fitz.Rect(0, rect.height * 0.46, rect.width, rect.height * 0.83))
                    page.set_rotation(90)
                    master_sku_pdfs[found_master_sku].insert_pdf(doc, from_page=page_num, to_page=page_num)

            # --- GRAND TOTAL CALCULATION ---
            # Har PDF mein 2 page (label+invoice) hain, isliye // 2
            total_grand_orders = sum(len(pdf) // 2 for pdf in master_sku_pdfs.values())

            # 💥 BIG CURVY COLORFUL FLOATING BANNER 💥
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); 
                        padding: 20px; 
                        border-radius: 25px; 
                        text-align: center; 
                        box-shadow: 0 10px 25px rgba(17, 153, 142, 0.4); 
                        margin-top: 10px;
                        margin-bottom: 35px;">
                <h1 style="color: white; margin: 0; font-size: 2.2rem; font-weight: 900; text-transform: uppercase;">
                    🚀 Total Packets To Dispatch: 
                    <span style="background: white; color: #11998e; padding: 5px 25px; border-radius: 20px; font-size: 3rem; margin-left: 15px; box-shadow: inset 0 3px 6px rgba(0,0,0,0.1);">
                        {total_grand_orders}
                    </span>
                </h1>
            </div>
            """, unsafe_allow_html=True)
            
            cols = st.columns(3)
            col_idx = 0
            
            for m_sku, pdf_doc in master_sku_pdfs.items():
                order_qty = len(pdf_doc) // 2
                prod_name = "Product Not Found"
                img_url = "https://via.placeholder.com/150?text=No+Photo"
                
                if m_sku in prod_df['SKU'].values:
                    p_row = prod_df[prod_df['SKU'] == m_sku].iloc[0]
                    prod_name = p_row['Product Name']
                    img_path = str(p_row.get('Product Image', ''))
                    
                    if img_path and img_path != 'nan' and app_id:
                        encoded_img = urllib.parse.quote(img_path)
                        img_url = f"https://www.appsheet.com/template/gettablefileurl?appName={app_id.strip()}&tableName=Products&fileName={encoded_img}"
                
                with cols[col_idx]:
                    # 🎨 FLOATING CARD WITH AUTO-FIT IMAGE & IN-BUILT QUANTITY
                    st.markdown(f"""
                    <div style="background: #ffffff; 
                                border-radius: 15px; 
                                padding: 12px; 
                                box-shadow: 0 8px 20px rgba(0,0,0,0.1); 
                                display: flex; 
                                align-items: center; 
                                gap: 15px; 
                                border: 1px solid #f1f5f9; 
                                margin-bottom: 5px;">
                        <div style="flex-shrink: 0;">
                            <img src="{img_url}" width="80" height="80" style="border-radius: 10px; object-fit: contain; background: #fff; border: 1px solid #e2e8f0; padding: 4px;">
                        </div>
                        <div style="flex-grow: 1;">
                            <h4 style="margin: 0 0 6px 0; font-size: 17px; color: #1e293b; font-weight: 800;">{prod_name}</h4>
                            <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                                <span style="background: #f1f5f9; color: #475569; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; border: 1px solid #cbd5e1;">{m_sku}</span>
                                <span style="background: #dbeafe; color: #1d4ed8; padding: 4px 8px; border-radius: 6px; font-size: 13px; font-weight: 900; border: 1px solid #bfdbfe;">📦 {order_qty} Pcs</span>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 🖨️ FULL WIDTH DOWNLOAD BUTTON
                    pdf_output = pdf_doc.write()
                    st.download_button(
                        label=f"📥 Download {order_qty} {m_sku} Labels",
                        data=pdf_output,
                        file_name=f"{m_sku}_Labels_Qty_{order_qty}.pdf",
                        mime="application/pdf",
                        key=f"btn_{m_sku}_{order_qty}",
                        use_container_width=True # Button poori width lega, ekdum tab se milkar aayega
                    )
                    st.markdown("<br>", unsafe_allow_html=True)

                col_idx = (col_idx + 1) % 3
                
        except Exception as e:
            st.error(f"Error: {e}")
