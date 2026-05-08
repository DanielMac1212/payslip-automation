import os
import pdfplumber
import re
import pandas as pd
import json

folder_path = "payslips"
summary_file = "payslipsummary.json"
rebuild = os.getenv("REBUILD", "false") == "true"

total_earnings = 31683.23

def extract_payslip_data(pdf_path):
    
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text()

    dateEnd = re.search(r"Period\s*Ending.*?(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE | re.DOTALL)
    hoursx1 = re.search(r"Hours Paid[:\s]*([\d]+)", text)
    hoursx1_5 = re.search(r"Rail - Casual Ordinary Hours 1.5[:\s]*([\d\.]+)", text)
    hoursx2 = re.search(r"Rail - Casual Ordinary Hours 2x[:\s]*([\d\.]+)", text)
    gross = re.search(r"Gross Earnings[:\s]*\$?([\d,\.]+)", text)
    net = re.search(r"Net Payment[:\s]*\$?([\d,\.]+)", text)

    week_ending = None
    if not dateEnd:
        dateEnd = re.search(r"(\d{2}/\d{2}/\d{4})", text)
    if dateEnd:
        raw_date = dateEnd.group(1)
        parsed = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")
    if pd.notna(parsed):
        week_ending = parsed.strftime("%d/%m/%Y")
                                                            
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
    df["Week Ending"] = pd.to_datetime(df["Week Ending"], dayfirst=True, errors= "coerce")
    df = df.sort_values("Week Ending").reset_index(drop=True)
    df = df.where(pd.notnull(df), None)

    target_row = 11
    total_earnings = float(df["Net Pay"].fillna(0).sum())

    return df, total_earnings

def safe(value):
    return None if pd.isna(value) else value

def main():

    existing_payslips = load_existing_data()

    if rebuild:
        if not existing_payslips:
            return
    else:
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
                raise RuntimeError(f"❌ Failed processing {file}: {e}")
    
    all_payslips = existing_payslips + new_entries
            
    if not all_payslips:
        print("No payslips found.")
        return
            
    df, total_earnings = calculate_balances(all_payslips)
            
    latest = (df.sort_values("Week Ending").iloc[-1])
    df["Week Ending"] = df["Week Ending"].dt.strftime("%d/%m/%Y")
    df = df.where(pd.notnull(df), None)
    output = {
        "payslips": json.loads(df.to_json(orient="records")),
        "summary": {
            "latest_week": latest["Week Ending"].strftime("%d/%m/%Y"),
            "latest_net": float(latest["Net Pay"]),
            "total_earnings": total_earnings,
        }
    }

    with open(summary_file, "w") as f:
        json.dump(output, f, indent=2, allow_nan=False)

    # delete processed PDFs
    for file in os.listdir(folder_path):
        if file.endswith(".pdf"):
            os.remove(os.path.join(folder_path, file))


if __name__ == "__main__":
    main()
