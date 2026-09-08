# Electricity Bill Generator

Generates one filled-in electricity bill PDF per row of an Excel sheet, using
an uploaded bill PDF as a visual template. All charges are calculated
dynamically by `billing_engine.py` - nothing is copied from the template PDF.

## Project layout

```
project/
├── app.py              Flask web app (upload -> generate -> ZIP download)
├── billing_engine.py    All bill calculations (fixed/energy/FPPCA/totals)
├── pdf_generator.py     Overlays calculated values onto the template PDF
├── pdf_mapper.py        Coordinate map + formatting for every dynamic field
├── excel_reader.py       Reads consumer rows out of the uploaded Excel file
├── config.py             Tariff rates, percentages, paths (edit rates here)
├── requirements.txt
├── templates/index.html  The 3-control upload page
├── static/
├── uploads/               Uploaded files land here (per request, in a job folder)
├── output/                Generated PDFs + ZIP land here
└── utils/file_utils.py    Filename sanitizing + zipping helpers
```

## Running it

```bash
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000, upload the template PDF and the Excel file,
and click **Generate PDFs**. A ZIP containing `Invoice_<CustomerID>.pdf` for
every row will download automatically.

## How the calculations work (billing_engine.py)

```
Fixed Charges   = Sanctioned Load (kW) x Fixed Charge Rate       [config.FIXED_CHARGE_RATE_PER_KW]
Energy Charges  = slab-wise sum over ENERGY_TARIFF_SLABS[category]
FPPCA           = (Fixed Charges + Energy Charges) x FPPCA%      [config.FPPCA_PERCENT]
Total Charges   = Fixed Charges + Energy Charges + FPPCA
Total Amount    = Total Charges + Arrear + Other Debit/Credit
                  - Prompt Rebate - Advance Rebate
Delay Surcharge = Total Amount x Delay%/month                    [config.DELAY_SURCHARGE_PERCENT_PER_MONTH]
Amount After Due Date = Total Amount + Delay Surcharge
```

All rates/percentages live in `config.py` - change them there, never in
`billing_engine.py` itself.

## Excel columns expected

`excel_reader.py` matches headers case-insensitively (spaces/underscores are
interchangeable), so minor formatting differences in your sheet are fine.
Expected columns include: `Customer_ID`, `Consumer_Name`, `Address`,
`Mobile_No`, `Email`, `Category`, `Supply_Type`, `Sanctioned_Load`,
`Billing_Month`, `Reading_Date`, `Bill_Date`, `Due_Date`, `Bill_No`,
`Meter_No`, `Start_Reading`, `End_Reading`, `Multiplier`, `Units`, `Arrear`,
`Other_Debit_Credit`, `Prompt_Rebate`, `Advance_Rebate`, `Previous_Payment`,
`Previous_Payment_Date`, `Security_Deposit`, `Additional_Security`, `Area`,
`Substation`, `Legacy_No`, `Billing_Mode`, `Group_No`.

Only raw inputs are read from Excel (readings, sanctioned load, arrear,
rebates, etc.) - any pre-calculated totals in your sheet are ignored, since
`billing_engine.py` is the single source of truth for computed values.

## How the PDF overlay works (pdf_mapper.py / pdf_generator.py)

The uploaded template's layout, fonts, logo, QR code, and borders are all
left untouched. For each dynamic field, `pdf_generator.py`:

1. Paints a small white rectangle over the original placeholder value.
2. Draws the newly calculated value in the same position/alignment.

Coordinates for every field are defined in `pdf_mapper.py`, calibrated
against the two-page bill template supplied with this project (A4,
595 x 842pt). **If you use a different template PDF layout, you must update
those coordinates** to match its design - the code has no way to guess where
a differently-designed template expects each value to go.

## Known limitations

- The "Consumption Trend" bar chart and QR code on the template are treated
  as static artwork and are not regenerated per-consumer.
- Overlay-based field placement (rather than true template redesign) means
  very large values (e.g. a huge number of units, or a very long name) may
  slightly outgrow their whiteout box on the specific supplied template.
  Widen the box in `pdf_mapper.py` if your data runs long.
