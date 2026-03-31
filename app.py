import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import io

st.set_page_config(page_title="Celvia Print Portal", layout="wide")
st.title("📦 Celvia Smart Label WMS")

st.sidebar.header("⚙️ Database Connection")
mapping_url = st.sidebar.text_input("Mapping CSV Link (Flipkart SKU to Master SKU)", placeholder="Paste Tab 1 CSV link here")
products_url = st.sidebar.text_input("Products CSV Link (SKU to Product Name)", placeholder="Paste Tab 2 CSV link here")

uploaded_pdf = st.file_uploader("📥 Upload Flipkart Raw Labels PDF", type=["pdf"])

if uploaded_pdf and mapping_url and products_url:
    with st.spinner("Processing Labels & Syncing Database... 🚀"):
        try:
            # Load Google Sheets Data
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
                
                # Crop to Top Half (Thermal Label Size 4x6 approx)
                rect = page.rect
                page.set_cropbox(fitz.Rect(0, 0, rect.width, rect.height / 2))
                
                # Group pages by Master SKU
                if found_master_sku not in master_sku_pdfs:
                    master_sku_pdfs[found_master_sku] = fitz.open()
                
                master_sku_pdfs[found_master_sku].insert_pdf(doc, from_page=page_num, to_page=page_num)

            st.success("✅ Labels Processed, Cropped & Sorted Automatically!")
            st.markdown("---")
            
            # Dashboard View Generation
            cols = st.columns(3)
            col_index = 0
            
            for m_sku, pdf_doc in master_sku_pdfs.items():
                order_count = len(pdf_doc)
                
                # Find Product Name from Products Tab
                prod_name = "Item Name Not Found"
                if m_sku in prod_df['SKU'].values:
                    # Aapki sheet se exact 'Product Name' uthayega
                    prod_name = prod_df[prod_df['SKU'] == m_sku]['Product Name'].values[0] 
                    
                # Save cropped PDF to memory
                pdf_bytes = pdf_doc.write()
                
                with cols[col_index]:
                    st.info(f"🏎️ **{prod_name}**")
                    st.write(f"**Master SKU:** {m_sku}")
                    st.write(f"**Total Labels:** {order_count} Orders")
                    
                    st.download_button(
                        label=f"🖨️ Download {order_count} Labels",
                        data=pdf_bytes,
                        file_name=f"{m_sku}_Labels.pdf",
                        mime="application/pdf",
                        key=m_sku
                    )
                col_index = (col_index + 1) % 3
                
        except Exception as e:
            st.error(f"❌ Kuch gadbad hui: {e}")
