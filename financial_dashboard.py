import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import date

st.set_page_config(
    page_title="LeadAHead Electrical Financial Dashboard",
    layout="wide"
)

st.title("⚡ LeadAHead Electrical Financial Dashboard")


FILE = "ledger.xlsx"

# -------------------------------
# LOAD DATA (SAFE)
# -------------------------------


required_cols = [
    "Date", "Account Type", "Type", "Category",
    "Subcategory", "Entity", "Amount"
]

if os.path.exists(FILE):
    df = pd.read_excel(FILE, engine="openpyxl")

    # Add missing columns automatically
    for col in required_cols:
        if col not in df.columns:
            df[col] = None
else:
    df = pd.DataFrame(columns=required_cols)

# Normalize Date column
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

# Normalize Amount column
df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")


# -------------------------------
# INPUT FORM (NORMALIZED)
# -------------------------------
st.sidebar.header("➕ Add Transaction")

with st.sidebar.form("entry"):
    d = st.date_input("Date", value=date.today())

    acct_type = st.selectbox("Account Type", [
        "Revenue", "Expense", "Asset", "Liability", "Equity"
    ])

    t = st.selectbox("Type", ["Revenue", "Expense"])

    cat = st.selectbox("Category", [
        "Sales", "COGS", "Payroll", "OPEX", "Government",
        "Cash", "Bank", "Accounts Receivable", "Inventory", "Equipment",
        "Accounts Payable", "Loans Payable", "Accrued Expenses",
        "Owner's Equity", "Retained Earnings"
    ])

    subcat = st.text_input("Subcategory")
    entity = st.text_input("Entity")
    amount = st.number_input("Amount", min_value=0.0)
    submit = st.form_submit_button("Save")


# -------------------------------
# SAVE ENTRY
# -------------------------------
if submit:
    new_row = pd.DataFrame([{
        "Date": d,
        "Account Type": acct_type,
        "Type": t,
        "Category": cat,
        "Subcategory": subcat,
        "Entity": entity,
        "Amount": amount
    }])

    df = pd.concat([df, new_row], ignore_index=True)
    df.to_excel(FILE, index=False)

    st.success("Transaction saved!")

# -------------------------------
# DATA VIEW
# -------------------------------
st.header("📒 Ledger (Preview Only)")

# Normalize Date column
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

# How many rows to show
rows_to_show = st.slider("Rows to display", 10, 200, 50)

# Preview only
df_preview = df.head(rows_to_show)

# Display version with commas
df_preview_display = df_preview.copy()
df_preview_display["Amount"] = df_preview_display["Amount"].apply(lambda x: f"{x:,.2f}")

st.dataframe(df_preview_display, use_container_width=True)


# -------------------------------
# EDIT / DELETE ROW
# -------------------------------
st.subheader("✏️ Edit or Delete Transaction")

if not df.empty:
    row_to_edit = st.number_input(
        "Select row index to edit/delete",
        min_value=0,
        max_value=len(df)-1,
        step=1
    )

    st.write("Selected row:")
    st.write(df.iloc[row_to_edit])

    with st.form("edit_form"):
        new_date = st.date_input("Date", df.iloc[row_to_edit]["Date"])
        new_type = st.selectbox("Type", ["Revenue", "Expense"],
                                index=["Revenue","Expense"].index(df.iloc[row_to_edit]["Type"]))
        new_cat = st.text_input("Category", df.iloc[row_to_edit]["Category"])
        new_subcat = st.text_input("Subcategory", df.iloc[row_to_edit]["Subcategory"])
        new_entity = st.text_input("Entity", df.iloc[row_to_edit]["Entity"])
        new_amount = st.number_input("Amount", value=float(df.iloc[row_to_edit]["Amount"]))

        save_edit = st.form_submit_button("Save Changes")

    if save_edit:
        df.at[row_to_edit, "Date"] = pd.to_datetime(new_date)
        df.at[row_to_edit, "Type"] = new_type
        df.at[row_to_edit, "Category"] = new_cat
        df.at[row_to_edit, "Subcategory"] = new_subcat
        df.at[row_to_edit, "Entity"] = new_entity
        df.at[row_to_edit, "Amount"] = new_amount
        df.to_excel(FILE, index=False)
        st.success("Row updated!")

    if st.button("Delete This Row"):
        df = df.drop(index=row_to_edit).reset_index(drop=True)
        df.to_excel(FILE, index=False)
        st.warning("Row deleted!")


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

# Table version (formatted)
expense_by_cat_display = expense_by_cat.copy()
expense_by_cat_display["Amount"] = expense_by_cat_display["Amount"].apply(lambda x: f"{x:,.2f}")
st.dataframe(expense_by_cat_display)

# Pie chart version (numeric)
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

# Revenue
revenue = df[df["Account Type"] == "Revenue"]["Amount"].sum()

# COGS
cogs = df[(df["Account Type"] == "Expense") & (df["Category"] == "COGS")]["Amount"].sum()

# Gross Profit
gross_profit = revenue - cogs

# Operating Expenses (OPEX)
opex = df[(df["Account Type"] == "Expense") & (df["Category"] == "OPEX")]["Amount"].sum()

# Net Income
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
monthly_display["Revenue"] = monthly_display["Revenue"].apply(lambda x: f"{x:,.2f}")
monthly_display["Expense"] = monthly_display["Expense"].apply(lambda x: f"{x:,.2f}")
monthly_display["Net Income"] = monthly_display["Net Income"].apply(lambda x: f"{x:,.2f}")

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
# -------------------------------
# CASH FLOW STATEMENT (ACCOUNT TYPE LOGIC)
# -------------------------------
st.header("💵 Cash Flow Statement")

# Ensure Date is datetime
df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

# Sort by date so changes are chronological
df_sorted = df.sort_values("Date")

# Compute changes in each account type
assets = df_sorted[df_sorted["Account Type"] == "Asset"]["Amount"].sum()
liabilities = df_sorted[df_sorted["Account Type"] == "Liability"]["Amount"].sum()
equity = df_sorted[df_sorted["Account Type"] == "Equity"]["Amount"].sum()

# Cash Flow Rules:
# Asset increase  → Cash Outflow
# Asset decrease  → Cash Inflow
# Liability increase → Cash Inflow
# Liability decrease → Cash Outflow
# Equity increase → Cash Inflow (owner contribution)
# Equity decrease → Cash Outflow (owner withdrawal)

# Operating Cash Flow = Revenue - Expense
operating_in = df_sorted[df_sorted["Account Type"] == "Revenue"]["Amount"].sum()
operating_out = df_sorted[df_sorted["Account Type"] == "Expense"]["Amount"].sum()
operating_cf = operating_in - operating_out

# Investing Cash Flow = changes in long-term assets (Equipment, etc.)
investing_cf = -1 * df_sorted[df_sorted["Category"].isin(["Equipment", "Inventory"])]["Amount"].sum()

# Financing Cash Flow = changes in liabilities + equity
financing_cf = (
    df_sorted[df_sorted["Account Type"] == "Liability"]["Amount"].sum() +
    df_sorted[df_sorted["Account Type"] == "Equity"]["Amount"].sum()
)

# Total Cash Flow
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

st.download_button(
    "Download Excel Ledger",
    data=open(FILE, "rb").read() if os.path.exists(FILE) else b"",
    file_name="ledger.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
