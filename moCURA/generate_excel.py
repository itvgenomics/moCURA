import logging
import os

import pandas as pd

from copy import copy

def adjust_excel_columns(**kwargs):
    worksheet = kwargs["worksheet"]
    dataframe: pd.DataFrame = kwargs["dataframe"]
    max_width = int(kwargs.get("max_width", 45))

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions

    for cell in worksheet[1]:
        header_font = copy(cell.font)
        header_font.bold = True
        cell.font = header_font

    for column_index, column_name in enumerate(dataframe.columns, start=1):
        values = dataframe[column_name].astype(str).tolist()
        width = min(
            max([len(str(column_name)), *(len(value) for value in values)]) + 2,
            max_width,
        )
        worksheet.column_dimensions[
            worksheet.cell(row=1, column=column_index).column_letter
        ].width = width

def add_blank_group_rows(dataframe: pd.DataFrame) -> pd.DataFrame:

    if dataframe.empty:
        return dataframe.copy()

    output_parts: list[pd.DataFrame] = []

    blank_row = pd.DataFrame(
        [[""] * len(dataframe.columns)],
        columns=dataframe.columns,
    )

    grouped = dataframe.fillna("-").groupby(
        ["Project name", "K-mer"],
        sort=False,
        dropna=False,
    )

    for _, group in grouped:
        output_parts.extend([group, blank_row.copy()])

    return pd.concat(output_parts, ignore_index=True)

def generate_excel(**kwargs):
    dataframe = kwargs.get("dataframe", None)
    output_file = kwargs.get("output_file", "novoplasty_summary.xlsx")
    separate_groups = bool(kwargs.get("separate_groups", True))

    os.makedirs(os.path.dirname(output_file), exist_ok=True, mode=0o755)

    export_df = dataframe.copy()

    export_df["Circularized"] = export_df["Circularized"].map(
        {True: "Yes", False: "No"}
    )

    if separate_groups:
        export_df = add_blank_group_rows(export_df)
    else:
        export_df = export_df.fillna("-")

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name="Summary", index=False)
        worksheet = writer.sheets["Summary"]
        adjust_excel_columns(worksheet=worksheet, dataframe=export_df)

    logging.info(f"Excel report generated: {output_file}")

    return output_file