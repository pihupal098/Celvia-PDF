import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="GST Master Aggregator", layout="wide", page_icon="📊")

st.title("📊 Celvia GST Master Aggregator (Anti-Blank Version)")
st.markdown("This version features a Deep Header Scanner to bypass any summary text or blank rows at the top of Amazon/Flipkart reports, ensuring no data is missed.")

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

# ==========================================
# 2. DEEP HEADER SCANNER (FIX FOR BLANK EXCEL)
# ==========================================
def find_true_header(df):
    """Scans the first 15 rows to find the actual table headers"""
    for i in range(min(15, len(df))):
        # Convert the entire row to a lowercase string to check for keywords
        row_str = str(df.iloc[i].values).lower()
        
        # If the row contains combinations of these words, it's the real header
        if ('taxable' in row_str or 'invoice' in row_str or 'gstin' in row_str) and ('rate' in row_str or 'value' in row_str or 'amount' in row_str):
            # Make this row the header
            df.columns = df.iloc[i].astype(str).str.lower().str.strip()
            # Drop this row and everything above it
            return df.iloc[i+1:].reset_index(drop=True)
    
    # Fallback if no clear header found
    df.columns = df.columns.astype(str).str.lower().str.strip()
    return df

# ==========================================
# 3. COLUMN STANDARDIZATION LOGIC
# ==========================================
def clean_col(name):
    return re.sub(r'\s+', ' ', str(name).lower().strip())

def extract_standard_data(df, category):
    df.columns = [clean_col(c) for c in df.columns]
    
    col_maps = {
        'gstin': ['gstin', 'uin'],
        'invoice_no': ['invoice number', 'document number', 'invoice no'],
        'invoice_date': ['invoice date', 'document date'],
        'invoice_val': ['invoice value', 'gross amount', 'total value'],
        'pos': ['place of supply', 'state', 'delivery state'],
        'rate': ['rate', 'tax %', 'igst rate', 'gst rate', 'tax rate'],
        'taxable_val': ['taxable value', 'taxable amount', 'item taxable'],
        'hsn': ['hsn'],
        'qty': ['quantity', 'qty', 'total quantity'],
        'uqc': ['uqc', 'unit']
    }

    def find_col(target):
        for possible_name in col_maps.get(target, []):
            for actual_col in df.columns:
                if possible_name in actual_col:
                    return actual_col
        return None

    std_df = pd.DataFrame()
    
    def safe_numeric(col_name):
        if col_name and col_name in df.columns:
            cleaned = df[col_name].astype(str).str.replace(',', '', regex=False).str.replace('Rs.', '', regex=False)
            return pd.to_numeric(cleaned, errors='coerce').fillna(0)
        return 0.0

    # Map the columns safely
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

    # Drop blank rows
    std_df = std_df.dropna(how='all')
    
    # Safely filter out zero values (if Taxable_Value column exists and mapped correctly)
    if 'Taxable_Value' in std_df.columns:
        std_df = std_df[std_df['Taxable_Value'] != 0]

    # Negative adjustment for Returns
    if category in ['CDNR', 'CDNUR'] and 'Taxable_Value' in std_df.columns:
        std_df['Taxable_Value'] = std_df['Taxable_Value'].apply(lambda x: -abs(x) if x > 0 else x)
        
    return std_df

# ==========================================
# 4. UPLOADER & PROCESSING
# ==========================================
st.header("1. Upload GSTR Reports")
uploaded_files = st.file_uploader(
    "Upload Amazon & Flipkart GSTR Excel files here", 
    type=['xlsx'], 
    accept_multiple_files=True
)

if uploaded_files:
    master_data = {'B2B': [], 'B2CS': [], 'CDNR': [], 'CDNUR': [], 'HSN': []}
    
    st.header("2. Deep Analysis Status")
    
    for file in uploaded_files:
        st.write(f"📂 **Analyzing File:** {file.name}")
        
        try:
            excel_data = pd.read_excel(file, sheet_name=None)
            
            for tab_name, raw_df in excel_data.items():
                category = classify_tab(tab_name)
                
                if not category:
                    if 'help' not in tab_name.lower() and 'summary' not in tab_name.lower():
                        st.text(f"  ⏭️ Ignored non-GST tab: '{tab_name}'")
                    continue

                if raw_df.empty or len(raw_df) < 1:
                    continue

                # Pass through the Deep Header Scanner
                clean_raw_df = find_true_header(raw_df)
                    
                processed_df = extract_standard_data(clean_raw_df, category)
                
                if not processed_df.empty:
                    st.success(f"  ✅ Extracted {category} Data from tab: '{tab_name}' ({len(processed_df)} records)")
                    master_data[category].append(processed_df)
                else:
                    st.warning(f"  ⚠️ Tab '{tab_name}' was read, but no valid sales data was found (values were 0 or columns didn't match).")
                
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")

    # ==========================================
    # 5. FINAL AGGREGATION & EXCEL GENERATION
    # ==========================================
    # Check if we have ANY data at all
    has_data = any(len(v) > 0 for v in master_data.values())
    
    if has_data:
        st.success("🎯 All reports analyzed and categorized successfully!")
        st.header("3. Master GSTR-1 Output")
        
        final_output = {}
        
        # Process B2B & CDNR
        for cat in ['B2B', 'CDNR']:
            if master_data[cat]:
                final_output[cat] = pd.concat(master_data[cat], ignore_index=True)
                st.write(f"**{cat} Invoices:** {len(final_output[cat])} records ready.")
                
        # Process B2CS & CDNUR (Merged)
        combined_b2cs = master_data['B2CS'] + master_data['CDNUR']
        
        if combined_b2cs:
            merged_df = pd.concat(combined_b2cs, ignore_index=True)
            grouped_b2cs = merged_df.groupby(['Place_of_Supply', 'Rate']).agg({'Taxable_Value': 'sum'}).reset_index()
            # Filter out zero sums resulting from perfectly cancelled orders
            grouped_b2cs = grouped_b2cs[grouped_b2cs['Taxable_Value'] != 0]
            final_output['B2CS_NET'] = grouped_b2cs.round(2)
            st.write(f"**B2CS Net Summary (Returns Adjusted):** Ready")

        # Process HSN
        if master_data['HSN']:
            combined_hsn = pd.concat(master_data['HSN'], ignore_index=True)
            combined_hsn['HSN'] = combined_hsn['HSN'].astype(str).str.split('.').str[0]
            grouped_hsn = combined_hsn.groupby(['HSN', 'Description', 'UQC', 'Rate']).agg({
                'Total_Quantity': 'sum', 'Total_Value': 'sum', 'Taxable_Value': 'sum'
            }).reset_index()
            final_output['HSN'] = grouped_hsn.round(2)
            st.write(f"**HSN Summary:** Ready")

        # Display Preview
        if 'B2CS_NET' in final_output:
            st.subheader("B2C State-Wise Net Sales Summary")
            st.dataframe(final_output['B2CS_NET'])
        elif 'B2B' in final_output:
             st.subheader("B2B Invoice Summary")
             st.dataframe(final_output['B2B'].head())

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
    else:
        st.error("❌ No data could be processed. Please check if the uploaded files contain valid GST data.")
