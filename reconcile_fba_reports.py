import pandas as pd


def reconcile_fba_reports(inventory_ledger_path, reimbursements_report_path, output_path):
    # Step 1: Load the Inventory Ledger and Reimbursements Report CSV files
    inventory_ledger_df = pd.read_csv(inventory_ledger_path)
    reimbursements_report_df = pd.read_csv(reimbursements_report_path)

    # Step 2: Filter Inventory Ledger for relevant events (Lost, Damaged, Missing, etc.)
    flagged_inventory = inventory_ledger_df[
        inventory_ledger_df['event_type'].isin(
            ['Lost', 'Damaged', 'Missing', 'Destroyed', 'Disposal', 'Transfer']
        )
    ]

    # Step 3: Cross-reference with Reimbursements Report to exclude already reimbursed transactions
    flagged_inventory = flagged_inventory[
        ~flagged_inventory['transaction_id'].isin(reimbursements_report_df['transaction_id'])
    ]

    # Step 4: Filter for transactions within the 9-month window
    flagged_inventory = flagged_inventory.copy()
    flagged_inventory['event_date'] = pd.to_datetime(flagged_inventory['event_date'])
    nine_months_ago = pd.Timestamp.today() - pd.DateOffset(months=9)
    flagged_inventory = flagged_inventory[flagged_inventory['event_date'] >= nine_months_ago]

    # Step 5: Assign Confidence Level (High for large quantity events, Medium for smaller)
    flagged_inventory['confidence_level'] = flagged_inventory['units_affected'].apply(
        lambda x: 'High' if x > 50 else 'Medium'
    )

    # Step 6: Generate the reconciliation report with key details
    reconciliation_report = flagged_inventory[
        ['asin', 'sku', 'transaction_id', 'event_date', 'units_affected', 'event_type', 'confidence_level']
    ]

    # Step 7: Save the output reconciliation report to a new CSV file
    reconciliation_report.to_csv(output_path, index=False)

    return reconciliation_report


if __name__ == '__main__':
    inventory_ledger_path = 'client_inventory_ledger.csv'
    reimbursements_report_path = 'client_reimbursements.csv'
    output_path = 'fba_reconciliation_report.csv'

    reconciliation_report = reconcile_fba_reports(
        inventory_ledger_path, reimbursements_report_path, output_path
    )

    print(reconciliation_report)
