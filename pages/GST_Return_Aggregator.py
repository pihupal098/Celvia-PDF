import streamlit as st
import pandas as pd
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="GST Aggregator", layout="wide", page_icon="📊")

st.title("📊 Celvia GST Return Aggregator")
st.markdown("Upload multiple Flipkart and Amazon Excel tax reports. The app will scan all tabs, standardize the columns, and generate a consolidated B2B and B2C report.")

# --- COLUMN STANDARDIZATION LOGIC ---
COLUMN_MAP = {
    'customer gstin': 'GSTIN', 'buyer gstin': 'GSTIN', 'buyer registration number': 'GSTIN',
    'item taxable value': 'Taxable_Value', 'taxable value': 'Taxable_Value', 'principal amount': 'Taxable_Value',
    'tax %': 'Tax_Rate', 'item tax %': 'Tax_Rate', 'igst rate': 'Tax_Rate',
    'delivery state': 'State', 'ship to state': 'State', 'place of supply': 'State',
    'igst amount': 'IGST', 'integrated tax': 'IGST',
    'cgst amount': 'CGST', 'central tax': 'CGST',
    'sgst amount': 'SGST', 'state tax': 'SGST',
    'invoice number': 'Invoice_Number', 'invoice date': 'Invoice_Date',
}

def standardize_dataframe(df):
    df.columns = df.columns.astype(str).str.lower().str.strip()
    df.rename(columns=COLUMN_MAP, inplace=True)
    required_cols = ['GSTIN', 'Taxable_Value', 'Tax_Rate', 'State', 'IGST', 'CGST', 'SGST', 'Invoice_Number']
    for col in required_cols:
        if col not in df.columns:
            if col in ['Taxable_Value', 'Tax_Rate', 'IGST', 'CGST', 'SGST']:
                df[col] = 0.0
            else:
                df[col] = None
    return df

# --- UPLOADER INTERFACE ---
st.header("1. Upload Reports")
uploaded_files = st.file_uploader(
    "Drag and drop all your Excel files (.xlsx) here", 
    type=['xlsx'], 
    accept_multiple_files=True
)

if uploaded_files:
    master_b2b = pd.DataFrame()
    master_b2c = pd.DataFrame()
    
    st.header("2. Processing Status")
    
    for file in uploaded_files:
        st.write(f"📂 **Reading File:** {file.name}")
        
        try:
            excel_data = pd.read_excel(file, sheet_name=None)
            
            for tab_name, df in excel_data.items():
                if df.empty:
                    continue
                    
                st.text(f"  ↳ Scanning Tab: '{tab_name}' ({len(df)} rows)")
                df_clean = standardize_dataframe(df)
                
                num_cols = ['Taxable_Value', 'Tax_Rate', 'IGST', 'CGST', 'SGST']
                for col in num_cols:
                    df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)
                
                is_b2b = df_clean['GSTIN'].notna() & (df_clean['GSTIN'].astype(str).str.len() > 5)
                
                master_b2b = pd.concat([master_b2b, df_clean[is_b2b]], ignore_index=True)
                master_b2c = pd.concat([master_b2c, df_clean[~is_b2b]], ignore_index=True)
                
        except Exception as e:
            st.error(f"Error processing {file.name}: {str(e)}")

    # --- EXPORT LOGIC ---
    if not master_b2b.empty or not master_b2c.empty:
        st.success("✅ All files processed and merged successfully!")
        st.header("3. Final Aggregated Data")
        
        final_b2b = master_b2b[['GSTIN', 'Invoice_Number', 'State', 'Taxable_Value', 'Tax_Rate', 'IGST', 'CGST', 'SGST']]
        
        if not master_b2c.empty:
            final_b2c = master_b2c.groupby(['State', 'Tax_Rate']).agg({
                'Taxable_Value': 'sum', 'IGST': 'sum', 'CGST': 'sum', 'SGST': 'sum'
            }).reset_index()
        else:
            final_b2c = pd.DataFrame()

        st.subheader("B2C Aggregated Summary")
        st.dataframe(final_b2c)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_b2c.to_excel(writer, sheet_name='B2C_Aggregated', index=False)
            final_b2b.to_excel(writer, sheet_name='B2B_Invoices', index=False)
            
        st.header("4. Download Output")
        st.download_button(
            label="📥 Download Consolidated GST Report (.xlsx)",
            data=output.getvalue(),
            file_name="Celvia_GST_Output.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
