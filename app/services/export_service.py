"""
Export service for Ndungu Electronics IMS.
Implements:
1. Pure-Python ReportLab A4 PDF generation (no native C Cairo/WeasyPrint dependencies, 100% PythonAnywhere compatible).
2. Formula-safe CSV export neutralizing injection characters (=, +, -, @, \\t, \\r) with UTF-8 BOM (\\ufeff).
"""

import io
import csv
from typing import List, Dict, Any
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from app.domain.money import format_kes


def sanitize_csv_cell(value: Any) -> str:
    """
    Neutralizes spreadsheet formula injection (CSV Injection / CWE-1236).
    If a string begins with =, +, -, @, \\t, or \\r, prepend a single quote (').
    """
    if value is None:
        return ""
    s = str(value)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s}"
    return s


class ExportService:
    """Handles formula-safe CSV exports and ReportLab PDF document compilation."""

    sanitize_csv_cell = staticmethod(sanitize_csv_cell)

    @staticmethod
    def export_sales_csv(sales_records: List[Dict[str, Any]]) -> str:
        """
        Exports sales transactions to CSV with UTF-8 BOM and formula sanitization.
        Returns the CSV content string.
        """
        output = io.StringIO()
        # Emit UTF-8 BOM
        output.write("\ufeff")

        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([
            "Receipt No",
            "Date Time",
            "Cashier",
            "Payment Method",
            "Payment Ref",
            "Status",
            "Subtotal (KES)",
            "Discount (KES)",
            "VAT 16% (KES)",
            "Total (KES)"
        ])

        for s in sales_records:
            writer.writerow([
                sanitize_csv_cell(s.get("receipt_no", "")),
                sanitize_csv_cell(s.get("sale_date", "")),
                sanitize_csv_cell(s.get("cashier_snapshot", "")),
                sanitize_csv_cell(s.get("payment_method", "").upper()),
                sanitize_csv_cell(s.get("payment_reference", "")),
                sanitize_csv_cell(s.get("status", "").upper()),
                sanitize_csv_cell(f"{s.get('subtotal_cents', 0) / 100:.2f}"),
                sanitize_csv_cell(f"{s.get('discount_cents', 0) / 100:.2f}"),
                sanitize_csv_cell(f"{s.get('tax_cents', 0) / 100:.2f}"),
                sanitize_csv_cell(f"{s.get('total_cents', 0) / 100:.2f}")
            ])

        return output.getvalue()

    @staticmethod
    def export_inventory_csv(inventory_items: List[Dict[str, Any]]) -> str:
        """Exports inventory catalog to formula-safe CSV."""
        output = io.StringIO()
        output.write("\ufeff")

        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([
            "SKU",
            "Product Name",
            "Brand",
            "Model",
            "Category",
            "Tracking Mode",
            "Stock",
            "Reorder Threshold",
            "Price (KES)",
            "Cost Price (KES)",
            "Valuation (KES)",
            "Status"
        ])

        for item in inventory_items:
            stock = item.get("stock", 0)
            price_cents = item.get("price_cents", 0)
            valuation_cents = stock * price_cents
            writer.writerow([
                sanitize_csv_cell(item.get("sku", "")),
                sanitize_csv_cell(item.get("name", "")),
                sanitize_csv_cell(item.get("brand", "")),
                sanitize_csv_cell(item.get("model", "")),
                sanitize_csv_cell(item.get("category_name", "")),
                sanitize_csv_cell(item.get("tracking_mode", "")),
                sanitize_csv_cell(stock),
                sanitize_csv_cell(item.get("reorder_threshold", 5)),
                sanitize_csv_cell(f"{price_cents / 100:.2f}"),
                sanitize_csv_cell(f"{item.get('cost_price_cents', 0) / 100:.2f}"),
                sanitize_csv_cell(f"{valuation_cents / 100:.2f}"),
                sanitize_csv_cell("Active" if item.get("is_active") else "Archived")
            ])

        return output.getvalue()

    @staticmethod
    def generate_bi_pdf(report_data: Dict[str, Any]) -> bytes:
        """
        Compiles an executive A4 PDF telemetry report using ReportLab Platypus.
        Returns raw PDF bytes.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#0F766E")
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#64748B")
        )
        section_style = ParagraphStyle(
            "DocSection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#0F172A")
        )
        table_cell = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10
        )
        table_cell_bold = ParagraphStyle(
            "TableCellBold",
            parent=table_cell,
            fontName="Helvetica-Bold"
        )

        elements = []

        # Store Header
        elements.append(Paragraph("NDUNGU ELECTRONICS — BUSINESS TELEMETRY REPORT", title_style))
        period_label = report_data.get("period_label", "Custom Period")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elements.append(Paragraph(f"Thika Main Branch • Period: {period_label} • Generated: {now_str}", subtitle_style))
        elements.append(Spacer(1, 15))

        # Financial KPI Summary Table
        kpi = report_data.get("kpi", {})
        kpi_data = [
            [
                Paragraph("<b>Metric</b>", table_cell_bold),
                Paragraph("<b>Value</b>", table_cell_bold),
                Paragraph("<b>Metric</b>", table_cell_bold),
                Paragraph("<b>Value</b>", table_cell_bold)
            ],
            [
                Paragraph("Gross Sales Revenue", table_cell),
                Paragraph(format_kes(kpi.get("gross_revenue_cents", 0)), table_cell_bold),
                Paragraph("Completed Transactions", table_cell),
                Paragraph(str(kpi.get("sales_count", 0)), table_cell_bold)
            ],
            [
                Paragraph("Promotion Discounts", table_cell),
                Paragraph(format_kes(kpi.get("discount_cents", 0)), table_cell),
                Paragraph("Voided Sales", table_cell),
                Paragraph(str(kpi.get("voided_count", 0)), table_cell)
            ],
            [
                Paragraph("VAT (16% Included)", table_cell),
                Paragraph(format_kes(kpi.get("tax_cents", 0)), table_cell),
                Paragraph("Active Catalog SKUs", table_cell),
                Paragraph(str(report_data.get("total_skus", 0)), table_cell)
            ],
            [
                Paragraph("Net Sales Revenue", table_cell_bold),
                Paragraph(format_kes(kpi.get("net_revenue_cents", 0)), table_cell_bold),
                Paragraph("Inventory Valuation", table_cell_bold),
                Paragraph(format_kes(report_data.get("valuation_cents", 0)), table_cell_bold)
            ]
        ]

        t_kpi = Table(kpi_data, colWidths=[140, 120, 140, 120])
        t_kpi.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t_kpi)
        elements.append(Spacer(1, 15))

        # Low Stock Reorder Recommendations
        low_stock_items = report_data.get("low_stock_items", [])
        if low_stock_items:
            elements.append(Paragraph(f"Low-Stock Reorder Recommendations ({len(low_stock_items)} SKUs)", section_style))
            elements.append(Spacer(1, 6))

            reorder_table_data = [
                [
                    Paragraph("<b>SKU</b>", table_cell_bold),
                    Paragraph("<b>Product Name</b>", table_cell_bold),
                    Paragraph("<b>Current Stock</b>", table_cell_bold),
                    Paragraph("<b>Threshold</b>", table_cell_bold),
                    Paragraph("<b>Suggested Order</b>", table_cell_bold),
                    Paragraph("<b>Supplier Contact</b>", table_cell_bold)
                ]
            ]

            for item in low_stock_items[:15]:
                reorder_table_data.append([
                    Paragraph(item.get("sku", ""), table_cell),
                    Paragraph(item.get("name", ""), table_cell),
                    Paragraph(str(item.get("stock", 0)), table_cell_bold),
                    Paragraph(str(item.get("reorder_threshold", 5)), table_cell),
                    Paragraph(f"+{item.get('reorder_qty', 10)} units", table_cell_bold),
                    Paragraph(f"{item.get('supplier_name', '')} {item.get('supplier_phone', '')}".strip() or "-", table_cell)
                ])

            t_reorder = Table(reorder_table_data, colWidths=[70, 170, 60, 60, 70, 90])
            t_reorder.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FEF3C7")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#FDE68A")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(t_reorder)
            elements.append(Spacer(1, 15))

        # Recent Sales Ledger Table
        recent_sales = report_data.get("recent_sales", [])
        if recent_sales:
            elements.append(Paragraph("Recent Transactions Snapshot", section_style))
            elements.append(Spacer(1, 6))

            sales_table_data = [
                [
                    Paragraph("<b>Receipt No</b>", table_cell_bold),
                    Paragraph("<b>Date & Time</b>", table_cell_bold),
                    Paragraph("<b>Cashier</b>", table_cell_bold),
                    Paragraph("<b>Payment</b>", table_cell_bold),
                    Paragraph("<b>Status</b>", table_cell_bold),
                    Paragraph("<b>Total (KES)</b>", table_cell_bold)
                ]
            ]

            for s in recent_sales[:12]:
                sales_table_data.append([
                    Paragraph(s.get("receipt_no", ""), table_cell),
                    Paragraph(s.get("sale_date", ""), table_cell),
                    Paragraph(s.get("cashier_snapshot", ""), table_cell),
                    Paragraph(s.get("payment_method", "").upper(), table_cell),
                    Paragraph(s.get("status", "").upper(), table_cell),
                    Paragraph(format_kes(s.get("total_cents", 0)), table_cell_bold)
                ])

            t_sales = Table(sales_table_data, colWidths=[90, 110, 100, 70, 60, 90])
            t_sales.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(t_sales)

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
