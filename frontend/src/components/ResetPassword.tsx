import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Eye, EyeOff, CheckCircle2 } from "lucide-react";
import logoImg from "../assets/TracePaylogo.png";

type ResetState = "EMAIL" | "SENT" | "NEW_PASSWORD" | "SUCCESS";

export const ResetPassword: React.FC = () => {
  const [step, setStep] = useState<ResetState>("EMAIL");
  const [email, setEmail] = useState("");
  
  // New Password state
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const maskEmail = (emailStr: string) => {
    if (!emailStr) return "";
    const [name, domain] = emailStr.split("@");
    if (!domain) return emailStr;
    const maskedName = name.length > 1 ? `${name[0]}*` : "*";
    return `${maskedName}@${domain}`;
  };

  const handleSendLink = (e: React.FormEvent) => {
    e.preventDefault();
    setStep("SENT");
  };

  const handleUpdatePassword = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      alert("Passwords do not match");
      return;
    }
    setStep("SUCCESS");
  };

  return (
    <div className="flex-1 flex items-center justify-center p-4">
      <div className="w-full max-w-[340px] bg-[#F5F3EA] rounded-3xl shadow-2xl overflow-hidden border border-white/20 p-5 sm:p-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        
        {/* Logo */}
        <div className="flex justify-center mb-5">
          <img src={logoImg} alt="TracePay" className="h-6 w-auto" />
        </div>

        {step === "EMAIL" && (
          <div className="animate-in fade-in duration-300">
            <div className="text-center mb-5">
              <h2 className="text-xl font-bold text-[#171A3A]">Reset your password</h2>
              <p className="text-[#171A3A]/70 text-[13px] mt-2 font-medium leading-relaxed px-1">
                Enter the email you used to create your TracePay account and we'll send you a link to reset your password.
              </p>
            </div>

            <form onSubmit={handleSendLink} className="space-y-4">
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-[#171A3A]">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="w-full bg-white border border-[#171A3A]/10 rounded-xl px-4 py-2 text-sm text-[#171A3A] font-medium focus:outline-none focus:border-[#7A9B6D] focus:ring-1 focus:ring-[#7A9B6D] transition-colors shadow-sm placeholder:text-[#171A3A]/30"
                  required
                />
              </div>

              <button
                type="submit"
                className="w-full bg-[#7A9B6D] hover:bg-[#7A9B6D]/90 text-white font-bold py-2.5 px-4 rounded-xl shadow-md hover:shadow-lg transition-all active:scale-[0.98] text-sm"
              >
                Send reset link
              </button>
            </form>
          </div>
        )}

        {step === "SENT" && (
          <div className="animate-in fade-in duration-300 text-center">
            <div className="flex justify-center mb-4">
              <div className="w-12 h-12 bg-[#7A9B6D]/10 rounded-full flex items-center justify-center">
                <CheckCircle2 className="w-6 h-6 text-[#7A9B6D]" strokeWidth={2.5} />
              </div>
            </div>
            <h2 className="text-xl font-bold text-[#171A3A]">Check your email</h2>
            <p className="text-[#171A3A]/70 text-[13px] mt-2 font-medium leading-relaxed px-1">
              We've sent a password reset link to <span className="font-bold text-[#171A3A]">{maskEmail(email || "user@example.com")}</span>
            </p>
            <p className="text-[#171A3A]/70 text-[13px] mt-2 font-medium leading-relaxed">
              Open the link in your email to continue.
            </p>
            
            <div className="mt-6 space-y-3">
              <button
                onClick={() => setStep("NEW_PASSWORD")} // Simulating click from email
                className="w-full bg-white border border-[#171A3A]/10 hover:bg-slate-50 text-[#171A3A] font-semibold py-2.5 px-4 rounded-xl shadow-sm transition-all text-sm"
              >
                Resend link
              </button>
              <p className="text-[10px] text-[#171A3A]/40 uppercase tracking-widest font-bold">For Preview:</p>
              <button
                onClick={() => setStep("NEW_PASSWORD")}
                className="w-full bg-[#7A9B6D]/10 text-[#164A3A] font-bold py-2 px-4 rounded-xl text-xs hover:bg-[#7A9B6D]/20 transition-all"
              >
                Simulate clicking email link
              </button>
            </div>
          </div>
        )}

        {step === "NEW_PASSWORD" && (
          <div className="animate-in fade-in duration-300">
            <div className="text-center mb-5">
              <h2 className="text-xl font-bold text-[#171A3A]">Create a new password</h2>
            </div>

            <form onSubmit={handleUpdatePassword} className="space-y-4">
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-[#171A3A]">New Password</label>
                <div className="relative">
                  <input
                    type={showNewPassword ? "text" : "password"}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Enter new password"
                    className="w-full bg-white border border-[#171A3A]/10 rounded-xl pl-4 pr-11 py-2 text-sm text-[#171A3A] font-medium focus:outline-none focus:border-[#7A9B6D] focus:ring-1 focus:ring-[#7A9B6D] transition-colors shadow-sm placeholder:text-[#171A3A]/30"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPassword(!showNewPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#171A3A]/40 hover:text-[#171A3A]/70 transition-colors p-1"
                  >
                    {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-[#171A3A]">Confirm Password</label>
                <div className="relative">
                  <input
                    type={showConfirmPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Confirm new password"
                    className={`w-full bg-white border rounded-xl pl-4 pr-11 py-2 text-sm text-[#171A3A] font-medium focus:outline-none focus:ring-1 transition-colors shadow-sm placeholder:text-[#171A3A]/30 ${
                      confirmPassword && newPassword !== confirmPassword 
                        ? 'border-red-400 focus:border-red-500 focus:ring-red-500' 
                        : 'border-[#171A3A]/10 focus:border-[#7A9B6D] focus:ring-[#7A9B6D]'
                    }`}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#171A3A]/40 hover:text-[#171A3A]/70 transition-colors p-1"
                  >
                    {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {confirmPassword && newPassword !== confirmPassword && (
                  <p className="text-[11px] text-red-500 font-semibold mt-1">Passwords do not match.</p>
                )}
              </div>

              <button
                type="submit"
                disabled={!newPassword || newPassword !== confirmPassword}
                className="w-full mt-2 bg-[#7A9B6D] hover:bg-[#7A9B6D]/90 disabled:opacity-50 disabled:hover:bg-[#7A9B6D] text-white font-bold py-2.5 px-4 rounded-xl shadow-md hover:shadow-lg transition-all active:scale-[0.98] text-sm"
              >
                Update password
              </button>
            </form>
          </div>
        )}

        {step === "SUCCESS" && (
          <div className="animate-in zoom-in-95 duration-500 text-center">
            <div className="flex justify-center mb-4">
              <div className="w-12 h-12 bg-[#7A9B6D]/10 rounded-full flex items-center justify-center">
                <CheckCircle2 className="w-6 h-6 text-[#7A9B6D]" strokeWidth={2.5} />
              </div>
            </div>
            <h2 className="text-xl font-bold text-[#171A3A]">Password updated successfully</h2>
            <p className="text-[#171A3A]/70 text-[13px] mt-2 font-medium leading-relaxed px-1">
              Your password has been changed. You can now sign in with your new password.
            </p>
            
            <div className="mt-6">
              <Link to="/login" className="w-full inline-block bg-[#164A3A] hover:bg-[#164A3A]/90 text-white font-bold py-2.5 px-4 rounded-xl shadow-md hover:shadow-lg transition-all active:scale-[0.98] text-sm">
                Return to sign in
              </Link>
            </div>
          </div>
        )}

        {/* Return to Sign In (Global for EMAIL and SENT states) */}
        {(step === "EMAIL" || step === "SENT") && (
          <div className="mt-6 text-center">
            <Link to="/login" className="text-xs font-bold text-[#164A3A] hover:text-[#7A9B6D] transition-colors flex items-center justify-center gap-1.5">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Return to Sign In
            </Link>
          </div>
        )}

      </div>
    </div>
  );
};
