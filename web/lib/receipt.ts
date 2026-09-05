import { jsPDF } from "jspdf";
import type { OrderReceipt } from "@/lib/api";

const money = (n: number) => `Rs. ${(Math.round(n * 100) / 100).toLocaleString("en-IN")}`;

/** Build and trigger download of a clean A4 PDF receipt for an order. */
export function downloadReceiptPdf(r: OrderReceipt): void {
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const pageW = doc.internal.pageSize.getWidth();
  const left = 48;
  const right = pageW - 48;
  let y = 60;

  // Brand header
  doc.setFont("helvetica", "bold");
  doc.setFontSize(20);
  doc.setTextColor(99, 102, 241);
  doc.text("SynCore", left, y);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(120);
  doc.text("AI Shopping Assistant", left, y + 15);

  doc.setFontSize(11);
  doc.setTextColor(30);
  doc.setFont("helvetica", "bold");
  doc.text("ORDER RECEIPT", right, y, { align: "right" });
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(120);
  const placed = new Date(r.placed_at * 1000).toLocaleString("en-IN");
  doc.text(placed, right, y + 15, { align: "right" });

  y += 40;
  doc.setDrawColor(225);
  doc.line(left, y, right, y);
  y += 24;

  // Order meta
  doc.setFontSize(10);
  doc.setTextColor(30);
  doc.setFont("helvetica", "bold");
  doc.text(`Order ID: ${r.order_id}`, left, y);
  doc.setFont("helvetica", "normal");
  doc.setTextColor(16, 150, 90);
  doc.text(`${r.payment_status} - ${r.payment_method}`, right, y, { align: "right" });
  y += 26;

  // Table header
  doc.setFillColor(244, 244, 245);
  doc.rect(left, y - 12, right - left, 22, "F");
  doc.setTextColor(90);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(9);
  doc.text("ITEM", left + 8, y + 3);
  doc.text("QTY", right - 190, y + 3, { align: "right" });
  doc.text("PRICE", right - 100, y + 3, { align: "right" });
  doc.text("AMOUNT", right - 8, y + 3, { align: "right" });
  y += 26;

  // Rows
  doc.setFont("helvetica", "normal");
  doc.setTextColor(30);
  doc.setFontSize(10);
  for (const it of r.items) {
    const name = it.name.length > 52 ? it.name.slice(0, 51) + "\u2026" : it.name;
    doc.text(name, left + 8, y);
    doc.text(`${it.quantity} ${it.unit}`, right - 190, y, { align: "right" });
    doc.text(money(it.unit_price), right - 100, y, { align: "right" });
    doc.text(money(it.line_total), right - 8, y, { align: "right" });
    y += 20;
    if (y > 720) {
      doc.addPage();
      y = 60;
    }
  }

  y += 6;
  doc.setDrawColor(225);
  doc.line(left, y, right, y);
  y += 24;

  // Total
  doc.setFont("helvetica", "bold");
  doc.setFontSize(13);
  doc.setTextColor(20);
  doc.text("TOTAL PAID", left + 8, y);
  doc.text(money(r.total), right - 8, y, { align: "right" });
  y += 22;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(120);
  doc.text(`Wallet balance after payment: ${money(r.wallet_balance_after)}`, left + 8, y);

  // Footer
  y = 780;
  doc.setDrawColor(225);
  doc.line(left, y, right, y);
  doc.setFontSize(8);
  doc.setTextColor(150);
  doc.text(
    "Demo receipt - SynCore AI Shopping Assistant. Paid from prepaid wallet (Razorpay test mode).",
    left,
    y + 16,
  );

  doc.save(`SynCore-Receipt-${r.order_id}.pdf`);
}
