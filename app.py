import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import io

st.set_page_config(page_title="Celvia Print Portal", layout="wide")
st.title("📦 Celvia Smart Label & Invoice WMS")

# ==========================================
# 🛑 APNE PERMANENT LINKS YAHAN DAALEIN 🛑
# ==========================================
DEFAULT_MAPPING_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=158825893&single=true&output=csv"  # Yahan apna Tab 1 (Mapping) ka link " " ke andar paste karein
DEFAULT_PRODUCTS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=0&single=true&output=csv" # Yahan apna Tab 2 (Products) ka link " " ke andar paste karein

st.sidebar.header("⚙️ Database Connection")
mapping_url = st.sidebar.text_input("Mapping CSV Link", value=DEFAULT_MAPPING_URL)
products_url = st.sidebar.text_input("Products CSV Link", value=DEFAULT_PRODUCTS_URL)

# Ye button naye SKU AppSheet me dalne ke baad dabana hai
if st.sidebar.button("🔄 Refresh Database"):
    st.cache_data.clear()
    st.sidebar.success("Database Refreshed! Upload PDF again.")

@st.cache_data(ttl=300) # Data ko fast load karne ke liye cache
def load_data(map_url, prod_url):
    map_df = pd.read_csv(map_url)
    prod_df = pd.read_csv(prod_url)
    map_df['Flipkart_SKU'] = map_df['Flipkart_SKU'].astype(str).str.strip()
    map_df['Master_SKU'] = map_df['Master_SKU'].astype(str).str.strip()
    prod_df['SKU'] = prod_df['SKU'].astype(str).str.strip()
    return map_df, prod_df

uploaded_pdf = st.file_uploader("📥 Upload Flipkart Raw Labels PDF", type=["pdf"])

if uploaded_pdf and mapping_url and products_url:
    with st.spinner("Processing Labels, Splitting Invoices & Syncing AppSheet... 🚀"):
        try:
            map_df, prod_df = load_data(mapping_url, products_url)
            
            # Read Raw PDF
            doc = fitz.open(stream=uploaded_pdf.read(), filetype="pdf")
            master_sku_pdfs = {}
            
            # Process each page
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                rect = page.rect
                
                # Naya/Unmapped SKU Check
                found_master_sku = "⚠️ UNMAPPED NEW ORDERS"
                for index, row in map_df.iterrows():
                    flipkart_sku = row['Flipkart_SKU']
                    if flipkart_sku != "nan" and flipkart_sku in text:
                        found_master_sku = row['Master_SKU']
                        break
                
                if found_master_sku not in master_sku_pdfs:
                    master_sku_pdfs[found_master_sku] = fitz.open()
                
                target_pdf = master_sku_pdfs[found_master_sku]
                
                # --- MAGIC TRICK: 1 A4 Page becomes 2 Thermal Pages ---
                
                # 1. LABEL: Insert page and crop top 45%
                target_pdf.insert_pdf(doc, from_page=page_num, to_page=page_num)
                label_page = target_pdf[-1]
                label_page.set_cropbox(fitz.Rect(0, 0, rect.width, rect.height * 0.46))
                
                # 2. INVOICE: Insert same page again and crop bottom 55%
                target_pdf.insert_pdf(doc, from_page=page_num, to_page=page_num)
                invoice_page = target_pdf[-1]
                invoice_page.set_cropbox(fitz.Rect(0, rect.height * 0.46, rect.width, rect.height))

            st.success("✅ Labels & Invoices Processed, Cropped & Sorted Automatically!")
            st.markdown("---")
            
            # Dashboard View Generation
            cols = st.columns(3)
            col_index = 0
            
            for m_sku, pdf_doc in master_sku_pdfs.items():
                # 1 Order ki 2 panni hain (Label + Invoice), toh actual orders half honge
                order_count = int(len(pdf_doc) / 2) 
                
                prod_name = "New SKU Detected!"
                if m_sku != "⚠️ UNMAPPED NEW ORDERS" and m_sku in prod_df['SKU'].values:
                    prod_name = prod_df[prod_df['SKU'] == m_sku]['Product Name'].values[0]
                    
                pdf_bytes = pdf_doc.write()
                
                with cols[col_index]:
                    if m_sku == "⚠️ UNMAPPED NEW ORDERS":
                        st.error(f"🚨 **{m_sku}**")
                        st.write(f"**Orders:** {order_count}")
                        st.caption("Print check karein, AppSheet me map karein, fir 'Refresh' dabayein.")
                    else:
                        st.info(f"🏎️ **{prod_name}**")
                        st.write(f"**Master SKU:** {m_sku}")
                        st.write(f"**Orders:** {order_count}")
                        st.caption("🖨️ Prints: Label + Invoice per order")
                    
                    st.download_button(
                        label=f"Download {order_count * 2} Thermal Pages",
                        data=pdf_bytes,
                        file_name=f"{m_sku}_Label_Invoice.pdf",
                        mime="application/pdf",
                        key=m_sku
                    )
                col_index = (col_index + 1) % 3
                
        except Exception as e:
            st.error(f"❌ Kuch gadbad hui: {e}")
