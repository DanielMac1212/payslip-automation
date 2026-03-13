import os
import pdfplumber
import re
import pandas as pd
import json

folder_path = "payslips"
summary_file = "payslipsummary.json"

start_balance = 7820
tax_bill = 7056.60 - 353


def extract_payslip_data(pdf_path):
    
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text()

    dateEnd = re.search(r"Period Ending[:\s]*([\d]{2}/[\d]{2}/[\d]{4})", text)
    hoursx1 = re.search(r"Hours Paid[:\s]*([\d]+)", text)
    hoursx1_5 = re.search(r"Rail - Casual Ordinary Hours 1.5[:\s]*([\d\.]+)", text)
    hoursx2 = re.search(r"Rail - Casual Ordinary Hours 2x[:\s]*([\d\.]+)", text)
    gross = re.search(r"Gross Earnings[:\s]*\$?([\d,\.]+)", text)
    net = re.search(r"Net Payment[:\s]*\$?([\d,\.]+)", text)

    week_ending = None
    if dateEnd:
        week_ending = pd.to_datetime(dateEnd.group(1), dayfirst=True).strftime("%d-%m-%Y")
                                        
    return {
        "File": os.path.basename(pdf_path),
        "Week Ending": week_ending,
        "Gross Pay": float(gross.group(1).replace(",", "")) if gross else None,
        "Net Pay": float(net.group(1).replace(",", "")) if net else None,
        "Ordinary Hours Worked": int(hoursx1.group(1)) if hoursx1 else None,
        "1.5x Hours Worked": float(hoursx1_5.group(1)) if hoursx1_5 else None,
        "2x Hours Worked": float(hoursx2.group(1)) if hoursx2 else None
    }


def load_existing_data():

    if not os.path.exists(summary_file):
        return []

    if os.path.getsize(summary_file) == 0:
        return []
    
    with open(summary_file, "r") as f:
        try:
            data = json.load(f)
            return data.get("payslips", [])
        except json.JSONDecodeError:
            return []
            
    return data.get("payslips", [])


def calculate_balances(payslips):

    df = pd.DataFrame(payslips).replace({pd.NA: None})
    df["Week Ending"] = pd.to_datetime(df["Week Ending"], dayfirst=True)
    df = df.sort_values("Week Ending").reset_index(drop=True)
    df = df.where(pd.notnull(df), None)

    balance = start_balance
    tax_balance = tax_bill

    df["Remaining Visa Balance"] = None
    df["Tax Bill Balance"] = None

    target_row = 11

    for idx in range(target_row, len(df)):
        net = df.at[idx, "Net Pay"]

        if pd.notnull(net):
            balance -= net
            tax_balance -= 90

            df.at[idx, "Remaining Visa Balance"] = round(balance, 2)
            df.at[idx, "Tax Bill Balance"] = round(tax_balance, 2)

    df["Week Ending"] = df["Week Ending"].dt.strftime("%d/%m/%Y")

    return df


def main():

    existing_payslips = load_existing_data()

    processed_files = {p["File"] for p in existing_payslips}

    new_entries = []

    pdf_files = [f for f in os.listdir("payslips") if f.endswith(".pdf")]
    
    for file in pdf_files:

        if file in processed_files:
            continue

        pdf_path = os.path.join(folder_path, file)

        try:
            data = extract_payslip_data(pdf_path)
            new_entries.append(data)

        except Exception as e:
            print(f"Skipping {file}: {e}")
            continue

    all_payslips = existing_payslips + new_entries

    if not all_payslips:
        print("No payslips found.")
        return

    df = calculate_balances(all_payslips)

    latest = df.iloc[-1]

    latest_balance = latest["Remaining Visa Balance"]
    tax_balance = latest["Tax Bill Balance"]

    weeks_left = None
    weeks_tax_remaining = None

    if pd.notnull(latest_balance) and latest["Net Pay"]:
        weeks_left = round(latest_balance / latest["Net Pay"], 2)

    if pd.notnull(tax_balance):
        weeks_tax_remaining = round(tax_balance / 90, 2)
    
    df = df.where(pd.notnull(df), None)
    
    output = {
        "payslips": df.to_dict(orient="records"),
        "summary": {
            "latest_week": latest["Week Ending"],
            "latest_net": float(latest["Net Pay"]),
            "visa_remaining": latest_balance,
            "weeks_until_paid": weeks_left,
            "tax_remaining": tax_balance,
            "weeks_tax_remaining": weeks_tax_remaining
        }
    }

    with open(summary_file, "w") as f:
        json.dump(output, f, indent=2)

    # delete processed PDFs
    for file in os.listdir(folder_path):
        if file.endswith(".pdf"):
            os.remove(os.path.join(folder_path, file))


if __name__ == "__main__":
    main()
