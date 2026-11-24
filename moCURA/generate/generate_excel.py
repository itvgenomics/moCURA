import logging
import os
from copy import copy

import pandas as pd


def adjust_excel_columns(**kwargs):
    worksheet = kwargs["worksheet"]
    dataframe = kwargs["dataframe"]
    max_width = int(kwargs.get("max_width", 45))

    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions

    for cell in worksheet[1]:
        header_font = copy(cell.font)
        header_font.bold = True
        cell.font = header_font

    for column_index, column_name in enumerate(dataframe.columns, start=1):
        values = dataframe[column_name].tolist()
        width = min(max([len(str(column_name)), *(len(str(value)) for value in values)]) + 2, max_width)
        worksheet.column_dimensions[
            worksheet.cell(row=1, column=column_index).column_letter].width = width

def add_blank_group_rows(**kwargs):
    dataframe = kwargs.get("dataframe")

    if dataframe is None or dataframe.empty:
        return dataframe.copy()

    output_parts = []
    blank_row = pd.DataFrame([[""] * len(dataframe.columns)], columns=dataframe.columns)

    grouped = dataframe.fillna("-").groupby(["Project name", "K-mer"], sort=False, dropna=False)

    for _, group in grouped:
        output_parts.extend([group, blank_row.copy()])

    return pd.concat(output_parts, ignore_index=True)

def write_dataframe_sheet(**kwargs):
    writer = kwargs.get("writer")
    dataframe = kwargs.get("dataframe")
    sheet_name = kwargs.get("sheet_name")
    max_width = int(kwargs.get("max_width", 45))

    if dataframe is None or dataframe.empty:
        return

    dataframe.to_excel(writer, sheet_name=sheet_name, index=False)
    worksheet = writer.sheets[sheet_name]
    adjust_excel_columns(worksheet=worksheet, dataframe=dataframe, max_width=max_width)

def generate_excel(**kwargs):
    dataframe = kwargs.get("dataframe")
    output_file = kwargs.get("output_file", "novoplasty_summary.xlsx")
    separate_groups = bool(kwargs.get("separate_groups", True))
    genbank_files_dataframe = kwargs.get("genbank_files_dataframe")
    marker_dataframe = kwargs.get("marker_dataframe")
    trf_summary_dataframe = kwargs.get("trf_summary_dataframe")
    trf_repeats_dataframe = kwargs.get("trf_repeats_dataframe")

    output_directory = os.path.dirname(output_file)

    if output_directory:
        os.makedirs(output_directory, exist_ok=True, mode=0o755)

    export_df = dataframe.copy()

    if "Circularized" in export_df.columns:
        export_df["Circularized"] = export_df["Circularized"].map({True: "Yes", False: "No"})

    if separate_groups:
        export_df = add_blank_group_rows(dataframe=export_df)
    else:
        export_df = export_df.fillna("-")

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        write_dataframe_sheet(writer=writer, dataframe=export_df, sheet_name="Summary")
        write_dataframe_sheet(writer=writer, dataframe=genbank_files_dataframe, sheet_name="GenBank Files", max_width=70)
        write_dataframe_sheet(writer=writer, dataframe=marker_dataframe, sheet_name="Marker Lengths", max_width=70)
        write_dataframe_sheet(writer=writer, dataframe=trf_summary_dataframe, sheet_name="TRF Summary", max_width=70)
        write_dataframe_sheet(writer=writer, dataframe=trf_repeats_dataframe, sheet_name="TRF Repeats", max_width=100)

        for sheet_name, sheet_dataframe in kwargs.get("extra_sheets", []) or []:
            write_dataframe_sheet(writer=writer, dataframe=sheet_dataframe, sheet_name=sheet_name, max_width=70)

    logging.info(f"Excel report generated: {output_file}")
    return output_file


def append_excel_sheets(**kwargs):
    """Add sheets to an existing workbook (used for Provenance, written last)."""

    output_file = kwargs.get("output_file")
    sheets = kwargs.get("sheets", []) or []

    if not output_file or not os.path.isfile(output_file) or not sheets:
        return output_file

    with pd.ExcelWriter(output_file, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        for sheet_name, dataframe in sheets:
            write_dataframe_sheet(writer=writer, dataframe=dataframe, sheet_name=sheet_name, max_width=90)

    return output_file
