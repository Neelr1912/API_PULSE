function parseErrorDetail(body) {
  if (!body) return "Request failed";
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) {
    return body.detail.map((e) => e.msg || JSON.stringify(e)).join(", ");
  }
  return "Request failed";
}

async function apiPost(path, payload) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseErrorDetail(data));
  }
  return data;
}

async function registerUser(username, email, password) {
  return apiPost("/auth/register", { username, email, password });
}

async function loginUser(email, password) {
  return apiPost("/auth/login", { email, password });
}

function setButtonLoading(button, loading) {
  if (!button) return;
  button.disabled = loading;
  button.classList.toggle("is-loading", loading);
  const spinner = button.querySelector(".spinner");
  if (spinner) spinner.hidden = !loading;
}

function showMessage(el, text, type) {
  if (!el) return;
  el.textContent = text;
  el.className = `form-message ${type}`;
  el.hidden = !text;
}

document.addEventListener("DOMContentLoaded", () => {
  if (localStorage.getItem("apipulse_token")) {
    window.location.href = "dashboard.html";
    return;
  }

  const tabRegister = document.getElementById("tab-register");
  const tabLogin = document.getElementById("tab-login");
  const panelRegister = document.getElementById("panel-register");
  const panelLogin = document.getElementById("panel-login");
  const registerForm = document.getElementById("register-form");
  const loginForm = document.getElementById("login-form");
  const registerMsg = document.getElementById("register-message");
  const loginMsg = document.getElementById("login-message");

  function switchTab(tab) {
    const isRegister = tab === "register";
    tabRegister.classList.toggle("active", isRegister);
    tabLogin.classList.toggle("active", !isRegister);
    panelRegister.hidden = !isRegister;
    panelLogin.hidden = isRegister;
    showMessage(registerMsg, "", "");
    showMessage(loginMsg, "", "");
  }

  tabRegister?.addEventListener("click", () => switchTab("register"));
  tabLogin?.addEventListener("click", () => switchTab("login"));

  registerForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = registerForm.querySelector('button[type="submit"]');
    showMessage(registerMsg, "", "");
    setButtonLoading(btn, true);
    try {
      const username = document.getElementById("reg-username").value.trim();
      const email = document.getElementById("reg-email").value.trim();
      const password = document.getElementById("reg-password").value;
      await registerUser(username, email, password);
      registerForm.reset();
      switchTab("login");
      showMessage(loginMsg, "Registered! Please log in.", "success");
    } catch (err) {
      showMessage(registerMsg, err.message, "error");
    } finally {
      setButtonLoading(btn, false);
    }
  });

  loginForm?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = loginForm.querySelector('button[type="submit"]');
    showMessage(loginMsg, "", "");
    setButtonLoading(btn, true);
    try {
      const email = document.getElementById("login-email").value.trim();
      const password = document.getElementById("login-password").value;
      const data = await loginUser(email, password);
      localStorage.setItem("apipulse_token", data.access_token);
      localStorage.setItem("apipulse_user", data.username);
      window.location.href = "dashboard.html";
    } catch (err) {
      showMessage(loginMsg, err.message, "error");
    } finally {
      setButtonLoading(btn, false);
    }
  });
});
