import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Eye, EyeOff, CheckCircle2 } from "lucide-react";
import logoImg from "../assets/TracePaylogo.png";

export const Signup: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Auth logic will go here
  };

  return (
    <div className="flex-1 flex items-center justify-center p-4 sm:p-8 animate-in fade-in duration-500">
      <div className="w-full max-w-[760px] flex flex-col md:flex-row rounded-3xl overflow-hidden shadow-2xl border border-white/10">
        
        {/* Left Side: Features */}
        <div className="bg-[#E9ECE4] p-6 sm:p-7 w-full md:w-[45%] flex flex-col shrink-0">
          <div className="mb-6">
            <img src={logoImg} alt="TracePay" className="h-6 w-auto mb-6" />
            <h1 className="text-2xl font-extrabold text-[#171A3A] tracking-tight leading-tight">
              Your receipts.<br />
              <span className="text-[#164A3A]">Organized.</span>
            </h1>
            <p className="mt-2 text-[13px] font-medium text-[#171A3A]/70 leading-relaxed">
              Turn everyday receipts into structured purchase data — automatically.
            </p>
          </div>

          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-[#164A3A] shrink-0 mt-0.5" />
              <div>
                <h3 className="font-bold text-[#171A3A] text-sm">Capture receipts effortlessly</h3>
                <p className="text-[13px] font-medium text-[#171A3A]/60 mt-0.5 leading-snug">Upload physical receipts or digital invoices.</p>
              </div>
            </div>
            
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-[#164A3A] shrink-0 mt-0.5" />
              <div>
                <h3 className="font-bold text-[#171A3A] text-sm">Extract the details automatically</h3>
                <p className="text-[13px] font-medium text-[#171A3A]/60 mt-0.5 leading-snug">Merchant, dates, items, prices, tax, and totals.</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-[#164A3A] shrink-0 mt-0.5" />
              <div>
                <h3 className="font-bold text-[#171A3A] text-sm">Understand your spending</h3>
                <p className="text-[13px] font-medium text-[#171A3A]/60 mt-0.5 leading-snug">Keep every purchase organized and ready for insights.</p>
              </div>
            </div>
          </div>
        </div>

        {/* Right Side: Signup Form */}
        <div className="bg-[#F5F3EA] p-6 sm:p-7 w-full md:w-[55%] flex flex-col">
          
          <div className="mb-4 flex items-center h-6">
            <h2 className="text-xl font-bold text-[#171A3A]">Create your account</h2>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            
            <div className="flex gap-3">
              <div className="space-y-1.5 flex-1">
                <label className="block text-xs font-semibold text-[#171A3A]">First Name</label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="John"
                  className="w-full bg-white border border-[#171A3A]/10 rounded-xl px-4 py-2.5 text-sm text-[#171A3A] font-medium focus:outline-none focus:border-[#7A9B6D] focus:ring-1 focus:ring-[#7A9B6D] transition-colors shadow-sm placeholder:text-[#171A3A]/30"
                  required
                />
              </div>
              <div className="space-y-1.5 flex-1">
                <label className="block text-xs font-semibold text-[#171A3A]">Last Name</label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="Doe"
                  className="w-full bg-white border border-[#171A3A]/10 rounded-xl px-4 py-2.5 text-sm text-[#171A3A] font-medium focus:outline-none focus:border-[#7A9B6D] focus:ring-1 focus:ring-[#7A9B6D] transition-colors shadow-sm placeholder:text-[#171A3A]/30"
                  required
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-[#171A3A]">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                className="w-full bg-white border border-[#171A3A]/10 rounded-xl px-4 py-2.5 text-sm text-[#171A3A] font-medium focus:outline-none focus:border-[#7A9B6D] focus:ring-1 focus:ring-[#7A9B6D] transition-colors shadow-sm placeholder:text-[#171A3A]/30"
                required
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-[#171A3A]">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Create a password"
                  className="w-full bg-white border border-[#171A3A]/10 rounded-xl pl-4 pr-11 py-2.5 text-sm text-[#171A3A] font-medium focus:outline-none focus:border-[#7A9B6D] focus:ring-1 focus:ring-[#7A9B6D] transition-colors shadow-sm placeholder:text-[#171A3A]/30"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#171A3A]/40 hover:text-[#171A3A]/70 transition-colors p-1"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="w-full mt-2 bg-[#7A9B6D] hover:bg-[#7A9B6D]/90 text-white font-bold py-2.5 px-4 rounded-xl shadow-md hover:shadow-lg transition-all active:scale-[0.98] text-sm"
            >
              Create Account
            </button>
          </form>

          {/* Divider */}
          <div className="my-4 flex items-center gap-3">
            <div className="flex-1 h-px bg-[#171A3A]/10"></div>
            <span className="text-[10px] font-bold text-[#171A3A]/40 tracking-wider">OR</span>
            <div className="flex-1 h-px bg-[#171A3A]/10"></div>
          </div>

          {/* Google Signup */}
          <button
            type="button"
            className="w-full bg-white border border-[#171A3A]/10 hover:bg-slate-50 text-[#171A3A] font-semibold py-2 px-4 rounded-xl shadow-sm transition-all flex items-center justify-center gap-3 active:scale-[0.98] text-sm"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24">
              <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
            Continue with Google
          </button>

          {/* Login Link */}
          <p className="mt-5 text-center text-xs font-medium text-[#171A3A]/70">
            Already have an account?{" "}
            <Link to="/login" className="text-[#164A3A] hover:text-[#7A9B6D] font-bold transition-colors">
              Log In
            </Link>
          </p>

        </div>
      </div>
    </div>
  );
};
