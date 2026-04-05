import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import io
import urllib.parse

st.set_page_config(page_title="Celvia Smart Print Portal", layout="wide", page_icon="📦")
st.title("📦 Celvia Smart Label WMS (Visual Multi-Batch)")

# 👇 PERMANENT LINKS & APP ID 👇
DEFAULT_MAPPING_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=158825893&single=true&output=csv"
DEFAULT_PRODUCTS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=0&single=true&output=csv"
# Aapka naya App ID yahan hardcode kar diya hai!
DEFAULT_APP_ID = "Untitledspreadsheet-306094028"

# --- SIDEBAR SETTINGS ---
st.sidebar.header("⚙️ Settings")
mapping_url = st.sidebar.text_input("Mapping CSV Link (Tab 1)", value=DEFAULT_MAPPING_URL)
products_url = st.sidebar.text_input("Products CSV Link (Tab 2)", value=DEFAULT_PRODUCTS_URL)

st.sidebar.markdown("---")
st.sidebar.header("🖼️ Photo Configuration")
st.sidebar.success("✅ AppSheet connected automatically!")
app_id = st.sidebar.text_input("AppSheet App ID", value=DEFAULT_APP_ID)

if st.sidebar.button("🔄 Sync Database Data"):
    st.rerun()

# --- MULTIPLE PDF UPLOADER ---
uploaded_pdfs = st.file_uploader("📥 Upload Multiple Flipkart PDFs (Select as many as you want)", type=["pdf"], accept_multiple_files=True)

if uploaded_pdfs:
    with st.spinner("Analyzing all PDFs, Aggregating SKUs & Fetching Live Photos... 🚀"):
        try:
            # Load Sheet Data
            map_df = pd.read_csv(mapping_url)
            prod_df = pd.read_csv(products_url)
            
            map_df['Flipkart_SKU'] = map_df['Flipkart_SKU'].astype(str).str.strip()
            prod_df['SKU'] = prod_df['SKU'].astype(str).str.strip()
            
            # Dictionary to hold combined PDFs for each SKU
            master_sku_pdfs = {}
            
            # Step 1: Har PDF ko ek-ek karke process karo aur ek jagah ikkatta karo
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
                    
                    # ✂️ CROP & ROTATE LOGIC 
                    rect = page.rect
                    # Label Crop (Seedha)
                    page.set_cropbox(fitz.Rect(rect.width * 0.30, rect.height * 0.03, rect.width * 0.70, rect.height * 0.46))
                    page.set_rotation(0)
                    master_sku_pdfs[found_master_sku].insert_pdf(doc, from_page=page_num, to_page=page_num)
                    
                    # Invoice Crop (90 Degree Ghuma ke)
                    page.set_cropbox(fitz.Rect(0, rect.height * 0.46, rect.width, rect.height * 0.83))
                    page.set_rotation(90)
                    master_sku_pdfs[found_master_sku].insert_pdf(doc, from_page=page_num, to_page=page_num)

            # --- DISPLAY DASHBOARD ---
            st.success(f"✅ Masterfully Processed {len(uploaded_pdfs)} PDF Files. Ready to Print & Pack!")
            st.markdown("---")
            
            cols = st.columns(3)
            col_idx = 0
            
            for m_sku, pdf_doc in master_sku_pdfs.items():
                order_qty = len(pdf_doc) // 2
                prod_name = "Product Not Found"
                img_url = "https://via.placeholder.com/150?text=No+Photo"
                
                # Tab 2 se photo uthana aur AppSheet link banana
                if m_sku in prod_df['SKU'].values:
                    p_row = prod_df[prod_df['SKU'] == m_sku].iloc[0]
                    prod_name = p_row.get('Product Name', 'Unknown Name')
                    img_path = str(p_row.get('Product Image', ''))
                    
                    # 💥 The Live AppSheet Photo Engine 💥
                    if img_path and img_path != 'nan' and app_id:
                        encoded_img = urllib.parse.quote(img_path)
                        img_url = f"https://www.appsheet.com/template/gettablefileurl?appName={app_id.strip()}&tableName=Products&fileName={encoded_img}"
                
                with cols[col_idx]:
                    # 🎨 PREMIUM UI CARD WITH LIVE PHOTO
                    st.markdown(f"""
                    <div style="border: 1px solid #d1d5db; border-radius: 8px; padding: 12px; background-color: #f3f4f6; display: flex; align-items: center; gap: 15px; margin-bottom: 10px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                        <img src="{img_url}" width="75" height="75" style="border-radius: 8px; object-fit: cover; border: 2px solid #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.2);">
                        <div>
                            <p style="margin: 0 0 5px 0; font-weight: 800; font-size: 15px; color: #1f2937; line-height: 1.2;">{prod_name}</p>
                            <span style="background-color: #e5e7eb; color: #374151; font-size: 11px; padding: 2px 6px; border-radius: 4px; border: 1px solid #d1d5db; font-weight: bold;">{m_sku}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"<p style='margin: 0; font-size: 16px;'>📦 <b>Total Packets:</b> <span style='color: #2563eb; font-weight: 900; font-size: 18px;'>{order_qty}</span></p>", unsafe_allow_html=True)
                    
                    # Download Button for the combined SKU PDF
                    pdf_output = pdf_doc.write()
                    st.download_button(
                        label=f"🖨️ Download {m_sku} Labels",
                        data=pdf_output,
                        file_name=f"Celvia_{m_sku}_Orders_{order_qty}.pdf",
                        mime="application/pdf",
                        key=f"btn_{m_sku}_{order_qty}"
                    )
                    st.markdown("<br>", unsafe_allow_html=True)

                col_idx = (col_idx + 1) % 3
                
        except Exception as e:
            st.error(f"❌ Error aaya hai: {e}")
