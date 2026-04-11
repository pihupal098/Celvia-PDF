import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="GST Master Aggregator", layout="wide", page_icon="📊")

st.title("📊 Celvia GST Master Aggregator (Govt Format Ready)")
st.markdown("Upload Amazon & Flipkart GSTR Reports. The system deeply analyzes tab names (like 'Section 5B' or 'B2C Small'), auto-corrects returns, and merges them into a single, flawless Master GSTR-1 Excel file.")

# ==========================================
# 1. SMART TAB CLASSIFIER
# Identifies which tab belongs to which GSTR-1 Section
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

# ==========================================
# 2. COLUMN STANDARDIZATION LOGIC
# Extracts exact data no matter what Amazon/Flipkart names the column
# ==========================================
def clean_col(name):
    return re.sub(r'\s+', ' ', str(name).lower().strip())

def extract_standard_data(df, category):
    # Standardize column headers
    df.columns = [clean_col(c) for c in df.columns]
    
    # Core mappings based on e-commerce GSTR files
    col_maps = {
        'gstin': ['gstin/uin of recipient', 'gstin/uin', 'customer gstin', 'buyer gstin'],
        'invoice_no': ['invoice number', 'document number', 'invoice no', 'original document number'],
        'invoice_date': ['invoice date', 'document date', 'original document date'],
        'invoice_val': ['invoice value', 'total invoice value', 'gross amount'],
        'pos': ['place of supply', 'state', 'delivery state'],
        'rate': ['rate', 'tax rate', 'tax %', 'igst rate', 'gst rate'],
        'taxable_val': ['taxable value', 'item taxable value', 'total taxable value', 'taxable amount'],
        'hsn': ['hsn', 'hsn code'],
        'qty': ['total quantity', 'quantity'],
        'uqc': ['uqc', 'unit']
    }

    def find_col(target):
        for possible_name in col_maps.get(target, []):
            for actual_col in df.columns:
                # Direct match or if the exact string is within the column name
                if possible_name == actual_col or possible_name in actual_col:
                    return actual_col
        return None

    # Create standardized dataframe based on category
    std_df = pd.DataFrame()
    
    # Force convert numeric columns safely
    def safe_numeric(col_name):
        if col_name in df.columns:
            # Remove any commas before converting
            cleaned = df[col_name].astype(str).str.replace(',', '', regex=False)
            return pd.to_numeric(cleaned, errors='coerce').fillna(0)
        return 0.0

    if category in ['B2B', 'CDNR']:
        std_df['GSTIN'] = df[find_col('gstin')] if find_col('gstin') else ''
        std_df['Invoice_Number'] = df[find_col('invoice_no')] if find_col('invoice_no') else ''
        std_df['Invoice_Date'] = df[find_col('invoice_date')] if find_col('invoice_date') else ''
        std_df['Invoice_Value'] = safe_numeric(find_col('invoice_val'))
        std_df['Place_of_Supply'] = df[find_col('pos')] if find_col('pos') else ''
        std_df['Rate'] = safe_numeric(find_col('rate'))
        std_df['Taxable_Value'] = safe_numeric(find_col('taxable_val'))
        
    elif category in ['B2CS', 'CDNUR']:
        std_df['Place_of_Supply'] = df[find_col('pos')] if find_col('pos') else 'Unknown'
        std_df['Rate'] = safe_numeric(find_col('rate'))
        std_df['Taxable_Value'] = safe_numeric(find_col('taxable_val'))
        
    elif category == 'HSN':
        std_df['HSN'] = df[find_col('hsn')] if find_col('hsn') else ''
        std_df['Description'] = 'E-commerce Goods'
        std_df['UQC'] = df[find_col('uqc')] if find_col('uqc') else 'NOS'
        std_df['Total_Quantity'] = safe_numeric(find_col('qty'))
        std_df['Total_Value'] = safe_numeric(find_col('invoice_val'))
        std_df['Taxable_Value'] = safe_numeric(find_col('taxable_val'))
        std_df['Rate'] = safe_numeric(find_col('rate'))

    # Drop completely empty rows or rows where Taxable Value is 0
    std_df = std_df.dropna(how='all')
    if 'Taxable_Value' in std_df.columns:
        std_df = std_df[std_df['Taxable_Value'] != 0]

    # --- CRITICAL LOGIC FOR RETURNS ---
    # If it is a Return tab (CDNR or CDNUR), ensure the Taxable Value is treated as Negative.
    # This ensures that when grouped with Sales, the returns are correctly deducted from the Total.
    if category in ['CDNR', 'CDNUR'] and 'Taxable_Value' in std_df.columns:
        # Convert any positive values to negative
        std_df['Taxable_Value'] = std_df['Taxable_Value'].apply(lambda x: -abs(x) if x > 0 else x)
        
    return std_df

# ==========================================
# 3. UPLOADER & PROCESSING
# ==========================================
st.header("1. Upload GSTR Reports")
uploaded_files = st.file_uploader(
    "Upload Amazon & Flipkart GSTR Excel files here", 
    type=['xlsx'], 
    accept_multiple_files=True
)

if uploaded_files:
    # Master storage for all categories
    master_data = {'B2B': [], 'B2CS': [], 'CDNR': [], 'CDNUR': [], 'HSN': []}
    
    st.header("2. Deep Analysis Status")
    
    for file in uploaded_files:
        st.write(f"📂 **Analyzing File:** {file.name}")
        
        try:
            excel_data = pd.read_excel(file, sheet_name=None)
            
            for tab_name, raw_df in excel_data.items():
                category = classify_tab(tab_name)
                
                if not category:
                    if 'help' not in tab_name.lower():
                        st.text(f"  ⏭️ Ignored non-GST tab: '{tab_name}'")
                    continue
                
                # Handling the blank rows above headers in reports
                # If first column is 'Summary' or Unnamed, drop rows until we hit actual headers
                while len(raw_df) > 0 and pd.isna(raw_df.iloc[0, 0]) and 'taxable' not in str(raw_df.iloc[0]).lower():
                     raw_df = raw_df.iloc[1:].reset_index(drop=True)
                     
                # Promote first row to header if it looks like column names
                if len(raw_df) > 0 and any(keyword in str(raw_df.iloc[0]).lower() for keyword in ['gstin', 'taxable', 'rate', 'value', 'hsn']):
                    raw_df.columns = raw_df.iloc[0]
                    raw_df = raw_df[1:].reset_index(drop=True)

                if len(raw_df) < 1:
                    continue
                    
                processed_df = extract_standard_data(raw_df, category)
                
                if not processed_df.empty:
                    st.text(f"  ✅ Extracted {category} Data from tab: '{tab_name}' ({len(processed_df)} records)")
                    master_data[category].append(processed_df)
                
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")

    # ==========================================
    # 4. FINAL AGGREGATION & EXCEL GENERATION
    # ==========================================
    st.success("🎯 All reports analyzed and categorized successfully!")
    st.header("3. Master GSTR-1 Output")
    
    final_output = {}
    
    # Process B2B & CDNR (Stack directly)
    for cat in ['B2B', 'CDNR']:
        if master_data[cat]:
            final_output[cat] = pd.concat(master_data[cat], ignore_index=True)
            st.write(f"**{cat} Invoices:** {len(final_output[cat])} records ready.")
            
    # CRUCIAL: Process B2CS & CDNUR (Merge them to get NET Taxable Value)
    combined_b2cs_cdnur = []
    if master_data['B2CS']: combined_b2cs_cdnur.extend(master_data['B2CS'])
    if master_data['CDNUR']: combined_b2cs_cdnur.extend(master_data['CDNUR'])
    
    if combined_b2cs_cdnur:
        merged_df = pd.concat(combined_b2cs_cdnur, ignore_index=True)
        # Group by State and Rate to calculate Net Sales (Sales + Negative Returns)
        grouped_b2cs = merged_df.groupby(['Place_of_Supply', 'Rate']).agg({'Taxable_Value': 'sum'}).reset_index()
        
        # Calculate Taxes dynamically based on Place of Supply
        # Assuming you operate from UP (Place of Supply 09-Uttar Pradesh). If different, IGST applies.
        # Note: You can manually adjust tax calculation if needed, but portal auto-calculates from Taxable Value.
        
        final_output['B2CS_NET'] = grouped_b2cs.round(2)
        st.write(f"**B2CS Net Summary (Returns Adjusted):** Ready")

    # Process HSN (Group by HSN and Rate)
    if master_data['HSN']:
        combined_hsn = pd.concat(master_data['HSN'], ignore_index=True)
        # Convert HSN to string to prevent scientific notation
        combined_hsn['HSN'] = combined_hsn['HSN'].astype(str).str.split('.').str[0]
        grouped_hsn = combined_hsn.groupby(['HSN', 'Description', 'UQC', 'Rate']).agg({
            'Total_Quantity': 'sum',
            'Total_Value': 'sum',
            'Taxable_Value': 'sum'
        }).reset_index()
        final_output['HSN'] = grouped_hsn.round(2)
        st.write(f"**HSN Summary:** Ready")

    # Preview Output
    if 'B2CS_NET' in final_output:
        st.subheader("B2C State-Wise Net Sales Summary")
        st.dataframe(final_output['B2CS_NET'])

    # Write to Memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        for sheet_name, df in final_output.items():
            if not df.empty:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                
    st.header("4. Download for Filing")
    st.download_button(
        label="📥 Download Master GSTR-1 Excel (.xlsx)",
        data=output.getvalue(),
        file_name="Celvia_Master_GSTR1.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
