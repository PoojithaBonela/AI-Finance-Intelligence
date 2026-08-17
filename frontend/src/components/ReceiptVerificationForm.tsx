import React, { useState, useRef } from "react";
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
  is_incomplete?: boolean;
}

interface Props {
  data: ExtractedReceiptData;
  cloudinaryUrl: string;
  cloudinaryPublicId?: string;
  filename: string;
  initialFiles: File[];
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
  initialFiles,
  onClose,
}) => {
  // Initialize state from props
  const [merchantName, setMerchantName] = useState(data.merchant_name);
  const [purchaseDate, setPurchaseDate] = useState(data.purchase_date ?? "");
  const [dueDate, setDueDate] = useState(data.due_date ?? "");
  const [currency, setCurrency] = useState(data.currency ?? "");
  const [tax, setTax] = useState<string>(data.tax ? String(data.tax) : "");
  const [totalAmount, setTotalAmount] = useState<string>(String(data.total_amount));
  const [paymentMethod, setPaymentMethod] = useState(data.payment_method ?? "");
  const [warrantyDays, setWarrantyDays] = useState(data.warranty_period_days ? String(data.warranty_period_days) : "");
  const [fc, setFc] = useState(data.field_confidences);
  
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

  // Upload missing part / multi-file state
  const [files, setFiles] = useState<File[]>(initialFiles);
  const [isUploadingMissingPart, setIsUploadingMissingPart] = useState(false);
  const missingPartInputRef = useRef<HTMLInputElement>(null);

  // Incomplete receipt state
  const [currentIsIncomplete, setCurrentIsIncomplete] = useState(data.is_incomplete);
  const [incompleteWarningDismissed, setIncompleteWarningDismissed] = useState(false);
  const isIncomplete = data.is_incomplete && !incompleteWarningDismissed;

  // Duplicate detection state
  interface DupMatch {
    id: string;
    merchant_name: string;
    purchase_date: string | null;
    currency: string | null;
    total_amount: number;
    score: number;
  }
  const [dupMatch, setDupMatch] = useState<DupMatch | null>(null);
  const [showDupModal, setShowDupModal] = useState(false);

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

  // ── Duplicate check ────────────────────────────────────────────────────────
  const checkDuplicate = async (normPurchaseDate: string | null): Promise<boolean> => {
    try {
      const res = await fetch("http://localhost:8000/api/receipts/check-duplicate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          merchant_name: merchantName.trim(),
          purchase_date: normPurchaseDate,
          currency: currency.trim() || null,
          total_amount: parseFloat(totalAmount) || 0,
          items: items.map(it => ({
            item_name: it.name.trim(),
            quantity: it.quantity ? parseFloat(it.quantity) : null,
            unit_price: it.unit_price ? parseFloat(it.unit_price) : null,
            total_price: parseFloat(it.total_price) || 0,
          })),
        }),
      });
      if (!res.ok) return false; // if dup-check fails, let user proceed
      const data = await res.json();
      if (data.is_duplicate && data.match) {
        setDupMatch(data.match);
        setShowDupModal(true);
        return true;
      }
      return false;
    } catch {
      return false; // network error — don't block save
    }
  };

  // ── Perform actual save ───────────────────────────────────────────────────
  const doSave = async (normPurchaseDate: string | null, normDueDate: string | null) => {
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
        if (typeof detail === "string") errorMsg = detail;
        else if (Array.isArray(detail)) errorMsg = detail.map((e: any) => `${e.loc?.join(".")}: ${e.msg}`).join(", ");
        else if (typeof detail === "object" && detail !== null) errorMsg = JSON.stringify(detail);
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

  // Stored for use in "Save Anyway" path
  const [pendingSaveDates, setPendingSaveDates] = useState<{ pd: string | null; dd: string | null } | null>(null);

  const handleSave = async () => {
    if (isSaving) return;

    if (isIncomplete) {
      setSaveError("Please resolve the incomplete receipt warning before saving.");
      return;
    }

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

    // Store dates for Save Anyway path
    setPendingSaveDates({ pd: normPurchaseDate, dd: normDueDate });

    // Duplicate check
    const isDup = await checkDuplicate(normPurchaseDate);
    if (isDup) return; // modal shown — user decides

    await doSave(normPurchaseDate, normDueDate);
  };

  const handleUploadMissingPart = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (files.length >= 5) return;

    setIsUploadingMissingPart(true);
    setSaveError(null);
    try {
      const formData = new FormData();
      // Send ALL files together to Gemini
      for (const f of files) {
        formData.append("files", f);
      }
      formData.append("files", file);

      const res = await fetch("http://localhost:8000/api/documents/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error("Failed to process the multi-photo upload.");
      }

      const resData = await res.json();
      const extracted = resData.document.extracted_data;

      // Overwrite all fields with the new combined extraction
      setMerchantName(extracted.merchant_name || "");
      setPurchaseDate(extracted.purchase_date || "");
      setDueDate(extracted.due_date || "");
      setCurrency(extracted.currency || "");
      setTax(extracted.tax ? String(extracted.tax) : "");
      setTotalAmount(String(extracted.total_amount ?? "0"));
      setPaymentMethod(extracted.payment_method || "");
      setWarrantyDays(extracted.warranty_period_days ? String(extracted.warranty_period_days) : "");
      setItems(toEditable(extracted.items || []));
      setFc(extracted.field_confidences || {});

      // Re-evaluate completeness
      setCurrentIsIncomplete(extracted.is_incomplete);
      
      // Update our local files array
      setFiles((prev) => [...prev, file]);

      // If it's now complete, we can automatically dismiss the warning
      if (!extracted.is_incomplete) {
        setIncompleteWarningDismissed(true);
      }
    } catch (err: any) {
      console.error(err);
      setSaveError(err.message || "Failed to process the new image.");
    } finally {
      setIsUploadingMissingPart(false);
      if (missingPartInputRef.current) missingPartInputRef.current.value = "";
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
    { val: totalAmount, label: "Total Amount" },
    { val: purchaseDate, label: "Purchase Date" }
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

  // ── Currency symbol helper ────────────────────────────────────────────────
  const SYMBOLS: Record<string, string> = { USD: "$", INR: "₹", EUR: "€", GBP: "£", CAD: "C$", AUD: "A$" };
  const symFor = (c: string | null) => (c ? (SYMBOLS[c] ?? c + " ") : "");
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

      {/* ── Duplicate Warning Modal ── */}
      {showDupModal && dupMatch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-md bg-[#B8C5A3] rounded-3xl shadow-2xl p-8 space-y-6 border border-[#7A9B6D]">
            {/* Icon + heading */}
            <div className="flex items-start gap-4">
              <div className="p-3 bg-amber-100 rounded-2xl shrink-0">
                <AlertTriangle className="w-6 h-6 text-amber-600" />
              </div>
              <div>
                <h2 className="text-lg font-extrabold text-[#171A3A]">Receipt already exists.</h2>
                <p className="text-sm text-[#164A3A] font-support mt-1">
                  This receipt may already have been uploaded. Review the existing match below before deciding.
                </p>
              </div>
            </div>

            {/* Match details */}
            <div className="bg-white rounded-2xl p-4 space-y-2 border border-[#7A9B6D]/30">
              <p className="text-xs font-bold text-[#164A3A] uppercase tracking-widest mb-3">Existing Receipt</p>
              <div className="flex justify-between text-xs">
                <span className="text-slate-500 font-semibold">Merchant</span>
                <span className="font-bold text-[#171A3A]">{dupMatch.merchant_name}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-slate-500 font-semibold">Date</span>
                <span className="font-semibold text-[#171A3A]">{dupMatch.purchase_date || "—"}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-slate-500 font-semibold">Currency</span>
                <span className="font-semibold text-[#171A3A]">{dupMatch.currency || "—"}</span>
              </div>
              <div className="flex justify-between text-xs border-t border-slate-100 pt-2 mt-1">
                <span className="text-slate-500 font-bold">Total</span>
                <span className="font-extrabold text-[#0D7C66]">
                  {symFor(dupMatch.currency)}{dupMatch.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>
              <p className="text-[10px] text-slate-400 font-support pt-1">
                Match confidence: {Math.round(dupMatch.score * 100)}%
              </p>
            </div>

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={() => {
                  setShowDupModal(false);
                  setDupMatch(null);
                }}
                className="flex-1 py-2.5 rounded-xl text-sm font-bold text-[#171A3A] bg-white border border-[#7A9B6D]/40 hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  setShowDupModal(false);
                  setDupMatch(null);
                  if (pendingSaveDates) {
                    await doSave(pendingSaveDates.pd, pendingSaveDates.dd);
                  }
                }}
                disabled={isSaving}
                className="flex-1 py-2.5 rounded-xl text-sm font-bold text-white bg-[#7A9B6D] hover:bg-[#6B8C5E] transition-colors disabled:opacity-60"
              >
                {isSaving ? "Saving…" : "Save Anyway"}
              </button>
            </div>
          </div>
        </div>
      )}


      <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
        <div className="space-y-2">
          <h1 className="text-3xl sm:text-4xl font-extrabold text-white">Review & Save Receipt</h1>
          <p className="text-white/70 font-support max-w-lg text-sm sm:text-base leading-relaxed">
            We've extracted the details from your document. Please review the information below and make any necessary changes before saving.
          </p>
        </div>
        <div className="bg-white/10 backdrop-blur-md border border-white/20 rounded-2xl p-5 flex items-start gap-4 min-w-[280px]">
          <div className="text-white mt-1">
            <FileText className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-white/60 font-semibold uppercase tracking-wider mb-1">Document Type</p>
            <p className="text-base font-bold text-white mb-3">Purchase Receipt</p>
            <p className="text-[11px] text-white/50 font-support">Extracted on</p>
            <p className="text-xs font-semibold text-white/80">{new Date().toLocaleString()}</p>
          </div>
        </div>
      </div>

      {/* ── Incomplete Warning Banner ── */}
      {isIncomplete && (
        <div className="bg-amber-50 rounded-2xl border border-amber-200 p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-sm animate-in fade-in zoom-in duration-300">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-amber-900 font-bold mb-1">Receipt information appears incomplete.</p>
              <p className="text-sm text-amber-700 font-support">
                {files.length >= 5 
                  ? "The full receipt could not be detected even with 5 photos. Please verify the extracted fields manually."
                  : "The uploaded image may not contain the full receipt. Please upload the complete receipt to ensure accurate extraction."}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto shrink-0">
            <button
              onClick={() => setIncompleteWarningDismissed(true)}
              className="px-4 py-2 text-sm font-semibold text-amber-700 hover:bg-amber-100 rounded-lg transition-colors whitespace-nowrap flex-1 sm:flex-none text-center"
            >
              Dismiss
            </button>
            {files.length < 5 && (
              <>
                <input
                  type="file"
                  ref={missingPartInputRef}
                  accept="image/*"
                  className="hidden"
                  onChange={handleUploadMissingPart}
                />
                <button
                  onClick={() => missingPartInputRef.current?.click()}
                  disabled={isUploadingMissingPart}
                  className="px-4 py-2 text-sm font-bold text-white bg-amber-600 hover:bg-amber-700 rounded-lg shadow-sm transition-colors whitespace-nowrap flex-1 sm:flex-none text-center disabled:opacity-70 flex items-center justify-center gap-2"
                >
                  {isUploadingMissingPart ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  {isUploadingMissingPart ? "Processing..." : "Add another photo"}
                </button>
              </>
            )}
          </div>
        </div>
      )}

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
        <div className="bg-[#B8C5A3] rounded-2xl border border-[#7A9B6D] p-4 flex flex-col gap-2 shadow-sm">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-[#171A3A] shrink-0 mt-0.5" />
            <p className="text-sm text-[#171A3A] font-support">
              <span className="font-bold">Missing required fields:</span> {missingFields.join(", ")}. Please fill them in before saving.
            </p>
          </div>
          {!purchaseDate && (
            <div className="ml-8 text-sm text-amber-900 bg-amber-50 rounded-lg p-2 border border-amber-200">
              <span className="font-bold">Purchase date not detected.</span> Please select the correct date.
            </div>
          )}
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
