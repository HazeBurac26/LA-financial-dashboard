import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from io import BytesIO
from prophet import Prophet

import gspread
from google.oauth2.service_account import Credentials

# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(
    page_title="LeadAHead Electrical Financial Dashboard",
    layout="wide"
)

st.title("⚡ LeadAHead Electrical Financial Dashboard")

# -------------------------------
# GOOGLE SHEETS SETUP
# -------------------------------
required_cols = [
    "Date", "Account Type", "Type", "Category",
    "Subcategory", "Entity", "Amount"
]

creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)

client = gspread.authorize(creds)

# Use your sheet ID
sheet = client.open_by_key("1hRkL3IDdhNfF4rtsVOMDDhMX2sxOoSEi6IEX8K_pO1Y").sheet1

# Load data
data = sheet.get_all_records()
df = pd.DataFrame(data)

# Ensure required columns exist
for col in required_cols:
    if col not in df.columns:
        df[col] = None

# Normalize types
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

# -------------------------------
# INPUT FORM (ADD TRANSACTION)
# -------------------------------

st.sidebar.header("➕ Add Transaction")

with st.sidebar.form("entry"):
    d = st.date_input("Date", value=date.today())

    acct_type = st.selectbox("Account Type", [
        "Revenue", "Expense", "Asset", "Liability", "Equity"
    ])

    # Auto-set Type
    if acct_type in ["Revenue", "Expense"]:
        t = acct_type
    else:
        t = ""

    cat = st.selectbox("Category", [
        "Sales", "COGS", "Payroll", "OPEX", "Government",
        "Cash", "Bank", "Accounts Receivable", "Inventory", "Equipment",
        "Accounts Payable", "Loans Payable", "Accrued Expenses",
        "Owner's Equity", "Retained Earnings"
    ])

    subcat = st.text_input("Subcategory")
    entity = st.text_input("Entity")
    amt = st.number_input("Amount", min_value=0.0, format="%.2f")

    submitted = st.form_submit_button("Add Transaction")

    if submitted:
        new_row = [
            str(d),
            acct_type,
            t,
            cat,
            subcat,
            entity,
            float(amt)
        ]

        sheet.append_row(new_row)
        st.success("Transaction added!")
        st.rerun()


# -------------------------------
# DATA VIEW
# -------------------------------
st.header("📒 Ledger (Preview Only)")

rows_to_show = st.slider("Rows to display", 10, 200, 50)
df_preview = df.head(rows_to_show)

df_preview_display = df_preview.copy()
df_preview_display["Amount"] = df_preview_display["Amount"].apply(
    lambda x: f"{x:,.2f}" if pd.notnull(x) else ""
)

st.dataframe(df_preview_display, use_container_width=True)

# -------------------------------
# EDIT / DELETE ROW (GOOGLE SHEETS)
# -------------------------------
st.subheader("✏️ Edit or Delete Transaction")

if not df.empty:
    row_to_edit = st.number_input(
        "Select row index to edit/delete",
        min_value=0,
        max_value=len(df) - 1,
        step=1
    )

    st.write("Selected row:")
    st.write(df.iloc[row_to_edit])

    # Google Sheets row number (header is row 1)
    sheet_row = row_to_edit + 2

    with st.form("edit_form"):
        current_row = df.iloc[row_to_edit]

        new_date = st.date_input(
            "Date",
            current_row["Date"].date() if pd.notnull(current_row["Date"]) else date.today()
        )

        # Type is derived from Account Type; show as read-only text
        st.write(f"Type: {current_row['Type']}")

        new_cat = st.text_input("Category", current_row["Category"])
        new_subcat = st.text_input("Subcategory", current_row["Subcategory"])
        new_entity = st.text_input("Entity", current_row["Entity"])
        new_amount = st.number_input(
            "Amount",
            value=float(current_row["Amount"]) if pd.notnull(current_row["Amount"]) else 0.0
        )

        save_edit = st.form_submit_button("Save Changes")

    if save_edit:
        # Update DataFrame
        df.at[row_to_edit, "Date"] = pd.to_datetime(new_date)
        df.at[row_to_edit, "Category"] = new_cat
        df.at[row_to_edit, "Subcategory"] = new_subcat
        df.at[row_to_edit, "Entity"] = new_entity
        df.at[row_to_edit, "Amount"] = new_amount

        # Prepare row for Google Sheets (must match column order)
        updated_row = [
            str(new_date),
            df.at[row_to_edit, "Account Type"],
            df.at[row_to_edit, "Type"],
            new_cat,
            new_subcat,
            new_entity,
            float(new_amount)
        ]

        sheet.update(f"A{sheet_row}:G{sheet_row}", [updated_row])
        st.success("Row updated in Google Sheets! Refresh to see changes.")

    if st.button("Delete This Row"):
        sheet.delete_rows(sheet_row)
        st.warning("Row deleted from Google Sheets! Refresh to see changes.")

# -------------------------------
# EXPENSE BREAKDOWN BY CATEGORY
# -------------------------------
st.header("💸 Expense Breakdown by Category")

expense_by_cat = (
    df[df["Account Type"] == "Expense"]
    .groupby("Category")["Amount"]
    .sum()
    .reset_index()
    .sort_values("Amount", ascending=False)
)

expense_by_cat_display = expense_by_cat.copy()
expense_by_cat_display["Amount"] = expense_by_cat_display["Amount"].apply(
    lambda x: f"{x:,.2f}" if pd.notnull(x) else ""
)
st.dataframe(expense_by_cat_display)

fig = px.pie(
    expense_by_cat,
    names="Category",
    values="Amount",
    title="Expense Breakdown by Category"
)
st.plotly_chart(fig)

# -------------------------------
# INCOME STATEMENT (GROSS PROFIT, OPEX, NET INCOME)
# -------------------------------
st.header("📊 Income Statement Breakdown")

revenue = df[df["Account Type"] == "Revenue"]["Amount"].sum()
cogs = df[(df["Account Type"] == "Expense") & (df["Category"] == "COGS")]["Amount"].sum()
gross_profit = revenue - cogs
opex = df[(df["Account Type"] == "Expense") & (df["Category"] == "OPEX")]["Amount"].sum()
net_income = gross_profit - opex

st.metric("Revenue", f"{revenue:,.2f}")
st.metric("COGS", f"{cogs:,.2f}")
st.metric("Gross Profit", f"{gross_profit:,.2f}")
st.metric("Operating Expenses (OPEX)", f"{opex:,.2f}")
st.metric("Net Income", f"{net_income:,.2f}")

# -------------------------------
# MONTHLY INCOME STATEMENT
# -------------------------------
st.header("📅 Monthly Income Statement")

df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df["Month"] = df["Date"].dt.to_period("M")

monthly = df.groupby(["Month", "Type"])["Amount"].sum().unstack().fillna(0)
monthly["Net Income"] = monthly.get("Revenue", 0) - monthly.get("Expense", 0)

monthly_display = monthly.copy()
for col in ["Revenue", "Expense", "Net Income"]:
    if col in monthly_display.columns:
        monthly_display[col] = monthly_display[col].apply(lambda x: f"{x:,.2f}")

st.dataframe(monthly_display)

# -------------------------------
# YTD INCOME STATEMENT
# -------------------------------
st.header("📆 YTD Income Statement")

current_year = date.today().year
df_ytd = df[df["Date"].dt.year == current_year]

ytd_revenue = df_ytd[df_ytd["Type"] == "Revenue"]["Amount"].sum()
ytd_expense = df_ytd[df_ytd["Type"] == "Expense"]["Amount"].sum()
ytd_net = ytd_revenue - ytd_expense

st.metric("YTD Revenue", f"{ytd_revenue:,.2f}")
st.metric("YTD Expense", f"{ytd_expense:,.2f}")
st.metric("YTD Net Income", f"{ytd_net:,.2f}")

# -------------------------------
# BALANCE SHEET (SIMPLE)
# -------------------------------
st.header("📄 Balance Sheet (Simple)")

assets = df[df["Account Type"] == "Asset"]["Amount"].sum()
liabilities = df[df["Account Type"] == "Liability"]["Amount"].sum()
equity = df[df["Account Type"] == "Equity"]["Amount"].sum()

bs_df = pd.DataFrame({
    "Item": ["Assets", "Liabilities", "Equity"],
    "Amount": [assets, liabilities, equity]
})

bs_df["Amount"] = bs_df["Amount"].apply(lambda x: f"{x:,.2f}")
st.dataframe(bs_df, use_container_width=True)

# -------------------------------
# CASH FLOW STATEMENT
# -------------------------------
st.header("💵 Cash Flow Statement")

df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
df_sorted = df.sort_values("Date")

operating_in = df_sorted[df_sorted["Account Type"] == "Revenue"]["Amount"].sum()
operating_out = df_sorted[df_sorted["Account Type"] == "Expense"]["Amount"].sum()
operating_cf = operating_in - operating_out

investing_cf = -1 * df_sorted[df_sorted["Category"].isin(["Equipment", "Inventory"])]["Amount"].sum()

financing_cf = (
    df_sorted[df_sorted["Account Type"] == "Liability"]["Amount"].sum() +
    df_sorted[df_sorted["Account Type"] == "Equity"]["Amount"].sum()
)

net_cash_flow = operating_cf + investing_cf + financing_cf

cf_df = pd.DataFrame({
    "Item": ["Operating Cash Flow", "Investing Cash Flow", "Financing Cash Flow", "Net Cash Flow"],
    "Amount": [operating_cf, investing_cf, financing_cf, net_cash_flow]
})

cf_df["Amount"] = cf_df["Amount"].apply(lambda x: f"{x:,.2f}")
st.dataframe(cf_df, use_container_width=True)

# -------------------------------
# EXPORT
# -------------------------------
st.header("📤 Export")

output = BytesIO()
df.to_excel(output, index=False)
output.seek(0)

st.download_button(
    "Download Excel Ledger",
    data=output,
    file_name="ledger.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

def prepare_monthly_data(df):
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df = df.dropna(subset=['Date'])

    df['Month'] = df['Date'].dt.to_period('M').dt.to_timestamp()

    revenue = df[df['Account Type'] == 'Revenue'].groupby('Month')['Amount'].sum()
    expense = df[df['Account Type'] == 'Expense'].groupby('Month')['Amount'].sum()

    net_income = revenue - expense

    monthly_df = pd.DataFrame({
        'ds': net_income.index,   # Prophet requires 'ds'
        'y': net_income.values    # Prophet requires 'y'
    })

    return monthly_df


def forecast_net_income(df):
    if len(df) < 2:
        return None

    # Ensure proper datetime format and sorted order
    df = df.sort_values("ds").reset_index(drop=True)
    df['ds'] = pd.to_datetime(df['ds'])

    model = Prophet()
    model.fit(df)

    # Use MS = Month Start (Prophet-friendly)
    future = model.make_future_dataframe(periods=3, freq='MS')
    forecast = model.predict(future)

    # Rename columns to management-friendly labels
    forecast = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
    forecast = forecast.rename(columns={
        'ds': 'Forecast Month',
        'yhat': 'Projected Net Income',
        'yhat_lower': 'Conservative Estimate',
        'yhat_upper': 'Optimistic Estimate'
    })

    # Format numbers with commas and 2 decimals
    for col in ['Projected Net Income', 'Conservative Estimate', 'Optimistic Estimate']:
        forecast[col] = forecast[col].apply(lambda x: float(f"{x:.2f}"))

    return forecast




st.header("📈 AI Forecast (Next 3 Months)")

monthly_df = prepare_monthly_data(df)
forecast = forecast_net_income(monthly_df)

if forecast is None:
    st.info("Not enough data to generate a forecast yet.")
else:
    # Line chart using management-friendly labels
    chart_df = forecast.copy()
    chart_df = chart_df.set_index('Forecast Month')

    st.line_chart(chart_df['Projected Net Income'])

    # Display formatted table
    display_df = forecast.copy()
    for col in ['Projected Net Income', 'Conservative Estimate', 'Optimistic Estimate']:
        display_df[col] = display_df[col].apply(lambda x: f"{x:,.2f}")

    st.dataframe(display_df)

