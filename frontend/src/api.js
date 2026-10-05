// Centralized API client for Almaari
// Uses relative /api which Vite proxies to http://127.0.0.1:8000.
// This allows the app to work seamlessly across localhost, LAN, and public tunnel URLs.

async function request(path, options = {}) {
  // Try proxy first (/api/...)
  try {
    const res = await fetch(`/api${path}`, options);
    if (res.status === 404) {
      // Direct localhost fallback if proxy not rewriting
      return await fetch(`http://127.0.0.1:8000${path}`, options);
    }
    return res;
  } catch (err) {
    // Direct localhost fallback
    return await fetch(`http://127.0.0.1:8000${path}`, options);
  }
}

export async function loginUser(username, password) {
  return request("/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
}

export async function getDocuments() {
  const res = await request("/documents");
  if (!res.ok) {
    throw new Error("Failed to retrieve documents from the cupboard.");
  }
  return res.json();
}

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

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
