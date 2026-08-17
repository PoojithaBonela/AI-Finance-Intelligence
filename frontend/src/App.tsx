import React from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { UploadZone } from "./components/UploadZone";
import { Navbar } from "./components/Navbar";
import { Sparkles, ScanLine, ShieldCheck } from "lucide-react";
import { ReceiptsList } from "./components/ReceiptsList";
import { PurchasesList } from "./components/PurchasesList";
import { Login } from "./components/Login";
import { Signup } from "./components/Signup";
import { ResetPassword } from "./components/ResetPassword";
import billsimage from "./assets/billsimage.png";

function UploadPage() {
  return (
    <div className="w-full flex flex-col -mt-24 pt-32">
      {/* Hero Section */}
      <div className="relative w-full pb-16 px-4">

        {/* 2-Column Hero */}
        <section className="relative z-10 max-w-5xl mx-auto flex flex-col md:flex-row items-center gap-10 lg:gap-16 mt-8 md:mt-12">
          {/* Left Side */}
          <div className="flex-1 space-y-5 text-center md:text-left overflow-hidden md:pl-12 lg:pl-20">
            <h1 className="text-3xl md:text-4xl lg:text-5xl font-medium text-white tracking-tight leading-tight flex flex-col items-center md:items-start">
              <span className="animate-typing-1 inline-block text-left w-full max-w-fit">Your purchases,</span>
              <span className="animate-typing-2 inline-block text-left w-full max-w-fit">at a glance.</span>
            </h1>
            <p className="text-white/80 text-base md:text-lg font-support max-w-md mx-auto md:mx-0 leading-relaxed">
              Extract, verify, and organize your receipts effortlessly — without the paperwork.
            </p>
            <div className="pt-2 flex justify-center md:justify-start">
              <button className="px-6 py-3 rounded-xl bg-[#7A9B6D] text-white font-medium text-sm shadow-[0_0_24px_rgba(122,155,109,0.3)] hover:shadow-[0_0_32px_rgba(122,155,109,0.5)] transition-all hover:-translate-y-0.5">
                Upload a Receipt &rarr;
              </button>
            </div>
          </div>
          
          {/* Right Side */}
          <div className="flex-1 relative w-full max-w-md mx-auto md:max-w-lg">
            <div className="relative w-full origin-center">
              <img 
                src={billsimage} 
                alt="Receipts and Bills" 
                className="w-full h-auto drop-shadow-[0_20px_50px_rgba(0,191,166,0.2)]"
              />
            </div>
            {/* Handwritten annotation — below image */}
            <div className="mt-6 max-w-[260px] mx-auto pointer-events-none select-none">
              <svg className="absolute -mt-4 -ml-3 w-8 h-8 text-[#00BFA6] opacity-60" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <path d="M4 20 C8 12, 14 28, 18 16 C22 4, 26 22, 30 14" />
              </svg>
              <p className="text-[15px] leading-relaxed text-white/50 italic" style={{ fontFamily: "'Caveat', cursive" }}>
                Your receipts have enough <span className="text-[#00BFA6]">stories</span> to tell.<br/>
                You shouldn't have to type them all out.
              </p>
              <svg className="mt-1.5 ml-auto w-12 h-5 text-[#00BFA6] opacity-40" viewBox="0 0 40 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <path d="M2 8 C8 2, 14 14, 20 8 C26 2, 32 14, 38 8" />
              </svg>
            </div>
          </div>
        </section>

        {/* Feature Highlights */}
        <section className="relative z-10 mt-32 md:mt-40 max-w-3xl mx-auto flex flex-col sm:flex-row items-center justify-center gap-16 sm:gap-20 px-4">
          <div className="flex flex-col items-center gap-3 text-center animate-icon-1">
            <div className="w-16 h-16 rounded-2xl border-2 border-[#7A9B6D]/30 bg-[#7A9B6D]/5 flex items-center justify-center">
              <ScanLine className="w-8 h-8 text-[#7A9B6D]" strokeWidth={1.5} />
            </div>
            <span className="font-medium text-sm text-white/90">Automated<br/>OCR</span>
          </div>
          <div className="flex flex-col items-center gap-3 text-center animate-icon-2">
            <div className="w-16 h-16 rounded-2xl border-2 border-[#7A9B6D]/30 bg-[#7A9B6D]/5 flex items-center justify-center">
              <Sparkles className="w-8 h-8 text-[#7A9B6D]" strokeWidth={1.5} />
            </div>
            <span className="font-medium text-sm text-white/90">Smart<br/>Classification</span>
          </div>
          <div className="flex flex-col items-center gap-3 text-center animate-icon-3">
            <div className="w-16 h-16 rounded-2xl border-2 border-[#7A9B6D]/30 bg-[#7A9B6D]/5 flex items-center justify-center">
              <ShieldCheck className="w-8 h-8 text-[#7A9B6D]" strokeWidth={1.5} />
            </div>
            <span className="font-medium text-sm text-white/90">Secure<br/>Processing</span>
          </div>
        </section>
      </div>

      {/* UPLOAD SECTION */}
      <div className="flex-1 w-full pb-16">
        
        {/* Section Heading */}
        <section className="relative z-10 max-w-4xl mx-auto text-center space-y-4 px-6 mt-10">
          <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight text-white leading-tight">
            Intelligent expense data extraction.<br/>
            <span className="text-[#0D7C66]">
              Upload your receipts.
            </span>
          </h2>
        </section>

        {/* Existing Upload Section */}
        <section className="relative z-10 w-full max-w-6xl mx-auto px-4 sm:px-6 mt-12">
          <UploadZone />
        </section>

        <p className="text-center text-sm font-support text-white/50 max-w-2xl mx-auto px-6 mt-12">
          Upload physical receipt photos or native digital invoices. Our advanced vision models classify, extract, and structure your transactions instantly.
        </p>
      </div>
    </div>
  );
}

function App() {
  const location = useLocation();
  const isAuthPage = ["/login", "/signup", "/reset-password"].includes(location.pathname);

  return (
    <div className="flex flex-col min-h-screen bg-[#11152F] text-white relative overflow-hidden">
      {/* Global Moving Turquoise Gradient */}
      <div className="absolute top-[-20%] left-[-10%] w-[120%] h-[1200px] bg-gradient-to-br from-transparent via-[#00BFA6]/15 to-[#55D6C2]/10 blur-[120px] rounded-full pointer-events-none animate-pan z-0"></div>
      
      <div className="relative z-10 flex flex-col min-h-screen">
        {!isAuthPage && <Navbar />}
        <main className={`flex-1 flex flex-col ${isAuthPage ? '' : 'pb-16'}`}>
          <Routes>
            <Route path="/" element={<Navigate to="/upload" replace />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/receipts" element={<ReceiptsList />} />
            <Route path="/purchases" element={<PurchasesList />} />
          </Routes>
        </main>
        {!isAuthPage && (
          <footer className="py-6 text-center text-xs text-white/40 font-support">
            &copy; {new Date().getFullYear()} TracePay Intelligence. All rights reserved.
          </footer>
        )}
      </div>
    </div>
  );
}

export default App;
