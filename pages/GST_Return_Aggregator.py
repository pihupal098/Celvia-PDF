import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="GST Master Aggregator", layout="wide", page_icon="📊")

st.title("📊 Celvia GST Master Aggregator (Full-Fledged)")
st.markdown("Ultimate GST engine. Extracts Taxable Value, EXACT Rates, IGST, CGST, SGST, applies negative math for returns automatically, and generates flawless output.")

# ==========================================
# 1. SMART TAB CLASSIFIER
# ==========================================
TAB_MAPPING = {
    'B2B': ['b2b', 'section 5b'],
    'B2CS': ['b2c small', 'section 7(a)(2)', 'section 7(b)(2)'],
    'CDNR': ['b2b cn', 'cdnr', 'section 10a(1)'],
    'CDNUR': ['b2cl cn', 'cdnur', 'section 10b(1)', 'b2cs cn'],
    'HSN': ['hsn', 'section 12']
}

def classify_tab(tab_name):
    tab_lower = tab_name.lower().strip()
    for category, keywords in TAB_MAPPING.items():
        for kw in keywords:
            if kw in tab_lower:
                return category
    return None

def find_true_header(df):
    """Deep Header Scanner"""
    for i in range(min(15, len(df))):
        row_str = str(df.iloc[i].values).lower()
        if ('taxable' in row_str or 'invoice' in row_str or 'gstin' in row_str) and ('rate' in row_str or 'value' in row_str or 'amount' in row_str):
            df.columns = df.iloc[i].astype(str).str.lower().str.strip()
            return df.iloc[i+1:].reset_index(drop=True)
    df.columns = df.columns.astype(str).str.lower().str.strip()
    return df

# ==========================================
# 2. FULL-FLEDGED COLUMN EXTRACTION
# ==========================================
def clean_col(name):
    return re.sub(r'\s+', ' ', str(name).lower().strip())

def extract_standard_data(df, category):
    df.columns = [clean_col(c) for c in df.columns]
    
    # Extensive mapping to catch every single column from Amazon/Flipkart
    col_maps = {
        'gstin': ['gstin/uin of recipient', 'gstin/uin', 'customer gstin', 'buyer gstin'],
        'invoice_no': ['invoice number', 'document number', 'invoice no', 'original document number'],
        'invoice_date': ['invoice date', 'document date', 'original document date'],
        'invoice_val': ['invoice value', 'total invoice value', 'gross amount'],
        'pos': ['place of supply', 'state', 'delivery state'],
        'rate': ['rate', 'tax rate', 'tax %', 'igst rate', 'gst rate', 'tax percentage', 'rate (%)'],
        'taxable_val': ['taxable value', 'item taxable value', 'total taxable value', 'taxable amount'],
        'igst': ['integrated tax amount', 'integrated tax', 'igst', 'igst amount', 'igst tax amount'],
        'cgst': ['central tax amount', 'central tax', 'cgst', 'cgst amount', 'cgst tax amount'],
        'sgst': ['state/ut tax amount', 'state tax amount', 'state tax', 'sgst', 'sgst amount', 'sgst tax amount'],
        'hsn': ['hsn', 'hsn code'],
        'qty': ['total quantity', 'quantity', 'qty'],
        'uqc': ['uqc', 'unit']
    }

    def find_col(target):
        # Exact match first, then partial match
        for possible_name in col_maps.get(target, []):
            for actual_col in df.columns:
                if possible_name == actual_col: return actual_col
        for possible_name in col_maps.get(target, []):
            for actual_col in df.columns:
                if possible_name in actual_col: return actual_col
        return None

    std_df = pd.DataFrame()
    
    def safe_numeric(col_name):
        if col_name and col_name in df.columns:
            # FIX: Removes '%', commas, and 'Rs.' to perfectly convert '18%' into 18.0
            cleaned = df[col_name].astype(str).str.replace(',', '', regex=False).str.replace('%', '', regex=False).str.replace('Rs.', '', regex=False)
            return pd.to_numeric(cleaned, errors='coerce').fillna(0)
        return 0.0

    # Populating all necessary fields including taxes
    std_df['Place_of_Supply'] = df[find_col('pos')] if find_col('pos') else 'Unknown'
    std_df['Rate'] = safe_numeric(find_col('rate'))
    std_df['Taxable_Value'] = safe_numeric(find_col('taxable_val'))
    std_df['IGST'] = safe_numeric(find_col('igst'))
    std_df['CGST'] = safe_numeric(find_col('cgst'))
    std_df['SGST'] = safe_numeric(find_col('sgst'))

    if category in ['B2B', 'CDNR']:
        std_df['GSTIN'] = df[find_col('gstin')] if find_col('gstin') else ''
        std_df['Invoice_Number'] = df[find_col('invoice_no')] if find_col('invoice_no') else ''
        std_df['Invoice_Date'] = df[find_col('invoice_date')] if find_col('invoice_date') else ''
        std_df['Invoice_Value'] = safe_numeric(find_col('invoice_val'))
        
    elif category == 'HSN':
        std_df['HSN'] = df[find_col('hsn')] if find_col('hsn') else ''
        std_df['Description'] = 'E-commerce Goods'
        std_df['UQC'] = df[find_col('uqc')] if find_col('uqc') else 'NOS'
        std_df['Total_Quantity'] = safe_numeric(find_col('qty'))
        std_df['Total_Value'] = safe_numeric(find_col('invoice_val'))

    # Drop blank rows safely
    std_df = std_df.dropna(how='all')
    if 'Taxable_Value' in std_df.columns:
        std_df = std_df[std_df['Taxable_Value'] != 0]

    # ==========================================
    # 3. EXACT RETURN MATH (Minus Values)
    # ==========================================
    # Apply negative logic to BOTH Taxable Value AND Taxes for Credit Notes
    if category in ['CDNR', 'CDNUR']:
        for col in ['Taxable_Value', 'IGST', 'CGST', 'SGST', 'Total_Value', 'Total_Quantity', 'Invoice_Value']:
            if col in std_df.columns:
                std_df[col] = std_df[col].apply(lambda x: -abs(x) if pd.notna(x) and x > 0 else x)
        
    return std_df

# ==========================================
# 4. PROCESSING ENGINE
# ==========================================
st.header("1. Upload GSTR Reports")
uploaded_files = st.file_uploader(
    "Upload Amazon & Flipkart GSTR Excel files here", 
    type=['xlsx'], 
    accept_multiple_files=True
)

if uploaded_files:
    master_data = {'B2B': [], 'B2CS': [], 'CDNR': [], 'CDNUR': [], 'HSN': []}
    st.header("2. Processing Status")
    
    for file in uploaded_files:
        st.write(f"📂 **Reading File:** {file.name}")
        try:
            excel_data = pd.read_excel(file, sheet_name=None)
            for tab_name, raw_df in excel_data.items():
                category = classify_tab(tab_name)
                if not category:
                    continue
                if raw_df.empty or len(raw_df) < 1:
                    continue

                clean_raw_df = find_true_header(raw_df)
                processed_df = extract_standard_data(clean_raw_df, category)
                
                if not processed_df.empty:
                    st.success(f"  ✅ Extracted {category} Data from: '{tab_name}'")
                    master_data[category].append(processed_df)
                
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")

    # ==========================================
    # 5. FINAL AGGREGATION & DISPLAY
    # ==========================================
    has_data = any(len(v) > 0 for v in master_data.values())
    
    if has_data:
        st.success("🎯 Analysis Complete. Returns deducted successfully.")
        st.header("3. Full-Fledged GSTR-1 Output")
        
        final_output = {}
        
        # Format B2B & CDNR
        for cat in ['B2B', 'CDNR']:
            if master_data[cat]:
                # Rearrange columns so GSTIN is first
                df_concat = pd.concat(master_data[cat], ignore_index=True)
                cols = ['GSTIN', 'Invoice_Number', 'Invoice_Date', 'Invoice_Value', 'Place_of_Supply', 'Rate', 'Taxable_Value', 'IGST', 'CGST', 'SGST']
                # Only keep columns that exist
                cols = [c for c in cols if c in df_concat.columns]
                final_output[cat] = df_concat[cols]
                st.write(f"**{cat}:** Ready")
                
        # Format B2CS (Grouped Net Sales)
        combined_b2cs = master_data['B2CS'] + master_data['CDNUR']
        if combined_b2cs:
            merged_df = pd.concat(combined_b2cs, ignore_index=True)
            grouped_b2cs = merged_df.groupby(['Place_of_Supply', 'Rate']).agg({
                'Taxable_Value': 'sum',
                'IGST': 'sum',
                'CGST': 'sum',
                'SGST': 'sum'
            }).reset_index()
            
            # Remove cleanly negated 0 rows
            grouped_b2cs = grouped_b2cs[grouped_b2cs['Taxable_Value'] != 0]
            final_output['B2CS_NET'] = grouped_b2cs.round(2)
            
        # Format HSN
        if master_data['HSN']:
            combined_hsn = pd.concat(master_data['HSN'], ignore_index=True)
            combined_hsn['HSN'] = combined_hsn['HSN'].astype(str).str.split('.').str[0]
            grouped_hsn = combined_hsn.groupby(['HSN', 'Description', 'UQC', 'Rate']).agg({
                'Total_Quantity': 'sum', 'Total_Value': 'sum', 'Taxable_Value': 'sum', 
                'IGST': 'sum', 'CGST': 'sum', 'SGST': 'sum'
            }).reset_index()
            final_output['HSN'] = grouped_hsn.round(2)

        # UI Preview
        if 'B2CS_NET' in final_output:
            st.subheader("B2C Net Sales Summary (Rate & Tax Breakup)")
            st.dataframe(final_output['B2CS_NET'], use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for sheet_name, df in final_output.items():
                if not df.empty:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    
        st.header("4. Download for Filing")
        st.download_button(
            label="📥 Download Detailed Master GSTR-1 (.xlsx)",
            data=output.getvalue(),
            file_name="Celvia_Detailed_GSTR1.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
