import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="GST Portal Aggregator", layout="wide", page_icon="📊")

st.title("📊 Celvia GST Aggregator (1:1 Portal Match)")
st.markdown("Generates an exact 1:1 match with the GST Portal Table 7 format. No manual column moving required.")

# ==========================================
# 1. CORE LOGIC: TAB & HEADER DETECTION
# ==========================================
def classify_tab(tab_name):
    tab_lower = tab_name.lower().strip()
    if any(x in tab_lower for x in ['b2c small', 'section 7(a)(2)', 'section 7(b)(2)']): return 'B2C'
    if any(x in tab_lower for x in ['b2cl cn', 'cdnur', 'section 10b(1)', 'b2cs cn']): return 'RETURN'
    return None

def find_true_header(df):
    for i in range(min(20, len(df))):
        row_str = str(df.iloc[i].values).lower()
        if 'taxable' in row_str and ('rate' in row_str or 'amount' in row_str or 'value' in row_str):
            df.columns = df.iloc[i].astype(str).str.lower().str.strip()
            return df.iloc[i+1:].reset_index(drop=True)
    df.columns = df.columns.astype(str).str.lower().str.strip()
    return df

# ==========================================
# 2. BULLETPROOF DATA EXTRACTION
# ==========================================
def clean_col(name):
    return re.sub(r'\s+', ' ', str(name).lower().strip())

def extract_portal_data(df, category):
    df.columns = [clean_col(c) for c in df.columns]
    
    col_maps = {
        'pos': ['place of supply', 'delivery state', 'state', 'ship to state', 'buyer state'],
        'rate': ['tax %', 'gst rate', 'tax percentage', 'rate', 'item tax %', 'igst rate', 'rate (%)'],
        'taxable_val': ['taxable value', 'item taxable value', 'total taxable value', 'taxable amount', 'principal amount'],
        'igst': ['igst', 'integrated tax amount', 'integrated tax', 'igst amount'],
        'cgst': ['cgst', 'central tax amount', 'central tax', 'cgst amount'],
        'sgst': ['sgst', 'state/ut tax amount', 'state tax', 'sgst amount']
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
            extracted = df[col_name].astype(str).str.extract(r'([+-]?\d+\.?\d*)')[0]
            return pd.to_numeric(extracted, errors='coerce').fillna(0.0)
        return 0.0

    std_df['POS'] = df[find_col('pos')] if find_col('pos') else 'Unknown'
    std_df['Rate'] = extract_pure_number(find_col('rate'))
    std_df['Taxable_Value'] = extract_pure_number(find_col('taxable_val'))
    std_df['IGST'] = extract_pure_number(find_col('igst'))
    std_df['CGST'] = extract_pure_number(find_col('cgst'))
    std_df['SGST'] = extract_pure_number(find_col('sgst'))

    std_df = std_df.dropna(how='all')
    std_df = std_df[std_df['Taxable_Value'] != 0]

    if std_df.empty: return std_df

    valid_slabs = [0, 5, 12, 18, 28]
    std_df['Rate'] = std_df['Rate'].apply(lambda x: min(valid_slabs, key=lambda slab: abs(slab - x)) if x > 0 else 0)

    tax_missing = (std_df['IGST'] == 0) & (std_df['CGST'] == 0) & (std_df['SGST'] == 0)
    is_up = std_df['POS'].astype(str).str.lower().str.contains('09|uttar pradesh|^up$')
    
    intra = tax_missing & is_up
    std_df.loc[intra, 'CGST'] = (std_df.loc[intra, 'Taxable_Value'] * std_df.loc[intra, 'Rate']) / 200
    std_df.loc[intra, 'SGST'] = (std_df.loc[intra, 'Taxable_Value'] * std_df.loc[intra, 'Rate']) / 200
    
    inter = tax_missing & ~is_up
    std_df.loc[inter, 'IGST'] = (std_df.loc[inter, 'Taxable_Value'] * std_df.loc[inter, 'Rate']) / 100

    if category == 'RETURN':
        for col in ['Taxable_Value', 'IGST', 'CGST', 'SGST']:
            std_df[col] = std_df[col].apply(lambda x: -abs(x) if x > 0 else x)

    return std_df

# ==========================================
# 3. UI AND EXECUTION
# ==========================================
st.header("1. Upload GSTR B2C Reports")
uploaded_files = st.file_uploader(
    "Upload Amazon & Flipkart GSTR Excel files", 
    type=['xlsx'], 
    accept_multiple_files=True
)

if uploaded_files:
    master_b2c = []
    
    for file in uploaded_files:
        try:
            excel_data = pd.read_excel(file, sheet_name=None)
            for tab_name, raw_df in excel_data.items():
                category = classify_tab(tab_name)
                if not category or raw_df.empty: continue

                clean_raw_df = find_true_header(raw_df)
                processed_df = extract_portal_data(clean_raw_df, category)
                
                if not processed_df.empty:
                    master_b2c.append(processed_df)
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")

    # ==========================================
    # 4. 1:1 PORTAL FORMAT MATCHING
    # ==========================================
    if master_b2c:
        merged_df = pd.concat(master_b2c, ignore_index=True)
        
        portal_ready_df = merged_df.groupby(['POS', 'Rate']).agg({
            'Taxable_Value': 'sum',
            'IGST': 'sum',
            'CGST': 'sum',
            'SGST': 'sum'
        }).reset_index()
        
        portal_ready_df = portal_ready_df[portal_ready_df['Taxable_Value'] != 0].round(2)
        
        # 1. ADD MISSING CESS COLUMN (Required by Portal)
        portal_ready_df['Cess'] = 0.0

        # 2. REORDER COLUMNS EXACTLY AS SHOWN IN THE PORTAL IMAGE
        portal_ready_df = portal_ready_df[['POS', 'Taxable_Value', 'Rate', 'IGST', 'CGST', 'SGST', 'Cess']]
        
        # 3. RENAME COLUMNS EXACTLY AS SHOWN IN THE PORTAL IMAGE (No extra symbols)
        portal_ready_df.rename(columns={
            'POS': 'Place of Supply (POS)',
            'Taxable_Value': 'Taxable Value',
            'Rate': 'Rate',
            'IGST': 'Integrated Tax',
            'CGST': 'Central Tax',
            'SGST': 'State/UT Tax',
            'Cess': 'Cess'
        }, inplace=True)

        st.success("🎯 Data Aggregated Successfully. Format is now a 1:1 match with the GST Portal.")
        
        st.header("2. Final Tax to Pay (Grand Totals)")
        total_taxable = portal_ready_df['Taxable Value'].sum()
        total_igst = portal_ready_df['Integrated Tax'].sum()
        total_cgst = portal_ready_df['Central Tax'].sum()
        total_sgst = portal_ready_df['State/UT Tax'].sum()
        total_tax = total_igst + total_cgst + total_sgst
        
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Taxable Value", f"₹ {total_taxable:,.2f}")
        col2.metric("Total IGST", f"₹ {total_igst:,.2f}")
        col3.metric("Total CGST", f"₹ {total_cgst:,.2f}")
        col4.metric("Total SGST", f"₹ {total_sgst:,.2f}")
        col5.metric("🔥 Total Tax Payable", f"₹ {total_tax:,.2f}")

        st.header("3. Exact Portal Sequence (Table 7)")
        st.markdown("You can now directly reference this table line-by-line for the portal.")
        st.dataframe(portal_ready_df, use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            portal_ready_df.to_excel(writer, sheet_name='Portal_B2C_Data', index=False)
            
        st.download_button(
            label="📥 Download 1:1 Portal-Ready Excel",
            data=output.getvalue(),
            file_name="Celvia_Portal_Exact_B2C.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("No valid B2C data found in the uploaded reports.")
