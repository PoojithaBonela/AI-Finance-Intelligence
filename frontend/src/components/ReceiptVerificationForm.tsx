import React, { useState } from "react";
import {
  AlertTriangle,
  FileText,
  Calendar,
  Pencil,
  Trash2,
  Plus,
  CheckCircle,
  Save,
  ArrowLeft,
  Loader2
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface ReceiptItemEditable {
  id: string;
  name: string;
  quantity: string;
  unit_price: string;
  total_price: string;
}

export interface ExtractedReceiptData {
  merchant_name: string;
  purchase_date: string | null;
  due_date: string | null;
  currency: string | null;
  items: Array<{ name: string; quantity: number | null; unit_price?: number | null; total_price: number }>;
  tax?: number | null;
  total_amount: number;
  payment_method?: string | null;
  warranty_period_days?: number | null;
  field_confidences: Record<string, number>;
}

interface Props {
  data: ExtractedReceiptData;
  cloudinaryUrl: string;
  cloudinaryPublicId?: string;
  filename: string;
  imageCount: number;
  onClose: () => void;
}

// ─── Confidence helpers ───────────────────────────────────────────────────────

function confLevel(score: number | undefined): "high" | "medium" | "low" {
  if (score === undefined) return "low";
  if (score >= 0.9) return "high";
  if (score >= 0.6) return "medium";
  return "low";
}

function ConfDot({ score }: { score: number | undefined }) {
  const lvl = confLevel(score);
  const colors = {
    high: "bg-emerald-500",
    medium: "bg-amber-400",
    low: "bg-rose-500",
  }[lvl];
  return <div className={`w-2 h-2 rounded-full ${colors} shrink-0`} />;
}

function ConfBadge({ score }: { score: number | undefined }) {
  if (score === undefined) return null;
  const lvl = confLevel(score);
  const pct = Math.round((score ?? 0) * 100);

  const styles = {
    high: "bg-emerald-100/50 text-emerald-700",
    medium: "bg-amber-100/50 text-amber-700",
    low: "bg-rose-100/50 text-rose-700",
  }[lvl];

  return (
    <span className={`inline-flex items-center justify-center text-[11px] font-bold px-2 py-0.5 rounded-md ${styles}`}>
      {pct}%
    </span>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export const ReceiptVerificationForm: React.FC<Props> = ({
  data,
  cloudinaryUrl,
  cloudinaryPublicId,
  filename,
  imageCount,
  onClose,
}) => {
  const fc = data.field_confidences ?? {};

  const [merchantName, setMerchantName] = useState(data.merchant_name ?? "");
  const [purchaseDate, setPurchaseDate] = useState(data.purchase_date ?? "");
  const [dueDate, setDueDate] = useState(data.due_date ?? "");
  const [currency, setCurrency] = useState(data.currency ?? "");
  const [tax, setTax] = useState(data.tax != null ? String(data.tax) : "");
  const [totalAmount, setTotalAmount] = useState(String(data.total_amount ?? ""));
  const [paymentMethod, setPaymentMethod] = useState(data.payment_method ?? "");
  const [warrantyDays, setWarrantyDays] = useState(
    data.warranty_period_days != null ? String(data.warranty_period_days) : ""
  );

  const toEditable = (items: ExtractedReceiptData["items"]): ReceiptItemEditable[] =>
    items.map((it, i) => ({
      id: String(i),
      name: it.name,
      quantity: it.quantity != null ? String(it.quantity) : "",
      unit_price: it.unit_price != null ? String(it.unit_price) : "",
      total_price: String(it.total_price),
    }));

  const [items, setItems] = useState<ReceiptItemEditable[]>(toEditable(data.items));
  const [saved, setSaved] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const formatCurrency = (val: string) => {
    if (!currency) return val;
    const symbols: Record<string, string> = { USD: "$", INR: "₹", EUR: "€", GBP: "£", CAD: "C$", AUD: "A$" };
    const symbol = symbols[currency] || currency + " ";
    return `${symbol}${val}`;
  };

  const updateItem = (id: string, field: keyof ReceiptItemEditable, value: string) => {
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, [field]: value } : it)));
  };

  const addItem = () => {
    setItems((prev) => [
      ...prev,
      { id: Date.now().toString(), name: "", quantity: "1", unit_price: "", total_price: "" },
    ]);
  };

  const removeItem = (id: string) => {
    setItems((prev) => prev.filter((it) => it.id !== id));
  };

  const normalizeDate = (dStr: string): string | null => {
    if (!dStr) return null;
    const s = dStr.trim();
    if (!s) return null;
    
    // If it's already YYYY-MM-DD
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
      if (!isNaN(Date.parse(s))) return s;
    }
    
    // Try native Date parse
    const d = new Date(s);
    if (!isNaN(d.getTime())) {
      return d.toISOString().split('T')[0];
    }
    
    // Try DD/MM/YYYY or DD-MM-YYYY
    const parts = s.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$/);
    if (parts) {
      let p1 = parseInt(parts[1], 10);
      let p2 = parseInt(parts[2], 10);
      const yyyy = parseInt(parts[3], 10);
      
      // If p1 > 12, it's definitely DD/MM
      if (p1 > 12) {
        const tmp = p1;
        p1 = p2;
        p2 = tmp;
      }
      
      if (p1 <= 12 && p2 <= 31) {
         const mm = String(p1).padStart(2, '0');
         const dd = String(p2).padStart(2, '0');
         const d2 = new Date(`${yyyy}-${mm}-${dd}`);
         if (!isNaN(d2.getTime())) return `${yyyy}-${mm}-${dd}`;
      }
    }
    
    return "invalid";
  };

  const handleSave = async () => {
    if (isSaving) return;
    
    if (!currency) {
      setSaveError("Currency not detected. Please select the correct currency before saving.");
      return;
    }

    const normPurchaseDate = normalizeDate(purchaseDate);
    if (normPurchaseDate === "invalid") {
      setSaveError("Invalid Purchase Date. Please use a recognized format (e.g. YYYY-MM-DD or DD/MM/YYYY).");
      return;
    }
    
    const normDueDate = normalizeDate(dueDate);
    if (normDueDate === "invalid") {
      setSaveError("Invalid Due Date. Please use a recognized format (e.g. YYYY-MM-DD or DD/MM/YYYY).");
      return;
    }

    setIsSaving(true);
    setSaveError(null);

    const verified = {
      merchant_name: merchantName.trim(),
      purchase_date: normPurchaseDate,
      due_date: normDueDate,
      currency: currency.trim() || null,
      items: items.map((it) => ({
        item_name: it.name.trim(),
        quantity: it.quantity ? parseFloat(it.quantity) : null,
        unit_price: it.unit_price ? parseFloat(it.unit_price) : null,
        total_price: parseFloat(it.total_price) || 0,
      })),
      tax: tax ? parseFloat(tax) : null,
      total_amount: parseFloat(totalAmount) || 0,
      payment_method: paymentMethod.trim() || null,
      warranty_period_days: warrantyDays ? parseInt(warrantyDays) : null,
      cloudinary_public_id: cloudinaryPublicId || null,
      cloudinary_resource_type: "image",
      original_filename: filename,
    };

    try {
      const response = await fetch("http://localhost:8000/api/receipts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(verified),
      });

      if (!response.ok) {
        const errorData = await response.json();
        const detail = errorData.detail;
        let errorMsg = "Failed to save receipt.";
        if (typeof detail === "string") {
          errorMsg = detail;
        } else if (Array.isArray(detail)) {
          errorMsg = detail.map((err: any) => `${err.loc?.join(".")}: ${err.msg}`).join(", ");
        } else if (typeof detail === "object" && detail !== null) {
          errorMsg = JSON.stringify(detail);
        }
        throw new Error(errorMsg);
      }

      console.info("[Purchase Trace] Successfully saved receipt to database.");
      setSaved(true);
    } catch (err: any) {
      console.error("Save error:", err);
      setSaveError(err.message || "An unexpected error occurred while saving.");
    } finally {
      setIsSaving(false);
    }
  };

  const lowFields = Object.entries(fc).filter(([, v]) => v < 0.6).map(([k]) => {
    const labels: Record<string, string> = {
      merchant_name: "merchant_name",
      purchase_date: "purchase_date",
      due_date: "due_date",
      currency: "currency",
      tax: "tax",
      total_amount: "total_amount",
      payment_method: "payment_method",
      warranty_period_days: "warranty_period_days"
    };
    return labels[k] || k;
  });

  const missingFields = [
    { val: merchantName, label: "Merchant Name" },
    { val: totalAmount, label: "Total Amount" }
  ].filter(f => !f.val).map(f => f.label);

  if (saved) {
    return (
      <div className="w-full max-w-2xl mx-auto mt-12 bg-brand-cream rounded-3xl p-10 flex flex-col items-center gap-4 text-center shadow-2xl">
        <div className="p-5 bg-emerald-100 rounded-full">
          <CheckCircle className="w-12 h-12 text-emerald-600" />
        </div>
        <h3 className="text-3xl font-bold text-brand-navy">Receipt Saved!</h3>
        <p className="text-slate-500 font-support">
          Verified data for <strong>{merchantName}</strong> has been confirmed and is ready for database storage.
        </p>
        <button
          onClick={onClose}
          className="mt-6 px-8 py-3 bg-gradient-to-r from-brand-violet to-brand-teal text-white font-bold rounded-xl hover:opacity-90 transition-opacity"
        >
          Upload Another
        </button>
      </div>
    );
  }

  const InputRow = ({ label, score, value, children }: { label: string; score?: number; value: any; children: React.ReactNode }) => {
    const isEmpty = value === "" || value === null || value === undefined;
    return (
      <div className="flex items-center gap-2 py-1 border-b border-[#171A3A]/10 last:border-0 hover:bg-black/5 px-2 -mx-2 rounded transition-colors">
        <div className="flex items-center gap-2 w-1/3 shrink-0">
          {isEmpty ? <div className="w-2 h-2 rounded-full bg-slate-300 shrink-0" /> : <ConfDot score={score} />}
          <label className="text-xs font-semibold text-[#171A3A]">{label}</label>
        </div>
        <div className="flex-1">
          {children}
        </div>
        <div className="w-10 flex justify-end shrink-0">
          {!isEmpty && <ConfBadge score={score} />}
        </div>
      </div>
    );
  };

  const baseInputCls = "w-full text-xs font-support text-[#171A3A] bg-transparent focus:outline-none focus:bg-white rounded px-2 py-1.5 border border-transparent hover:border-[#171A3A]/10 focus:border-[#171A3A]/30 transition-colors";

  return (
    <div className="w-full max-w-5xl mx-auto pt-6 pb-20 space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
        <div className="space-y-2">
          <h1 className="text-3xl sm:text-4xl font-extrabold text-[#171A3A]">Review & Save Receipt</h1>
          <p className="text-[#164A3A] font-support max-w-lg text-sm sm:text-base leading-relaxed">
            We've extracted the details from your document. Please review the information below and make any necessary changes before saving.
          </p>
        </div>
        <div className="bg-white/50 backdrop-blur-md border border-[#171A3A]/10 rounded-2xl p-5 flex items-start gap-4 min-w-[280px]">
          <div className="text-[#0D7C66] mt-1">
            <FileText className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-[#171A3A]/60 font-semibold uppercase tracking-wider mb-1">Document Type</p>
            <p className="text-base font-bold text-[#171A3A] mb-3">Purchase Receipt</p>
            <p className="text-[11px] text-[#171A3A]/50 font-support">Extracted on</p>
            <p className="text-xs font-semibold text-[#171A3A]/80">{new Date().toLocaleString()}</p>
          </div>
        </div>
      </div>

      {/* Review Banner */}
      {lowFields.length > 0 && (
        <div className="bg-[#7A9B6D] rounded-2xl border border-[#6B8C5E] p-4 flex items-start gap-3 shadow-sm">
          <AlertTriangle className="w-5 h-5 text-white shrink-0 mt-0.5" />
          <p className="text-sm text-white font-support">
            <span className="font-bold">{lowFields.length} field{lowFields.length > 1 ? "s" : ""} need review:</span>{" "}
            {lowFields.join(", ")}. Low-confidence fields are highlighted.
          </p>
        </div>
      )}

      {/* Missing Fields Banner */}
      {missingFields.length > 0 && (
        <div className="bg-[#B8C5A3] rounded-2xl border border-[#7A9B6D] p-4 flex items-start gap-3 shadow-sm">
          <AlertTriangle className="w-5 h-5 text-[#0D7C66] shrink-0 mt-0.5" />
          <p className="text-sm text-[#0D7C66] font-support">
            <span className="font-bold">Missing required fields:</span>{" "}
            {missingFields.join(", ")}. Please fill them before saving.
          </p>
        </div>
      )}

      {/* Currency Missing Banner */}
      {!currency && (
        <div className="bg-amber-50 rounded-2xl border border-amber-200 p-4 flex items-start gap-3 shadow-sm">
          <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
          <p className="text-sm text-amber-700 font-support">
            <span className="font-bold">⚠ Currency not detected.</span> Please select the correct currency before saving.
          </p>
        </div>
      )}

      {/* Save Error Banner */}
      {saveError && (
        <div className="bg-rose-50 rounded-2xl border border-rose-200 p-4 flex items-start gap-3 shadow-sm">
          <AlertTriangle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
          <p className="text-sm text-rose-700 font-support">
            <span className="font-bold">Failed to save receipt:</span> {saveError}
          </p>
        </div>
      )}

      {/* Main Form Panel */}
      <div className="bg-[#B8C5A3] rounded-[32px] shadow-2xl p-6 sm:p-10 space-y-12">
        
        {/* Core Details */}
        <div className="space-y-2">
          <h3 className="text-xs font-bold text-[#164A3A] uppercase tracking-widest pl-2">Core Details</h3>
          <div className="bg-white rounded-xl p-2 sm:px-4 sm:py-2 shadow-sm border border-slate-100">
            <InputRow label="Merchant Name" score={fc.merchant_name} value={merchantName}>
              <input className={baseInputCls} value={merchantName} onChange={e => setMerchantName(e.target.value)} placeholder="Walk-in Customer" />
            </InputRow>
            
            <InputRow label="Purchase Date" score={fc.purchase_date} value={purchaseDate}>
              <input className={baseInputCls} value={purchaseDate} onChange={e => setPurchaseDate(e.target.value)} placeholder="DD-MMM-YYYY" />
            </InputRow>

            <InputRow label="Due Date" score={fc.due_date} value={dueDate}>
              <div className="relative">
                <input className={baseInputCls} value={dueDate} onChange={e => setDueDate(e.target.value)} placeholder="Select date" />
                <Calendar className="w-4 h-4 text-slate-400 absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>
            </InputRow>

            <InputRow label="Currency" score={fc.currency} value={currency}>
              <select className={baseInputCls} value={currency || ""} onChange={e => setCurrency(e.target.value)}>
                <option value="" disabled>Select currency</option>
                <option value="USD">USD</option>
                <option value="INR">INR</option>
                <option value="EUR">EUR</option>
                <option value="GBP">GBP</option>
                <option value="CAD">CAD</option>
                <option value="AUD">AUD</option>
              </select>
            </InputRow>

            <InputRow label="Total Amount" score={fc.total_amount} value={totalAmount}>
              <input type="number" step="0.01" className={baseInputCls} value={totalAmount} onChange={e => setTotalAmount(e.target.value)} placeholder="0.00" />
            </InputRow>

            <InputRow label="Tax" score={fc.tax} value={tax}>
              <input type="number" step="0.01" className={baseInputCls} value={tax} onChange={e => setTax(e.target.value)} placeholder="Not found" />
            </InputRow>

            <InputRow label="Payment Method" score={fc.payment_method} value={paymentMethod}>
              <input className={baseInputCls} value={paymentMethod} onChange={e => setPaymentMethod(e.target.value)} placeholder="Select payment method" />
            </InputRow>

            <InputRow label="Warranty Period (Days)" score={fc.warranty_period_days} value={warrantyDays}>
              <input type="number" className={baseInputCls} value={warrantyDays} onChange={e => setWarrantyDays(e.target.value)} placeholder="Not found" />
            </InputRow>
          </div>
        </div>

        {/* Line Items Table */}
        <div className="space-y-4">
          <div className="flex items-center justify-between pl-2">
            <div className="flex items-center gap-3">
              <h3 className="text-xs font-bold text-[#164A3A] uppercase tracking-widest">Line Items</h3>
              {/* Optional overall items confidence could go here */}
            </div>
            <button onClick={addItem} className="flex items-center gap-1.5 text-sm font-bold text-[#0D7C66] hover:text-[#0a5c4c] transition-colors">
              <Plus className="w-4 h-4" /> Add Item
            </button>
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse min-w-[600px]">
                <thead>
                  <tr className="border-b border-[#171A3A]/20">
                    <th className="py-2 px-3 text-xs font-bold text-[#171A3A] w-1/3">Item Name</th>
                    <th className="py-2 px-3 text-xs font-bold text-[#171A3A] w-24">Qty</th>
                    <th className="py-2 px-3 text-xs font-bold text-[#171A3A] w-32">Unit Price</th>
                    <th className="py-2 px-3 text-xs font-bold text-[#171A3A] w-32">Total</th>
                    <th className="py-2 px-3 text-xs font-bold text-[#171A3A] w-20 text-right"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#171A3A]/10">
                  {items.map((item, idx) => (
                    <tr key={item.id} className="group hover:bg-black/5">
                      <td className="py-1 px-3 border-r border-[#171A3A]/10">
                        <div className="flex items-center gap-2">
                          {item.name ? <ConfDot score={data.items[idx]?.name ? 0.9 : undefined} /> : <div className="w-2 h-2 rounded-full bg-slate-300 shrink-0" />}
                          <input
                            className="w-full text-xs font-medium text-[#171A3A] bg-transparent focus:outline-none focus:bg-white rounded px-1 py-1"
                            value={item.name}
                            onChange={(e) => updateItem(item.id, "name", e.target.value)}
                            placeholder="Item name"
                          />
                        </div>
                      </td>
                      <td className="py-1 px-3 border-r border-[#171A3A]/10">
                        <input
                          type="number"
                          className="w-full text-xs font-support text-[#171A3A] bg-transparent focus:outline-none focus:bg-white rounded px-1 py-1"
                          value={item.quantity}
                          onChange={(e) => updateItem(item.id, "quantity", e.target.value)}
                          placeholder="—"
                        />
                      </td>
                      <td className="py-1 px-3 border-r border-[#171A3A]/10">
                        <input
                          type="number"
                          className="w-full text-xs font-support text-[#171A3A] bg-transparent focus:outline-none focus:bg-white rounded px-1 py-1"
                          value={item.unit_price}
                          onChange={(e) => updateItem(item.id, "unit_price", e.target.value)}
                          placeholder="—"
                        />
                      </td>
                      <td className="py-1 px-3 border-r border-[#171A3A]/10">
                        <input
                          type="number"
                          className="w-full text-xs font-support font-semibold text-[#171A3A] bg-transparent focus:outline-none focus:bg-white rounded px-1 py-1"
                          value={item.total_price}
                          onChange={(e) => updateItem(item.id, "total_price", e.target.value)}
                          placeholder="0.00"
                        />
                      </td>
                      <td className="py-1 px-3 text-right">
                        <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button className="p-1 text-slate-400 hover:text-[#0D7C66] transition-colors">
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button onClick={() => removeItem(item.id)} className="p-1 text-slate-400 hover:text-[#800020] transition-colors">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Subtotal/Total Summary Row */}
            <div className="bg-slate-50/50 border-t border-slate-100 p-6 flex flex-col items-end gap-2">
              <div className="flex items-center justify-between w-64 text-sm">
                <span className="text-slate-500 font-semibold">Subtotal</span>
                <span className="font-support text-brand-navy font-semibold">{formatCurrency(totalAmount || "0.00")}</span>
              </div>
              <div className="flex items-center justify-between w-64 text-base mt-1">
                <span className="font-bold text-brand-navy">Total Amount</span>
                <span className="font-support font-bold text-emerald-600">{formatCurrency(totalAmount || "0.00")}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Action Bar */}
        <div className="flex items-center justify-between pt-4">
          <button
            onClick={onClose}
            disabled={isSaving}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold text-brand-navy bg-white border border-slate-200 hover:bg-slate-50 transition-colors shadow-sm disabled:opacity-50"
          >
            <ArrowLeft className="w-4 h-4" /> Back
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="flex items-center gap-2 px-8 py-3 rounded-xl text-sm font-bold text-white bg-[#7A9B6D] hover:bg-[#6B8C5E] transition-colors shadow-lg disabled:opacity-70 disabled:cursor-not-allowed"
          >
            {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {isSaving ? "Saving..." : "Save Receipt"}
          </button>
        </div>

      </div>
    </div>
  );
};
