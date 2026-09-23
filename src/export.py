from io import BytesIO


def to_csv_bytes(frame):
    return frame.to_csv(index=False).encode("utf-8-sig")


def to_excel_bytes(frame):
    output = BytesIO()
    with __import__("pandas").ExcelWriter(output, engine="xlsxwriter") as writer:
        for supplier, group in frame.groupby("supplier", sort=False):
            group.to_excel(writer, sheet_name=str(supplier)[:31], index=False)
    return output.getvalue()
