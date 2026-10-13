// Centralized API client for Almaari with RBAC Bearer Authentication
// Uses relative /api proxy with http://127.0.0.1:8000 fallback.

export function getStoredUser() {
  try {
    const data = localStorage.getItem("almaari_user");
    return data ? JSON.parse(data) : null;
  } catch {
    return null;
  }
}

export function getAuthToken() {
  const user = getStoredUser();
  return user?.token || "";
}

async function request(path, options = {}) {
  const token = getAuthToken();
  const headers = new Headers(options.headers || {});

  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const fetchOptions = {
    ...options,
    headers,
  };

  let res;
  try {
    res = await fetch(`/api${path}`, fetchOptions);
    if (res.status === 404) {
      // Direct localhost fallback if proxy not rewriting
      res = await fetch(`http://127.0.0.1:8000${path}`, fetchOptions);
    }
  } catch (err) {
    // Direct localhost fallback
    res = await fetch(`http://127.0.0.1:8000${path}`, fetchOptions);
  }

  // Handle 401 Unauthorized: clear session and redirect to /login
  if (res.status === 401) {
    localStorage.removeItem("almaari_user");
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
  }

  return res;
}

export async function loginUser(username, password) {
  // Login does not need Bearer token
  const res = await fetch(`http://127.0.0.1:8000/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  }).catch(() => {
    return fetch(`/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  });

  return res;
}

export async function getDocuments() {
  const res = await request("/documents");
  if (!res.ok) {
    throw new Error("Failed to retrieve documents from the cupboard.");
  }
  return res.json();
}

export async function uploadDocument(file, allowedRoles = "everyone") {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("allowed_roles", allowedRoles);

  const res = await request("/upload", {
    method: "POST",
    body: formData,
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Failed to file document away.");
  }
  return data;
}

export async function deleteDocument(docId) {
  const res = await request(`/documents/${docId}`, {
    method: "DELETE",
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Failed to remove document.");
  }
  return data;
}

export async function askQuestion(question) {
  const res = await request("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Error consulting the documents.");
  }
  return data;
}
