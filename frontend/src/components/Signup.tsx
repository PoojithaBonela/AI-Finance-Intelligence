import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Eye, EyeOff, CheckCircle2 } from "lucide-react";
import logoImg from "../assets/TracePaylogo.png";
import { supabase } from "../lib/supabase";

export const Signup: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Password validation
  const hasMinLen = password.length >= 8;
  const hasUpper = /[A-Z]/.test(password);
  const hasLower = /[a-z]/.test(password);
  const hasNumber = /[0-9]/.test(password);
  const hasSpecial = /[^A-Za-z0-9]/.test(password);
  const isValidPassword = hasMinLen && hasUpper && hasLower && hasNumber && hasSpecial;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValidPassword) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const { data, error: signUpError } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            first_name: firstName,
            last_name: lastName
          }
        }
      });

      if (signUpError) throw signUpError;
      
      // If we got here, signup was successful
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || "An error occurred during sign up.");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignup = async () => {
    setError(null);
    try {
      const { error: oauthError } = await supabase.auth.signInWithOAuth({
        provider: 'google'
      });
      if (oauthError) throw oauthError;
    } catch (err: any) {
      setError(err.message || "Failed to initialize Google login.");
    }
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

        {/* Right Side: Form or Success */}
        <div className="bg-[#F5F3EA] p-6 sm:p-7 w-full md:w-[55%] flex flex-col justify-center">
          
          {success ? (
            <div className="animate-in fade-in zoom-in-95 duration-500 text-center">
              <div className="flex justify-center mb-4">
                <div className="w-12 h-12 bg-[#7A9B6D]/10 rounded-full flex items-center justify-center">
                  <CheckCircle2 className="w-6 h-6 text-[#7A9B6D]" strokeWidth={2.5} />
                </div>
              </div>
              <h2 className="text-xl font-bold text-[#171A3A] mb-2">Check your email</h2>
              <p className="text-[#171A3A]/70 text-[13px] font-medium leading-relaxed px-2 mb-6">
                We've sent a confirmation link to <span className="font-bold text-[#171A3A]">{email}</span>. Please verify your email to continue.
              </p>
              <Link to="/login" className="w-full inline-block bg-[#164A3A] hover:bg-[#164A3A]/90 text-white font-bold py-2.5 px-4 rounded-xl shadow-md hover:shadow-lg transition-all active:scale-[0.98] text-sm">
                Return to Log In
              </Link>
            </div>
          ) : (
            <>
              <div className="mb-4 flex items-center h-6">
                <h2 className="text-xl font-bold text-[#171A3A]">Create your account</h2>
              </div>

              {error && (
                <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-600 text-xs font-semibold">
                  {error}
                </div>
              )}

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
                  
                  {/* Live Password Validation Feedback */}
                  {password && (
                    <div className="mt-2 grid grid-cols-2 gap-y-1 text-[10px] font-semibold">
                      <div className={`flex items-center gap-1.5 ${hasMinLen ? 'text-[#7A9B6D]' : 'text-[#171A3A]/40'}`}>
                        <div className={`w-1.5 h-1.5 rounded-full ${hasMinLen ? 'bg-[#7A9B6D]' : 'bg-[#171A3A]/20'}`}></div>
                        8+ characters
                      </div>
                      <div className={`flex items-center gap-1.5 ${hasUpper ? 'text-[#7A9B6D]' : 'text-[#171A3A]/40'}`}>
                        <div className={`w-1.5 h-1.5 rounded-full ${hasUpper ? 'bg-[#7A9B6D]' : 'bg-[#171A3A]/20'}`}></div>
                        1 uppercase
                      </div>
                      <div className={`flex items-center gap-1.5 ${hasLower ? 'text-[#7A9B6D]' : 'text-[#171A3A]/40'}`}>
                        <div className={`w-1.5 h-1.5 rounded-full ${hasLower ? 'bg-[#7A9B6D]' : 'bg-[#171A3A]/20'}`}></div>
                        1 lowercase
                      </div>
                      <div className={`flex items-center gap-1.5 ${hasNumber ? 'text-[#7A9B6D]' : 'text-[#171A3A]/40'}`}>
                        <div className={`w-1.5 h-1.5 rounded-full ${hasNumber ? 'bg-[#7A9B6D]' : 'bg-[#171A3A]/20'}`}></div>
                        1 number
                      </div>
                      <div className={`flex items-center gap-1.5 col-span-2 ${hasSpecial ? 'text-[#7A9B6D]' : 'text-[#171A3A]/40'}`}>
                        <div className={`w-1.5 h-1.5 rounded-full ${hasSpecial ? 'bg-[#7A9B6D]' : 'bg-[#171A3A]/20'}`}></div>
                        1 special character
                      </div>
                    </div>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={loading || (password.length > 0 && !isValidPassword)}
                  className="w-full mt-2 bg-[#7A9B6D] hover:bg-[#7A9B6D]/90 disabled:opacity-50 disabled:hover:bg-[#7A9B6D] text-white font-bold py-2.5 px-4 rounded-xl shadow-md hover:shadow-lg transition-all active:scale-[0.98] text-sm flex justify-center items-center h-[40px]"
                >
                  {loading ? (
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  ) : (
                    "Create Account"
                  )}
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
                onClick={handleGoogleSignup}
                disabled={loading}
                className="w-full bg-white border border-[#171A3A]/10 hover:bg-slate-50 text-[#171A3A] font-semibold py-2 px-4 rounded-xl shadow-sm transition-all flex items-center justify-center gap-3 active:scale-[0.98] text-sm h-[40px] disabled:opacity-50"
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
            </>
          )}

        </div>
      </div>
    </div>
  );
};
