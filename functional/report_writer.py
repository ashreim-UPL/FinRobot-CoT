import os
import json
import traceback
from typing import Annotated, Dict
from reportlab.lib import colors
from reportlab.lib import pagesizes
from reportlab.platypus import (
    SimpleDocTemplate,
    Frame,
    Paragraph,
    Image,
    PageTemplate,
    FrameBreak,
    Spacer,
    Table,
    TableStyle,
    NextPageTemplate,
    PageBreak,
)
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT

# In report_writer.py
def get_analysis_utils():
    from data_source.report_analysis_utils import ReportAnalysisUtils
    return ReportAnalysisUtils

from data_source.fmp_utils import FMPUtils
from typing import Annotated


class ReportLabUtils:
    @staticmethod
    def build_annual_report(
        ticker_symbol: Annotated[str, "The ticker symbol, e.g., 'MSFT'"],
        filing_date: Annotated[str, "Filing date of the report, e.g., '2024-02-15'"],
        work_dir: Annotated[str, "Path to the working directory containing all asset files."],
        asset_map: Annotated[Dict[str, str], "A dict mapping all report assets to their source filenames."],
        output_pdf_path: Annotated[str, "The full, absolute path for the output PDF."]
    ) -> str:
        """
        Builds a final PDF report from a unified asset map of pre-generated text summaries,
        chart images, and table data. This tool ONLY handles layout and compilation.
        """
        try:
            # --- 1. Load all text and image assets from the asset_map ---
            report_sections = {}
            # Define the text sections the PDF expects
            report_sections = {}
            text_keys_to_load = [
                "business_overview", "market_position", "operating_results",
                "risk_assessment", "competitors_analysis"
            ]

            # FIX #2: The loop iterates over `asset_map`'.
            for section_name in text_keys_to_load:
                file_name = asset_map.get(section_name)
                if file_name:
                    file_path = os.path.join(work_dir, file_name)
                    if os.path.exists(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            report_sections[section_name] = f.read()
                    else:
                        report_sections[section_name] = f"Content file not found: {file_path}"
                else:
                    report_sections[section_name] = f"'{section_name}' not found in asset map."
            
            # FIX #3: Image paths are also retrieved from the unified asset_map.
            share_perf_filename = asset_map.get("share_performance_image")
            pe_eps_filename = asset_map.get("pe_eps_performance_image")

            share_performance_image_path = os.path.join(work_dir, share_perf_filename) if share_perf_filename else None
            pe_eps_performance_image_path = os.path.join(work_dir, pe_eps_filename) if pe_eps_filename else None

            financial_metrics_data = {}
            key_data = {}
            metrics_path = os.path.join(work_dir, asset_map.get("financial_metrics_data", ""))
            key_data_path = os.path.join(work_dir, asset_map.get("key_data", ""))


            if os.path.exists(metrics_path):
                with open(metrics_path, 'r') as f:
                    financial_metrics_data = json.load(f) # Assumes JSON format

            if os.path.exists(key_data_path):
                with open(key_data_path, 'r') as f:
                    key_data = json.load(f) # Assumes JSON format

            pdf_path = output_pdf_path
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            doc = SimpleDocTemplate(pdf_path, pagesize=pagesizes.A4)

            # 2. 创建PDF并插入图像
            # 页面设置
            page_width, page_height = pagesizes.A4
            left_column_width = page_width * 2 / 3
            right_column_width = page_width - left_column_width
            margin = 4
      
            # 定义两个栏位的Frame
            frame_left = Frame(
                margin,
                margin,
                left_column_width - margin * 2,
                page_height - margin * 2,
                id="left",
            )
            frame_right = Frame(
                left_column_width,
                margin,
                right_column_width - margin * 2,
                page_height - margin * 2,
                id="right",
            )

            single_frame = Frame(margin, margin, page_width-margin*2, page_height-margin*2, id='single')
            single_column_layout = PageTemplate(id='OneCol', frames=[single_frame])

            left_column_width_p2 = (page_width - margin * 3) // 2
            right_column_width_p2 = left_column_width_p2
            frame_left_p2 = Frame(
                margin,
                margin,
                left_column_width_p2 - margin * 2,
                page_height - margin * 2,
                id="left",
            )
            frame_right_p2 = Frame(
                left_column_width_p2,
                margin,
                right_column_width_p2 - margin * 2,
                page_height - margin * 2,
                id="right",
            )

            #创建PageTemplate，并添加到文档
            page_template = PageTemplate(
                id="TwoColumns", frames=[frame_left, frame_right]
            )
            page_template_p2 = PageTemplate(
                id="TwoColumns_p2", frames=[frame_left_p2, frame_right_p2]
            )

            #Define single column Frame
            single_frame = Frame(
                margin,
                margin,
                page_width - 2 * margin,
                page_height - 2 * margin,
                id="single",
            )

            # Create a PageTemplate with a single column
            single_column_layout = PageTemplate(id="OneCol", frames=[single_frame])

            doc.addPageTemplates([page_template, single_column_layout, page_template_p2])

            styles = getSampleStyleSheet()

            # 自定义样式
            custom_style = ParagraphStyle(
                name="Custom",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=10,
                # leading=15,
                alignment=TA_JUSTIFY,
            )

            title_style = ParagraphStyle(
                name="TitleCustom",
                parent=styles["Title"],
                fontName="Helvetica-Bold",
                fontSize=16,
                leading=20,
                alignment=TA_LEFT,
                spaceAfter=10,
            )

            subtitle_style = ParagraphStyle(
                name="Subtitle",
                parent=styles["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=14,
                leading=12,
                alignment=TA_LEFT,
                spaceAfter=6,
            )

            table_style2 = TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                    ("FONT", (0, 0), (-1, -1), "Helvetica", 7),
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    # 所有单元格左对齐
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    # 标题栏下方添加横线
                    ("LINEBELOW", (0, 0), (-1, 0), 2, colors.black),
                    # 表格最下方添加横线
                    ("LINEBELOW", (0, -1), (-1, -1), 2, colors.black),
                ]
            )

            df, currency, name = FMPUtils.get_financial_metrics(ticker_symbol, years=5)

            # 准备左栏和右栏内容
            content = []
            # 标题
            content.append(
                Paragraph(
                    f"Equity Research Report: {name}",
                    title_style,
                )
            )

            # 子标题
            content.append(Paragraph("Business Overview", subtitle_style))
            content.append(Paragraph(report_sections.get("business_overview",""), custom_style))

            content.append(Paragraph("Market Position", subtitle_style))
            content.append(Paragraph(report_sections.get("market_position",""), custom_style))
            
            content.append(Paragraph("Operating Results", subtitle_style))
            content.append(Paragraph(report_sections.get("operating_results",""), custom_style))

            content.append(Paragraph("Summarization", subtitle_style))

            df.reset_index(inplace=True)
            df.rename(columns={"index": f"FY ({currency} mn)"}, inplace=True)

            # Transpose the table: metrics as rows, years as columns
            #df_flipped = df.set_index(f"FY ({currency} mn)")
            #df_flipped.reset_index(inplace=True)
            #df_flipped.rename(columns={"index": "Financial Metrics"}, inplace=True)
            #print("after currency", df)

            # Now use this transposed DataFrame for the table
            table_data = [df.columns.to_list()] + df.values.tolist()

            #table_data = [["Financial Metrics"]]
            #table_data += [df.columns.to_list()] + df.values.tolist()

            # Compute adaptive column widths based on column types
            base_width = (left_column_width - margin * 4)
            num_cols = len(df.columns)

            # Assign slightly larger width to potentially wider columns like "Gross Profit" or "Revenue"
            column_weights = [
                1.2 if "Profit" in col or "Revenue" in col else 1.0
                for col in df.columns
            ]
            total_weight = sum(column_weights)
            col_widths = [base_width * w / total_weight for w in column_weights]

            # Create the table
            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            table.setStyle(table_style2)
            content.append(table)

            content.append(FrameBreak())  # 用于从左栏跳到右栏

            table_style = TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                    ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 12),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    # 第一列左对齐
                    ("ALIGN", (0, 1), (0, -1), "LEFT"),
                    # 第二列右对齐
                    ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                    # 标题栏下方添加横线
                    ("LINEBELOW", (0, 0), (-1, 0), 2, colors.black),
                ]
            )
            full_length = right_column_width - 2 * margin

            data = [
                ["FinRobot"],
                ["Team9 - UOA"],
                ["https://github.com/ashreim-UPL/FinRobot-Final"],
                [f"Report date: {filing_date}"],
            ]
            col_widths = [full_length]
            table = Table(data, colWidths=col_widths)
            table.setStyle(table_style)
            content.append(table)

            # content.append(Paragraph("", custom_style))
            content.append(Spacer(1, 0.15 * inch))
            key_data = ReportAnalysisUtils.get_key_data(ticker_symbol, filing_date)
            # 表格数据
            data = [["Key data", ""]]
            data += [[k, v] for k, v in key_data.items()]
            col_widths = [full_length // 3 * 2, full_length // 3]
            table = Table(data, colWidths=col_widths)
            table.setStyle(table_style)
            content.append(table)

            # 将Matplotlib图像添加到右栏

            # 历史股价
            data = [["Share Performance"]]
            col_widths = [full_length]
            table = Table(data, colWidths=col_widths)
            table.setStyle(table_style)
            content.append(table)

            plot_path = share_performance_image_path
            width = right_column_width
            height = width // 2
            if os.path.exists(plot_path):
                content.append(Image(plot_path, width=width, height=height))
            else:
                content.append(Paragraph(f"Image not found: {plot_path}", custom_style))

            # 历史PE和EPS
            data = [["PE & EPS"]]
            col_widths = [full_length]
            table = Table(data, colWidths=col_widths)
            table.setStyle(table_style)
            content.append(table)

            plot_path = pe_eps_performance_image_path
            width = right_column_width
            height = width // 2
            if os.path.exists(plot_path):
                content.append(Image(plot_path, width=width, height=height))
            else:
                content.append(Paragraph(f"Image not found: {plot_path}", custom_style))

            # # 开始新的一页
            content.append(NextPageTemplate("OneCol"))
            content.append(PageBreak())
            
            content.append(Paragraph("Risk Assessment", subtitle_style))
            content.append(Paragraph(report_sections.get("risk_assessment",""), custom_style))

            content.append(Paragraph("Competitors Analysis", subtitle_style))
            content.append(Paragraph(report_sections.get("competitors_analysis",""), custom_style))

            doc.build(content)
            return f"Success: Annual report generated successfully at {pdf_path}"

        except Exception as e:
            # The essential error handler returns a clean message to the agent.
            error_details = traceback.format_exc()
            return f"Error: An unexpected error occurred during PDF generation. Details: {error_details}"

