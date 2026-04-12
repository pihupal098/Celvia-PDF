import streamlit as st
import pandas as pd
import io
import re
import numpy as np

st.set_page_config(page_title="GST Master Aggregator", layout="wide", page_icon="📊")

st.title("📊 Celvia GST Master Aggregator (Auto-Tax Engine)")
st.markdown("Ultimate engine: Extracts exact rates using Regex and auto-calculates missing IGST, CGST, and SGST based on UP Place of Supply.")

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
    """Scans rows to find the exact header line."""
    for i in range(min(20, len(df))):
        row_vals = df.iloc[i].astype(str).str.lower().tolist()
        if any('taxable' in str(v) for v in row_vals) and any('rate' in str(v) or 'amount' in str(v) for v in row_vals):
            df.columns = df.iloc[i].astype(str).str.lower().str.strip()
            return df.iloc[i+1:].reset_index(drop=True)
    df.columns = df.columns.astype(str).str.lower().str.strip()
    return df

# ==========================================
# 2. COLUMN EXTRACTION & AUTO-TAX ENGINE
# ==========================================
def clean_col(name):
    return re.sub(r'\s+', ' ', str(name).lower().strip())

def extract_standard_data(df, category):
    df.columns = [clean_col(c) for c in df.columns]
    
    col_maps = {
        'gstin': ['gstin/uin of recipient', 'gstin/uin', 'customer gstin', 'buyer gstin'],
        'invoice_no': ['invoice number', 'document number', 'invoice no'],
        'invoice_date': ['invoice date', 'document date'],
        'invoice_val': ['invoice value', 'total invoice value', 'gross amount'],
        'pos': ['place of supply', 'state', 'delivery state'],
        'rate': ['rate', 'tax rate', 'tax %', 'igst rate', 'gst rate', 'rate (%)'],
        'taxable_val': ['taxable value', 'item taxable value', 'total taxable value', 'taxable amount'],
        'igst': ['integrated tax amount', 'integrated tax', 'igst', 'igst amount'],
        'cgst': ['central tax amount', 'central tax', 'cgst', 'cgst amount'],
        'sgst': ['state/ut tax amount', 'state tax amount', 'state tax', 'sgst', 'sgst amount'],
        'hsn': ['hsn', 'hsn code'],
        'qty': ['total quantity', 'quantity', 'qty'],
        'uqc': ['uqc', 'unit']
    }

    def find_col(target):
        for possible_name in col_maps.get(target, []):
            for actual_col in df.columns:
                if possible_name == actual_col: return actual_col
        for possible_name in col_maps.get(target, []):
            for actual_col in df.columns:
                if possible_name in actual_col: return actual_col
        return None

    std_df = pd.DataFrame()
    
    def extract_pure_number(col_name):
        if col_name and col_name in df.columns:
            # Bulletproof regex: extracts only the digits/decimals
            extracted = df[col_name].astype(str).str.extract(r'(\d+\.?\d*)')[0]
            return pd.to_numeric(extracted, errors='coerce').fillna(0.0)
        return 0.0

    std_df['Place_of_Supply'] = df[find_col('pos')] if find_col('pos') else 'Unknown'
    std_df['Rate'] = extract_pure_number(find_col('rate'))
    std_df['Taxable_Value'] = extract_pure_number(find_col('taxable_val'))
    std_df['IGST'] = extract_pure_number(find_col('igst'))
    std_df['CGST'] = extract_pure_number(find_col('cgst'))
    std_df['SGST'] = extract_pure_number(find_col('sgst'))

    if category in ['B2B', 'CDNR']:
        std_df['GSTIN'] = df[find_col('gstin')] if find_col('gstin') else ''
        std_df['Invoice_Number'] = df[find_col('invoice_no')] if find_col('invoice_no') else ''
        std_df['Invoice_Date'] = df[find_col('invoice_date')] if find_col('invoice_date') else ''
        std_df['Invoice_Value'] = extract_pure_number(find_col('invoice_val'))
        
    elif category == 'HSN':
        std_df['HSN'] = df[find_col('hsn')] if find_col('hsn') else ''
        std_df['Description'] = 'E-commerce Goods'
        std_df['UQC'] = df[find_col('uqc')] if find_col('uqc') else 'NOS'
        std_df['Total_Quantity'] = extract_pure_number(find_col('qty'))
        std_df['Total_Value'] = extract_pure_number(find_col('invoice_val'))

    # Drop fully empty rows
    std_df = std_df.dropna(how='all')
    if 'Taxable_Value' in std_df.columns:
        std_df = std_df[std_df['Taxable_Value'] != 0]

    if std_df.empty:
        return std_df

    # ==========================================
    # AUTO-TAX CALCULATOR (The Magic Fix)
    # If GSTR-1 files omit tax columns, calculate them dynamically
    # ==========================================
    tax_is_zero = (std_df['IGST'] == 0) & (std_df['CGST'] == 0) & (std_df['SGST'] == 0)
    valid_data = (std_df['Rate'] > 0) & (std_df['Taxable_Value'] != 0)
    needs_calc = tax_is_zero & valid_data
    
    if needs_calc.any():
        # Base state logic: 09 - Uttar Pradesh
        is_up = std_df['Place_of_Supply'].astype(str).str.lower().str.contains('09|uttar pradesh|^up$|lucknow')
        
        # Intra-state (UP): Split 50-50 into CGST and SGST
        intra = needs_calc & is_up
        std_df.loc[intra, 'CGST'] = (std_df.loc[intra, 'Taxable_Value'] * std_df.loc[intra, 'Rate']) / 200
        std_df.loc[intra, 'SGST'] = (std_df.loc[intra, 'Taxable_Value'] * std_df.loc[intra, 'Rate']) / 200
        
        # Inter-state (Outside UP): 100% IGST
        inter = needs_calc & ~is_up
        std_df.loc[inter, 'IGST'] = (std_df.loc[inter, 'Taxable_Value'] * std_df.loc[inter, 'Rate']) / 100

    # ==========================================
    # RETURN MATH (Negative adjustments for Credit Notes)
    # ==========================================
    if category in ['CDNR', 'CDNUR']:
        cols_to_negate = ['Taxable_Value', 'IGST', 'CGST', 'SGST', 'Total_Value', 'Total_Quantity', 'Invoice_Value']
        for col in cols_to_negate:
            if col in std_df.columns:
                std_df[col] = std_df[col].apply(lambda x: -abs(x) if pd.notna(x) and x > 0 else x)
        
    return std_df

# ==========================================
# 3. ENGINE RUNNER
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
    # 4. AGGREGATION & DISPLAY
    # ==========================================
    has_data = any(len(v) > 0 for v in master_data.values())
    
    if has_data:
        st.success("🎯 Analysis Complete. Values Extracted & Auto-Calculated.")
        st.header("3. Full-Fledged GSTR-1 Output")
        
        final_output = {}
        
        # Format B2B & CDNR
        for cat in ['B2B', 'CDNR']:
            if master_data[cat]:
                df_concat = pd.concat(master_data[cat], ignore_index=True)
                cols = ['GSTIN', 'Invoice_Number', 'Invoice_Date', 'Invoice_Value', 'Place_of_Supply', 'Rate', 'Taxable_Value', 'IGST', 'CGST', 'SGST']
                cols = [c for c in cols if c in df_concat.columns]
                final_output[cat] = df_concat[cols].round(2)
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
            st.subheader("B2C Net Sales Summary (Exact Tax Breakup)")
            st.dataframe(final_output['B2CS_NET'], use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for sheet_name, df in final_output.items():
                if not df.empty:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    
        st.header("4. Download for Filing")
        st.download_button(
            label="📥 Download Final Detailed GSTR-1 (.xlsx)",
            data=output.getvalue(),
            file_name="Celvia_Final_Detailed_GSTR1.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
