import os
import pdfplumber
import re
import pandas as pd
from openpyxl import load_workbook
import json
from openpyxl.chart import LineChart, Reference

start_balance = 7820
tax_bill = 7056.60 - 353

summary_file = "/Users/danielmchugh/Library/Mobile Documents/iCloud~dk~simonbs~Scriptable/Documents/payslipsummary.json"
folder_path = "payslips"
file_path = "/Users/danielmchugh/Documents/Oz/LGC Rail Services/Payslips/all_payslips.xlsx"

def upload_paylsip_data():

    rows = []
    for file in os.listdir(folder_path):
        if file.endswith(".pdf"):
            pdf_path = os.path.join(folder_path, file)
            with pdfplumber.open(pdf_path) as pdf:
                text = pdf.pages[0].extract_text()

            dateEnd = re.search(r"Period Ending[:\s]*([\d]{2}/[\d]{2}/[\d]{4})", text)
            hoursx1 = re.search(r"Hours Paid[:\s]*([\d]+)", text)
            hoursx1_5 = re.search(r"Rail - Casual Ordinary Hours 1.5[:\s](\d)", text)
            hoursx2 = re.search(r"Rail - Casual Ordinary Hours 2x[:\s](\d)", text)
            gross = re.search(r"Gross Earnings[:\s]*\$?([\d,\.]+)", text)
            net = re.search(r"Net Payment[:\s]*\$?([\d,\.]+)", text)

            rows.append({
                "File": file,
                "Week Ending": dateEnd.group(1) if dateEnd else None,
                "Gross Pay": float(gross.group(1).replace(",","")) if gross else None,
                "Net Pay": float(net.group(1).replace(",","")) if net else None,
                "Ordinary Hours Worked": int(hoursx1.group(1)) if hoursx1 else None,
                "1.5x Hours Worked": float(hoursx1_5.group(1).replace(",","")) if hoursx1_5 else None,
                "2x Hours Worked": float(hoursx2.group(1).replace(",","")) if hoursx2 else None
            })

    df = pd.DataFrame(rows)
    df["Week Ending"] = pd.to_datetime(df["Week Ending"], dayfirst=True)
    df = df.sort_values(by="Week Ending", ascending=True).reset_index(drop=True)

    # df["Remaining Visa Balance"] = start_balance
    target_row = 11
    tax_balance = tax_bill
    balance = start_balance
    for idx in range(target_row, len(df)):
        net = df.at[idx, "Net Pay"]

        if pd.notnull(net):
            net = float(net)
            balance -= net
            df.at[idx, "Remaining Visa Balance"] = round(balance, 2)
            tax_balance -= 90
            df.at[idx, "Tax Bill Balance"] = tax_balance

    df["Week Ending"] = df["Week Ending"].dt.strftime("%d/%m/%Y")

    total_row = {
        "File": "TOTAL",
        "Week Ending": pd.NaT,
        "Gross Pay": df["Gross Pay"].sum(),
        "Net Pay": df["Net Pay"].sum(),
        "Ordinary Hours Worked": df["Ordinary Hours Worked"].sum(),
        "1.5x Hours Worked": df["1.5x Hours Worked"].sum(),
        "2x Hours Worked": df["2x Hours Worked"].sum(),
        "Remaining Visa Balance": ""  # optional
    }

    df_total = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)
    df_total.to_excel(file_path, index=False)

    def create_net_pay_chart(file_path):
        wb = load_workbook(file_path)
        ws = wb.active

        chart = LineChart()
        chart.title = "Net Pay Over Time"
        chart.style = 2
        chart.y_axis.title = "Net Pay ($)"
        chart.x_axis.title = "Week Ending"

        data = Reference(ws, min_col=4, min_row=1, max_row=ws.max_row-1)
        dates = Reference(ws, min_col=2, min_row=2, max_row=ws.max_row-1)

        chart.add_data(data, titles_from_data=True)
        chart.set_categories(dates)

        chart.height = 10
        chart.width = 20

        ws.add_chart(chart, "I20")
        wb.save(file_path)

    create_net_pay_chart(file_path)

    def auto_adjust_column_width(file_path: str):
        wb = load_workbook(file_path)
        ws = wb.active

        for col in ws.columns:
            max_length = 0
            col_letter = col[0].column_letter  # Get the column name
            for cell in col:
                try:
                    if cell.value:
                        length = len(str(cell.value))
                        if length > max_length:
                            max_length = length
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[col_letter].width = adjusted_width

        wb.save(file_path)

    auto_adjust_column_width(file_path)

    latest = df[df["File"] != "Total"].iloc[-1]
    latest_balance = float(df[df["File"] != "Total"].iloc[-1]["Remaining Visa Balance"])

    weeks_left = latest_balance / latest["Net Pay"]
    weeks_tax_remaining = tax_balance / 90
    summary = {
        "latest_week": latest["Week Ending"],
        "latest_net": float(latest["Net Pay"]),
        "visa_remaining": float(latest_balance),
        "weeks_until_paid": round(float(weeks_left), 2),
        "tax_remaining": float(tax_balance),
        "weeks_tax_remaining": round(float(weeks_tax_remaining),2)
    }

    with open(summary_file,"w") as f:
        json.dump(summary, f, indent=2)

upload_paylsip_data()

    
