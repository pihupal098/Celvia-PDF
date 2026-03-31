import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import io

st.set_page_config(page_title="Celvia Print Portal", layout="wide")
st.title("📦 Celvia Smart Label WMS")

# 👇 APNE PERMANENT LINKS YAHAN DAALEIN (Inverted commas ke andar) 👇
DEFAULT_MAPPING_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=158825893&single=true&output=csv"
DEFAULT_PRODUCTS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=0&single=true&output=csv"

st.sidebar.header("⚙️ Database Connection")
st.sidebar.success("✅ Links pehle se bhare hue hain. Future mein sheet change ho toh yahan naya link daal sakte hain.")

# Dabbe rahenge, par unme default links pehle se bhare honge
mapping_url = st.sidebar.text_input("Mapping CSV Link (Tab 1)", value=DEFAULT_MAPPING_URL)
products_url = st.sidebar.text_input("Products CSV Link (Tab 2)", value=DEFAULT_PRODUCTS_URL)

# Refresh Button
if st.sidebar.button("🔄 Refresh Database"):
    st.rerun() # Naya SKU AppSheet se turant fetch karne ke liye

uploaded_pdf = st.file_uploader("📥 Upload Flipkart Raw Labels PDF", type=["pdf"])

if uploaded_pdf:
    if mapping_url == "TAB_1_LINK_HERE" or products_url == "TAB_2_LINK_HERE":
        st.error("⚠️ Paji, Code mein apne Google Sheet ke CSV links paste kijiye, ya left side dabbe mein daaliye!")
    else:
        with st.spinner("Processing Labels, Rotating Invoice & Syncing... 🚀"):
            try:
                # Load Google Sheets Data from the input boxes
                map_df = pd.read_csv(mapping_url)
                prod_df = pd.read_csv(products_url)
                
                # Ensure text matching is clean
                map_df['Flipkart_SKU'] = map_df['Flipkart_SKU'].astype(str).str.strip()
                map_df['Master_SKU'] = map_df['Master_SKU'].astype(str).str.strip()
                prod_df['SKU'] = prod_df['SKU'].astype(str).str.strip()
                
                # Read Raw PDF
                doc = fitz.open(stream=uploaded_pdf.read(), filetype="pdf")
                master_sku_pdfs = {}
                
                # Process each page
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    text = page.get_text()
                    
                    # Find which Flipkart SKU is on this page
                    found_master_sku = "Unmapped_SKU"
                    for index, row in map_df.iterrows():
                        flipkart_sku = row['Flipkart_SKU']
                        if flipkart_sku in text:
                            found_master_sku = row['Master_SKU']
                            break
                    
                    # Group pages by Master SKU dictionary
                    if found_master_sku not in master_sku_pdfs:
                        master_sku_pdfs[found_master_sku] = fitz.open()
                    
                    rect = page.rect
                    
                    # ✂️ CROP 1: LABEL (Left 30%, Right 70%, Top 3% to 46%)
                    label_left = rect.width * 0.30
                    label_right = rect.width * 0.70
                    page.set_cropbox(fitz.Rect(label_left, rect.height * 0.03, label_right, rect.height * 0.46))
                    page.set_rotation(0) # Label seedha rahega
                    master_sku_pdfs[found_master_sku].insert_pdf(doc, from_page=page_num, to_page=page_num)
                    
                    # ✂️ CROP 2: INVOICE (Left 0, Right Full, Top 46% to 83% + 90 Degree Rotation)
                    page.set_cropbox(fitz.Rect(0, rect.height * 0.46, rect.width, rect.height * 0.86))
                    page.set_rotation(90) # 🔥 Invoice ko 90 degree ghumakar khada kiya
                    master_sku_pdfs[found_master_sku].insert_pdf(doc, from_page=page_num, to_page=page_num)

                st.success("✅ Labels Cropped Tight & Invoices Rotated Automatically!")
                st.markdown("---")
                
                # Dashboard View Generation
                cols = st.columns(3)
                col_index = 0
                
                for m_sku, pdf_doc in master_sku_pdfs.items():
                    order_count = len(pdf_doc) // 2 
                    
                    # Find Product Name from Products Tab
                    prod_name = "Item Name Not Found"
                    if m_sku in prod_df['SKU'].values:
                        prod_name = prod_df[prod_df['SKU'] == m_sku]['Product Name'].values[0] 
                        
                    # Save cropped PDF to memory
                    pdf_bytes = pdf_doc.write()
                    
                    with cols[col_index]:
                        st.info(f"🏎️ **{prod_name}**")
                        st.write(f"**Master SKU:** {m_sku}")
                        st.write(f"**Orders:** {order_count} (Total Prints: {len(pdf_doc)})")
                        
                        st.download_button(
                            label=f"🖨️ Download {m_sku} Labels",
                            data=pdf_bytes,
                            file_name=f"{m_sku}_Cropped_Labels.pdf",
                            mime="application/pdf",
                            key=f"dl_{m_sku}_{order_count}"
                        )
                    col_index = (col_index + 1) % 3
                    
            except Exception as e:
                st.error(f"❌ Kuch gadbad hui: {e}")
