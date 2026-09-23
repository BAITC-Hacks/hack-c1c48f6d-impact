import pandas as pd
from src.quality import data_quality_report


def test_unmatched_skus_are_reported_not_silently_dropped():
    products = pd.DataFrame({"supplier": ["IEK"], "sku": ["MOQ_ONLY"]})
    sales = pd.DataFrame({"supplier": ["IEK"], "sku": ["SALES_ONLY"]})
    inventory = pd.DataFrame({"sku": []})
    inbound = pd.DataFrame({"sku": []})
    tx = pd.DataFrame({"date": [pd.NaT], "raw_quantity": [None]})
    got = data_quality_report(products, sales, inventory, inbound, tx).set_index(
        "check"
    )
    assert (
        got.loc["sales_missing_moq", "count"] == 1
        and got.loc["moq_missing_sales", "count"] == 1
    )
