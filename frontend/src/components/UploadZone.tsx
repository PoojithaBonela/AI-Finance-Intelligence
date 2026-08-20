import React, { useState, useRef } from "react";
import { Upload, FileImage, FileText, AlertCircle, Loader2, Images } from "lucide-react";
import { ReceiptVerificationForm, type ExtractedReceiptData } from "./ReceiptVerificationForm";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";



interface UploadedDoc {
  original_filename: string;
  file_type: string;
  image_count: number;
  cloudinary_url: string;
  cloudinary_public_id: string;
  extracted_data: ExtractedReceiptData;
  files: File[];
}

const MAX_IMAGES = 5;
const MAX_BYTES = 10 * 1024 * 1024;

export const UploadZone: React.FC = () => {
  const { session } = useAuth();
  const navigate = useNavigate();
  const [dragActiveType, setDragActiveType] = useState<"physical" | "digital" | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [docType, setDocType] = useState<"physical" | "digital" | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successDoc, setSuccessDoc] = useState<UploadedDoc | null>(null);
  const [showAuthModal, setShowAuthModal] = useState(false);

  const fileInputRefPhysical = useRef<HTMLInputElement>(null);
  const fileInputRefDigital = useRef<HTMLInputElement>(null);

  // ── Drag handlers ──────────────────────────────────────────────────────────
  const handleDrag = (e: React.DragEvent, type: "physical" | "digital") => {
    e.preventDefault(); e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActiveType(type);
    else if (e.type === "dragleave") setDragActiveType(null);
  };

  // ── File validation ────────────────────────────────────────────────────────
  const validateAndSetFiles = (incoming: File[], type: "physical" | "digital") => {
    if (!session) {
      setShowAuthModal(true);
      return;
    }
    setErrorMsg(null);
    setSuccessDoc(null);

    if (type === "physical" && incoming.length > MAX_IMAGES) {
      setErrorMsg(`You can upload at most ${MAX_IMAGES} images at once for a long receipt.`);
      return;
    }

    const allowed = type === "physical" ? ["jpg", "jpeg", "png"] : ["pdf"];
    for (const file of incoming) {
      const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
      if (!allowed.includes(ext)) {
        setErrorMsg(
          type === "physical"
            ? "Only JPG, JPEG, or PNG images are accepted for physical receipts."
            : "Only PDF files are accepted for digital receipts/invoices."
        );
        return;
      }
      if (file.size > MAX_BYTES) {
        setErrorMsg(`'${file.name}' exceeds the 10 MB size limit.`);
        return;
      }
    }
    setSelectedFiles(incoming);
    setDocType(type);
  };

  const handleDrop = (e: React.DragEvent, type: "physical" | "digital") => {
    e.preventDefault(); e.stopPropagation();
    setDragActiveType(null);
    if (e.dataTransfer.files?.length) validateAndSetFiles(Array.from(e.dataTransfer.files), type);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, type: "physical" | "digital") => {
    if (e.target.files?.length) validateAndSetFiles(Array.from(e.target.files), type);
    e.target.value = "";
  };

  const removeFile = (idx: number) => {
    setSelectedFiles((prev) => {
      const next = prev.filter((_, i) => i !== idx);
      if (next.length === 0) setDocType(null);
      return next;
    });
  };

  const triggerFileInput = (type: "physical" | "digital") => {
    if (!session) {
      setShowAuthModal(true);
      return;
    }
    if (isUploading) return;
    if (type === "physical") fileInputRefPhysical.current?.click();
    else fileInputRefDigital.current?.click();
  };

  // ── Upload ─────────────────────────────────────────────────────────────────
  const uploadFiles = async () => {
    if (!selectedFiles.length || !docType || isUploading) return;
    setIsUploading(true);
    setErrorMsg(null);
    setUploadProgress(10);

    const formData = new FormData();
    for (const file of selectedFiles) formData.append("files", file);

    const tick = setInterval(() => {
      setUploadProgress((p) => (p >= 85 ? (clearInterval(tick), 85) : p + 8));
    }, 180);

    try {
      const headers: Record<string, string> = {};
      if (session?.access_token) {
        headers["Authorization"] = `Bearer ${session.access_token}`;
      }

      const response = await fetch("/api/documents/upload", { 
        method: "POST", 
        body: formData,
        headers
      });
      clearInterval(tick);
      const data = await response.json();

      if (!response.ok) {
        const d = data.detail;
        throw new Error(typeof d === "object" && d?.message ? d.message : (typeof d === "string" ? d : "Upload failed."));
      }

      setUploadProgress(100);
      setSuccessDoc({
        original_filename: data.document.original_filename,
        file_type: data.document.file_type,
        image_count: data.document.image_count,
        cloudinary_url: data.cloudinary_url,
        cloudinary_public_id: data.cloudinary_public_id,
        extracted_data: {
          ...data.document.extracted_data,
          field_confidences: data.document.extracted_data.field_confidences ?? {},
        },
        files: selectedFiles,
      });
      // We do NOT clear selectedFiles here anymore, we pass them down
      setDocType(null);
    } catch (err: any) {
      setErrorMsg(err.message || "An unexpected error occurred during receipt upload.");
    } finally {
      setIsUploading(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (!bytes) return "0 B";
    const sizes = ["B", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
  };

  // ── If extraction done → hand off to verification form ────────────────────
  if (successDoc) {
    return (
      <ReceiptVerificationForm
        data={successDoc.extracted_data}
        cloudinaryPublicId={successDoc.cloudinary_public_id}
        filename={successDoc.original_filename}
        initialFiles={successDoc.files}
        onClose={() => {
          setSuccessDoc(null);
          setUploadProgress(0);
          setSelectedFiles([]);
        }}
      />
    );
  }

  // ── Upload UI ──────────────────────────────────────────────────────────────
  return (
    <div className="w-full max-w-4xl mx-auto space-y-8">

      {/* Drop zone cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        {/* PHYSICAL */}
        <div
          onDragEnter={(e) => !isUploading && handleDrag(e, "physical")}
          onDragOver={(e) => !isUploading && handleDrag(e, "physical")}
          onDragLeave={(e) => !isUploading && handleDrag(e, "physical")}
          onDrop={(e) => !isUploading && handleDrop(e, "physical")}
          onClick={() => triggerFileInput("physical")}
          className={`relative rounded-3xl p-8 flex flex-col items-center justify-center cursor-pointer transition-all duration-300 min-h-[240px]
            ${isUploading ? "opacity-50 cursor-not-allowed" : ""}
            ${dragActiveType === "physical"
              ? "border-2 border-[#171A3A] shadow-lg scale-[1.02]"
              : "border border-[#171A3A]/25 hover:border-[#171A3A]/50 hover:shadow-md"
            }`}
          style={{ backgroundColor: "#F5F3EA" }}
        >
          <input ref={fileInputRefPhysical} type="file" className="hidden" accept=".jpg,.jpeg,.png" multiple disabled={isUploading} onChange={(e) => handleFileChange(e, "physical")} />
          <div className="w-14 h-14 rounded-2xl bg-[#0D7C66]/10 flex items-center justify-center mb-5">
            <FileImage className="w-7 h-7 text-[#0D7C66]" strokeWidth={1.5} />
          </div>
          <h3 className="text-lg font-medium text-[#171A3A]">Physical Receipt</h3>
          <p className="text-sm text-[#164A3A] mt-2 text-center max-w-[240px]">
            Upload 1–{MAX_IMAGES} photos of the same receipt (JPG/JPEG/PNG).
          </p>
          <div className="mt-4 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#0D7C66]/8 text-xs text-[#164A3A] font-medium border border-[#0D7C66]/15">
            <Images className="w-3.5 h-3.5 text-[#0D7C66]" /><span>Multi-photo long receipts supported</span>
          </div>
        </div>

        {/* DIGITAL */}
        <div
          onDragEnter={(e) => !isUploading && handleDrag(e, "digital")}
          onDragOver={(e) => !isUploading && handleDrag(e, "digital")}
          onDragLeave={(e) => !isUploading && handleDrag(e, "digital")}
          onDrop={(e) => !isUploading && handleDrop(e, "digital")}
          onClick={() => triggerFileInput("digital")}
          className={`relative rounded-3xl p-8 flex flex-col items-center justify-center cursor-pointer transition-all duration-300 min-h-[240px]
            ${isUploading ? "opacity-50 cursor-not-allowed" : ""}
            ${dragActiveType === "digital"
              ? "border-2 border-[#171A3A] shadow-lg scale-[1.02]"
              : "border border-[#171A3A]/25 hover:border-[#171A3A]/50 hover:shadow-md"
            }`}
          style={{ backgroundColor: "#F5F3EA" }}
        >
          <input ref={fileInputRefDigital} type="file" className="hidden" accept=".pdf" disabled={isUploading} onChange={(e) => handleFileChange(e, "digital")} />
          <div className="w-14 h-14 rounded-2xl bg-[#0D7C66]/10 flex items-center justify-center mb-5">
            <FileText className="w-7 h-7 text-[#0D7C66]" strokeWidth={1.5} />
          </div>
          <h3 className="text-lg font-medium text-[#171A3A]">Digital Invoice</h3>
          <p className="text-sm text-[#164A3A] mt-2 text-center max-w-[240px]">
            Upload a native PDF e-receipt, invoice, or bill.
          </p>
        </div>
      </div>

      {/* Action panel */}
      <div className={`rounded-3xl p-6 shadow-lg transition-all duration-300 ${
        selectedFiles.length > 0 && docType
          ? "bg-[#F5F3EA] border border-[#171A3A]/15"
          : "bg-[#B8C5A3] border border-[#9DB38A]"
      }`}>

        {selectedFiles.length > 0 && docType ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-[#171A3A]/10 pb-4">
              <p className="text-sm font-medium text-[#171A3A]">
                {selectedFiles.length === 1 ? "1 file selected" : `${selectedFiles.length} images selected (long receipt)`}
              </p>
              <button onClick={() => { setSelectedFiles([]); setDocType(null); setErrorMsg(null); }} disabled={isUploading} className="text-xs font-medium text-[#171A3A]/60 hover:text-[#171A3A] transition-colors disabled:opacity-40">
                Clear all
              </button>
            </div>

            <div className="space-y-2 max-h-[180px] overflow-y-auto pr-1">
              {selectedFiles.map((file, idx) => (
                <div key={idx} className="flex items-center gap-4 p-3 rounded-2xl bg-white/60 border border-[#171A3A]/10">
                  <div className="p-2 rounded-xl shrink-0 bg-[#0D7C66]/10">
                    {docType === "physical" ? <FileImage className="w-4 h-4 text-[#0D7C66]" /> : <FileText className="w-4 h-4 text-[#0D7C66]" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[#171A3A] truncate">{file.name}</p>
                    <p className="text-xs text-[#171A3A]/50">{formatBytes(file.size)}</p>
                  </div>
                  {!isUploading && (
                    <button onClick={(e) => { e.stopPropagation(); removeFile(idx); }} className="text-[#171A3A]/40 hover:text-rose-500 transition-colors shrink-0">
                      <span className="text-sm">✕</span>
                    </button>
                  )}
                </div>
              ))}
            </div>

            <button
              onClick={uploadFiles}
              disabled={isUploading}
              className="w-full mt-4 py-3.5 text-sm font-medium text-white rounded-2xl shadow-md transition-all active:scale-[0.98] flex items-center justify-center gap-2 hover:opacity-90 disabled:opacity-60 bg-[#7A9B6D] hover:bg-[#6B8C5E]"
            >
              {isUploading
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Validating &amp; Analysing with Gemini…</>
                : <><Upload className="w-4 h-4" /> Upload &amp; Extract ({selectedFiles.length} {selectedFiles.length === 1 ? "file" : "images"})</>
              }
            </button>
          </div>
        ) : null}

        {/* Progress */}
        {isUploading && (
          <div className="mt-5">
            <div className="flex justify-between text-xs text-[#171A3A]/70 font-medium mb-2">
              <span>Running Gemini Vision + validation…</span><span>{uploadProgress}%</span>
            </div>
            <div className="w-full bg-[#171A3A]/10 rounded-full h-1.5 overflow-hidden">
              <div className="h-full transition-all duration-200 bg-[#0D7C66]" style={{ width: `${uploadProgress}%` }} />
            </div>
          </div>
        )}

        {/* Error */}
        {errorMsg && (
          <div className="mt-5 flex items-start gap-3 p-4 bg-rose-50 text-rose-600 rounded-2xl border border-rose-200">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-sm">Upload Rejected</p>
              <p className="text-sm mt-1">{errorMsg}</p>
            </div>
          </div>
        )}

        {!selectedFiles.length && !errorMsg && (
          <p className="text-center text-sm text-white/90 py-4">
            Select a document class above to begin loading your expense documents.
          </p>
        )}
      </div>

      {/* Auth Modal */}
      {showAuthModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-sm bg-[#F5F3EA] rounded-3xl shadow-2xl overflow-hidden p-6 text-center animate-in zoom-in-95 duration-300">
            <div className="w-14 h-14 bg-[#164A3A]/10 rounded-full flex items-center justify-center mx-auto mb-4">
              <AlertCircle className="w-7 h-7 text-[#164A3A]" strokeWidth={2} />
            </div>
            <h3 className="text-xl font-bold text-[#171A3A] mb-2">Sign in to continue</h3>
            <p className="text-sm text-[#171A3A]/70 font-medium mb-6 leading-relaxed">
              You need an account to upload, verify, and track your receipts.
            </p>
            <div className="flex flex-col gap-3">
              <button
                onClick={() => navigate("/login")}
                className="w-full bg-[#164A3A] hover:bg-[#164A3A]/90 text-white font-bold py-2.5 rounded-xl shadow-md transition-all text-sm"
              >
                Sign In
              </button>
              <button
                onClick={() => setShowAuthModal(false)}
                className="w-full bg-white border border-[#171A3A]/10 hover:bg-slate-50 text-[#171A3A] font-semibold py-2.5 rounded-xl shadow-sm transition-all text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
