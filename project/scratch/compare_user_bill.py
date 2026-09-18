import os, filecmp

p_user = r"f:\BILLING\00_Electricity_Bill_June_2025_7432005324.pdf"
p_temp = r"C:\Users\91798\AppData\Local\Temp\electricity_bill_generator\output\direct_6e4a3f033e\00_Electricity_Bill_June_2025_7432005324.pdf"
print("Exists:", os.path.exists(p_temp))
if os.path.exists(p_temp):
    print("Identical to direct_6e4a3f033e:", filecmp.cmp(p_user, p_temp))
