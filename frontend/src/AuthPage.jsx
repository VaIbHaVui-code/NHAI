import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { validateEmail, validatePassword, saveUserToDB, checkUserCredentials } from "./authValidation";
import "./AuthPage.css";

export default function AuthPage({ onLogin }) {
  const [isLogin, setIsLogin] = useState(false);
  const navigate = useNavigate();

  // Individual error states for each field
  const [errors, setErrors] = useState({
    email: "",
    password: "",
    confirmPassword: "",
    general: ""
  });

  const [form, setForm] = useState({
    email: "",
    password: "",
    confirmPassword: ""
  });

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
    // Clear specific error when user starts typing again
    setErrors({ ...errors, [e.target.name]: "", general: "" });
  };

  const handleSubmit = () => {
    const { email, password, confirmPassword } = form;
    let newErrors = { email: "", password: "", confirmPassword: "", general: "" };
    let hasError = false;

    // 1. Email Validation
    if (!validateEmail(email)) {
      newErrors.email = "Email must end with @gmail.com";
      hasError = true;
    }

    // 2. Password Validation
    if (!validatePassword(password)) {
      newErrors.password = "Password must be at least 8 characters";
      hasError = true;
    }

    if (!isLogin) {
      // 3. Confirm Password Validation (Signup only)
      if (password !== confirmPassword) {
        newErrors.confirmPassword = "Passwords do not match";
        hasError = true;
      }

      if (hasError) {
        setErrors(newErrors);
        return;
      }

      const result = saveUserToDB(email, password);
      if (result.success) {
        setErrors({ ...newErrors, general: "Registration Successful! Switching to Login..." });
        setTimeout(() => setIsLogin(true), 1500);
      } else {
        setErrors({ ...newErrors, email: result.message });
      }
    } else {
      // Login Logic
      if (hasError) {
        setErrors(newErrors);
        return;
      }

      const isValid = checkUserCredentials(email, password);
      if (isValid) {
        setErrors({ ...newErrors, general: "Login Successful! Redirecting..." });
        if (onLogin) onLogin(email);
        setTimeout(() => navigate("/HighwayDashboard"), 1000);
      } else {
        setErrors({ ...newErrors, general: "Invalid credentials. Please try again." });
      }
    }
  };

  return (
    <div className="auth-container">
      <div className="blurred-bg"></div>
      <div className="dark-overlay"></div>

      <div className="auth-box">
        <div className="auth-header">
          <h2>NHAI AI Monitoring</h2>
          <p>{isLogin ? "Authorized Access" : "Secure Registration"}</p>
        </div>

        <div className="input-group">
          {/* Email Field */}
          <div className="field-wrapper">
            <label>Official Email</label>
            <input
              type="email"
              name="email"
              placeholder="user@gmail.com"
              onChange={handleChange}
              value={form.email}
              className={errors.email ? "input-error" : ""}
            />
            {errors.email && <span className="error-msg">{errors.email}</span>}
          </div>

          {/* Password Field */}
          <div className="field-wrapper">
            <label>Secure Password</label>
            <input
              type="password"
              name="password"
              placeholder="Min. 8 characters"
              onChange={handleChange}
              value={form.password}
              className={errors.password ? "input-error" : ""}
            />
            {errors.password && <span className="error-msg">{errors.password}</span>}
          </div>

          {/* Confirm Password Field */}
          {!isLogin && (
            <div className="field-wrapper">
              <label>Confirm Password</label>
              <input
                type="password"
                name="confirmPassword"
                placeholder="Re-enter password"
                onChange={handleChange}
                value={form.confirmPassword}
                className={errors.confirmPassword ? "input-error" : ""}
              />
              {errors.confirmPassword && <span className="error-msg">{errors.confirmPassword}</span>}
            </div>
          )}

          {/* General success/error message (e.g., "User already exists" or "Login successful") */}
          {errors.general && (
            <div className={`auth-alert ${errors.general.includes("Successful") ? "success" : "error"}`}>
              {errors.general}
            </div>
          )}
        </div>

        <button onClick={handleSubmit} className="primary-btn">
          {isLogin ? "Login to Portal" : "Register Credentials"}
        </button>

        <p className="toggle-text">
          {isLogin ? "New to the system?" : "Already have access?"}
          <span onClick={() => setIsLogin(!isLogin)}>
            {isLogin ? " Sign Up" : " Login"}
          </span>
        </p>
      </div>
    </div>
  );
}
