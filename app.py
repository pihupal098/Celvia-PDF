import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import io
import urllib.parse
import base64

st.set_page_config(page_title="Celvia Smart Print Portal", layout="wide", page_icon="📦")

# 👇 DEFAULTS (PRE-FILLED DATA) 👇
# Aapki photos se maine aapka asli App ID nikal liya hai
DEFAULT_MAPPING_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=158825893&single=true&output=csv"
DEFAULT_PRODUCTS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSiWvmcQ_fLTnGyrh7gLJCtr40_7Er_hGenwP0D6Ra2322Nkx6ATfh9cSHs5ILETiiIoFkA6llLc9Lp/pub?gid=0&single=true&output=csv"
DEFAULT_APP_ID = "Untitledspreadsheet-306094028" # 👈 AAPKA ASLI APP ID 

# --- SIDEBAR (Links & ID already daale hue hain) ---
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
    with st.spinner("Analyzing PDFs, Sorting by Quantity & Preparing UI... 🚀"):
        try:
            map_df = pd.read_csv(mapping_url)
            prod_df = pd.read_csv(products_url)
            
            map_df['Flipkart_SKU'] = map_df['Flipkart_SKU'].astype(str).str.strip()
            prod_df['SKU'] = prod_df['SKU'].astype(str).str.strip()
            
            master_sku_pdfs = {}
            
            # Smart PDF Aggregation
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
                    
                    page.set_cropbox(fitz.Rect(0, rect.height * 0.46, rect.width, rect.height * 0.92))
                    page.set_rotation(90)
                    master_sku_pdfs[found_master_sku].insert_pdf(doc, from_page=page_num, to_page=page_num)

            # --- 💥 DESCENDING ORDER SORTING 💥 ---
            # Total pages // 2 ke hisaab se descending order mein sort kiya
            sorted_skus = sorted(master_sku_pdfs.items(), key=lambda x: len(x[1]), reverse=True)

            # --- GRAND TOTAL BANNER ---
            total_grand_orders = sum(len(pdf) // 2 for pdf in master_sku_pdfs.values())

            # Flush-left HTML to avoid Streamlit code block bugs
            grand_total_html = f"""
<div style="background: linear-gradient(135deg, #ff416c 0%, #ff4b2b 100%); padding: 25px; border-radius: 25px; text-align: center; box-shadow: 0 15px 35px rgba(255, 75, 43, 0.4); margin-top: 15px; margin-bottom: 40px; border: 3px solid rgba(255,255,255,0.3);">
<h1 style="color: white; margin: 0; font-size: 2.8rem; font-weight: 900; letter-spacing: 2px; text-transform: uppercase;">
🚀 Total Packets: 
<span style="background: white; color: #ff4b2b; padding: 5px 30px; border-radius: 20px; font-size: 3.5rem; margin-left: 20px; box-shadow: inset 0 5px 10px rgba(0,0,0,0.15);">
{total_grand_orders}
</span>
</h1>
</div>
"""
            st.markdown(grand_total_html, unsafe_allow_html=True)
            
            # --- VIBRANT COLOR PALETTE ---
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
            
            # Render Cards based on Sorted Data
            for m_sku, pdf_doc in sorted_skus:
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
                
                # Encode PDF for direct HTML Download Button
                pdf_bytes = pdf_doc.write()
                b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                download_filename = f"{m_sku}_Labels_Qty_{order_qty}.pdf"
                card_bg = bg_gradients[loop_counter % len(bg_gradients)]
                
                # Flush-left Card HTML
                card_html = f"""
<div style="background: {card_bg}; border-radius: 20px; padding: 18px; box-shadow: 0 10px 25px rgba(0,0,0,0.12); display: flex; flex-direction: column; gap: 15px; border: 2px solid rgba(255,255,255,0.6); margin-bottom: 25px; transition: transform 0.3s ease;">
<div style="display: flex; align-items: center; gap: 15px; background: rgba(255,255,255,0.7); padding: 12px; border-radius: 15px; backdrop-filter: blur(5px);">
<div style="background: white; padding: 4px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.08); flex-shrink: 0; width: 88px; height: 88px; display: flex; justify-content: center; align-items: center;">
<img src="{img_url}" style="max-width: 80px; max-height: 80px; border-radius: 8px; object-fit: contain;">
</div>
<div style="flex-grow: 1;">
<h4 style="margin: 0 0 6px 0; font-size: 17px; color: #0f172a; font-weight: 900; line-height: 1.2;">{prod_name}</h4>
<span style="background: #1e293b; color: white; padding: 4px 10px; border-radius: 8px; font-size: 12px; font-weight: 800; letter-spacing: 0.5px; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
{m_sku}
</span>
</div>
</div>
<a href="data:application/pdf;base64,{b64_pdf}" download="{download_filename}" style="text-decoration: none;">
<div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 12px; border-radius: 14px; text-align: center; font-weight: 900; font-size: 16px; letter-spacing: 1px; box-shadow: 0 6px 15px rgba(16, 185, 129, 0.4); display: flex; justify-content: center; align-items: center; gap: 12px;">
📥 DOWNLOAD 
<span style="background: white; color: #059669; padding: 2px 14px; border-radius: 10px; font-size: 18px; box-shadow: inset 0 2px 5px rgba(0,0,0,0.15);">
{order_qty}
</span>
</div>
</a>
</div>
"""
                with cols[loop_counter % 3]:
                    st.markdown(card_html, unsafe_allow_html=True)
                    
                loop_counter += 1
                
        except Exception as e:
            st.error(f"❌ Error: {e}")
