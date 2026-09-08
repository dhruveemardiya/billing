import billing_engine

def fix_previous_payments(consumers):
    """
    Overwrite each row's previous_payment with the ACTUAL computed
    total_amount_due from the previous month's bill, instead of trusting
    the (possibly stale) Previous_Payment value from Excel.
    Assumes `consumers` is already in chronological (month) order,
    which matches the row order in your sheet.
    """
    previous_total = None
    previous_due_date = None

    for consumer in consumers:
        if previous_total is not None:
            consumer["previous_payment"] = previous_total
            consumer["previous_payment_date"] = previous_due_date

        bill = billing_engine.compute_bill(consumer)

        previous_total = bill.total_amount_due
        previous_due_date = consumer.get("due_date")

    return consumers