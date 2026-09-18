import sys, os
sys.path.insert(0, ".")

import excel_reader, billing_engine, pdf_mapper, template_detector

excel_path = r"f:\BILLING\Bimonthly_Bills_2021_to_August_2026.xlsx"
consumers = excel_reader.read_consumers(excel_path)
history = excel_reader.build_consumption_history(consumers)

print(f"Read {len(consumers)} consumers")

# Find June 2025 consumer
c_june = next(c for c in consumers if c.get("billing_month") == "June 2025")
bill_june = billing_engine.compute_bill(c_june)
tpl_june = template_detector.get_template_for_billing_month(c_june)
ts_june = template_detector.detect_template_structure(tpl_june)
vals_june = pdf_mapper.build_field_values(c_june, bill_june, consumption_history=history, template_info=ts_june)

print("\n=== Excel June 2025 ===")
print("Template:", os.path.basename(tpl_june))
print("Units:", bill_june.units_consumed)
print("Chart values:", vals_june["chart_values"])
print("Chart months:", [vals_june.get(f"chart_month_{i}") for i in range(6)])
print("Chart years:", [f"{vals_june.get(f'chart_year_{i*2}')}-{vals_june.get(f'chart_year_{i*2+1}')}" for i in range(6)])

# Find August 2026 consumer
c_aug = next(c for c in consumers if c.get("billing_month") == "August 2026")
bill_aug = billing_engine.compute_bill(c_aug)
tpl_aug = template_detector.get_template_for_billing_month(c_aug)
ts_aug = template_detector.detect_template_structure(tpl_aug)
vals_aug = pdf_mapper.build_field_values(c_aug, bill_aug, consumption_history=history, template_info=ts_aug)

print("\n=== Excel August 2026 ===")
print("Template:", os.path.basename(tpl_aug))
print("Units:", bill_aug.units_consumed)
print("Chart values:", vals_aug["chart_values"])
print("Chart months:", [vals_aug.get(f"chart_month_{i}") for i in range(6)])
print("Chart years:", [f"{vals_aug.get(f'chart_year_{i*2}')}-{vals_aug.get(f'chart_year_{i*2+1}')}" for i in range(6)])
