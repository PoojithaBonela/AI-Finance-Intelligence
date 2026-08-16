import React, { useEffect, useState } from "react";
import { Loader2, FileText, ExternalLink, RefreshCw, X } from "lucide-react";

interface ReceiptItem {
  item_name: string;
  quantity: number | null;
  unit_price: number | null;
  total_price: number;
}

interface Receipt {
  id: string;
  merchant_name: string;
  purchase_date: string | null;
  document_type: string | null;
  currency: string | null;
  total_amount: number;
  tax: number | null;
  payment_method: string | null;
  due_date: string | null;
  warranty_period_days: number | null;
  cloudinary_public_id: string | null;
  cloudinary_resource_type: string | null;
  original_filename: string | null;
  items: ReceiptItem[];
}

export const PurchasesList: React.FC = () => {
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedReceipt, setSelectedReceipt] = useState<Receipt | null>(null);

  const fetchReceipts = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch("http://localhost:8000/api/receipts");
      if (!res.ok) {
        throw new Error("Failed to fetch purchases data.");
      }
      const data = await res.json();
      setReceipts(data);
    } catch (err: any) {
      setError(err.message || "An unknown error occurred.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReceipts();
  }, []);

  const formatCurrency = (val: number, currencyCode: string | null) => {
    const amount = val.toFixed(2);
    if (!currencyCode) return amount;
    const symbols: Record<string, string> = { USD: "$", INR: "₹", EUR: "€", GBP: "£", CAD: "C$", AUD: "A$" };
    const symbol = symbols[currencyCode] || currencyCode + " ";
    return `${symbol}${amount}`;
  };

  if (loading) {
    return (
      <div className="w-full h-64 flex flex-col items-center justify-center">
        <Loader2 className="w-8 h-8 text-brand-teal animate-spin mb-4" />
        <p className="text-slate-400 font-support">Loading your purchases...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full max-w-3xl mx-auto mt-12 bg-rose-50 rounded-2xl p-8 text-center border border-rose-100">
        <p className="text-rose-600 font-semibold mb-4">{error}</p>
        <button
          onClick={fetchReceipts}
          className="flex items-center gap-2 mx-auto px-5 py-2.5 bg-white border border-rose-200 rounded-lg text-rose-600 hover:bg-rose-100 transition-colors"
        >
          <RefreshCw className="w-4 h-4" /> Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl mx-auto pt-10 pb-20 px-4 sm:px-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="mb-8">
        <h1 className="text-3xl font-extrabold text-white tracking-tight">Purchases</h1>
        <p className="text-slate-400 font-support text-sm mt-1">
          Detailed log of your verified receipts and expenses.
        </p>
      </div>

      {receipts.length === 0 ? (
        <div className="bg-brand-cream rounded-[32px] p-12 text-center shadow-xl">
          <FileText className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <h3 className="text-xl font-bold text-brand-navy">No purchases found</h3>
          <p className="text-slate-500 mt-2">You haven't saved any verified receipts yet.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {receipts.map((r) => (
            <div key={r.id} className="rounded-xl shadow-md overflow-hidden border border-slate-200 flex flex-col" style={{ backgroundColor: "#E9ECE4" }}>
              
              {/* Header */}
              <div className="px-4 py-3 flex items-center justify-between border-b border-slate-300">
                <div>
                  <h2 className="text-sm font-bold text-slate-800">{r.merchant_name}</h2>
                  <p className="text-xs text-slate-600 mt-0.5">
                    {r.purchase_date || "Date unknown"} • {r.document_type || "Receipt"}
                  </p>
                </div>
                {r.cloudinary_public_id && (
                  <button 
                    onClick={() => setSelectedReceipt(r)}
                    className="flex items-center gap-1.5 text-xs font-bold text-brand-violet hover:text-brand-teal transition-colors shrink-0 bg-white/50 px-3 py-1.5 rounded"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>View Receipt</span>
                  </button>
                )}
              </div>

              {/* Items Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse min-w-[500px]">
                  <thead>
                    <tr className="border-b border-slate-300">
                      <th className="py-1.5 px-4 text-[11px] font-bold text-slate-600 uppercase tracking-widest w-1/2">Item</th>
                      <th className="py-1.5 px-4 text-[11px] font-bold text-slate-600 uppercase tracking-widest text-right">Qty</th>
                      <th className="py-1.5 px-4 text-[11px] font-bold text-slate-600 uppercase tracking-widest text-right">Unit Price</th>
                      <th className="py-1.5 px-4 text-[11px] font-bold text-slate-600 uppercase tracking-widest text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-300">
                    {r.items.length > 0 ? (
                      r.items.map((item, idx) => (
                        <tr key={idx} className="hover:bg-black/5 transition-colors">
                          <td className="py-1.5 px-4 text-xs font-semibold text-slate-800">
                            {item.item_name}
                          </td>
                          <td className="py-1.5 px-4 text-xs text-slate-600 text-right">
                            {item.quantity != null ? item.quantity : <span className="text-slate-400">—</span>}
                          </td>
                          <td className="py-1.5 px-4 text-xs text-slate-600 text-right">
                            {item.unit_price != null ? formatCurrency(item.unit_price, r.currency) : <span className="text-slate-400">—</span>}
                          </td>
                          <td className="py-1.5 px-4 text-xs font-bold text-slate-800 text-right">
                            {formatCurrency(item.total_price, r.currency)}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={4} className="py-3 text-center text-xs text-slate-500 font-support">
                          No items extracted for this receipt.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Summary Section */}
              <div className="border-t border-slate-300 px-4 py-3 flex flex-col items-end gap-1.5">
                <div className="flex items-center justify-between w-full sm:w-48 text-[11px]">
                  <span className="text-slate-600 font-semibold">Tax</span>
                  <span className="text-slate-800 font-semibold">
                    {r.tax != null ? formatCurrency(r.tax, r.currency) : <span className="text-slate-400">—</span>}
                  </span>
                </div>
                
                <div className="flex items-center justify-between w-full sm:w-48 text-[11px]">
                  <span className="text-slate-600 font-semibold">Payment Method</span>
                  <span className="text-slate-800 font-semibold">
                    {r.payment_method || <span className="text-slate-400">—</span>}
                  </span>
                </div>

                <div className="flex items-center justify-between w-full sm:w-48 text-[11px]">
                  <span className="text-slate-600 font-semibold">Due Date</span>
                  <span className="text-slate-800 font-semibold">
                    {r.due_date || <span className="text-slate-400">—</span>}
                  </span>
                </div>

                <div className="flex items-center justify-between w-full sm:w-48 text-[11px] border-b border-slate-300 pb-1.5">
                  <span className="text-slate-600 font-semibold">Warranty</span>
                  <span className="text-slate-800 font-semibold">
                    {r.warranty_period_days != null ? `${r.warranty_period_days} days` : <span className="text-slate-400">—</span>}
                  </span>
                </div>

                <div className="flex items-center justify-between w-full sm:w-48 text-sm mt-1">
                  <span className="font-extrabold text-slate-800">Total</span>
                  <span className="font-extrabold text-slate-900 tracking-tight">
                    {formatCurrency(r.total_amount, r.currency)}
                  </span>
                </div>
              </div>

            </div>
          ))}
        </div>
      )}

      {/* View Receipt Modal */}
      {selectedReceipt && selectedReceipt.cloudinary_public_id && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="relative w-full max-w-4xl bg-black rounded-lg shadow-2xl overflow-hidden flex flex-col">
            <div className="absolute top-4 right-4 z-10">
              <button 
                onClick={() => setSelectedReceipt(null)}
                className="p-2 bg-white/10 hover:bg-white/20 rounded-full text-white transition-colors backdrop-blur-md"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="w-full h-auto max-h-[85vh] overflow-auto flex items-center justify-center">
              {selectedReceipt.original_filename?.toLowerCase().endsWith(".pdf") ? (
                <iframe 
                  src={`https://res.cloudinary.com/iplgysjg/${selectedReceipt.cloudinary_resource_type || "image"}/upload/${selectedReceipt.cloudinary_public_id}.pdf`}
                  title="Receipt PDF"
                  className="w-full h-[85vh] border-0"
                />
              ) : (
                <img 
                  src={`https://res.cloudinary.com/iplgysjg/${selectedReceipt.cloudinary_resource_type || "image"}/upload/${selectedReceipt.cloudinary_public_id}`}
                  alt="Receipt Document"
                  className="max-w-full h-auto object-contain"
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
