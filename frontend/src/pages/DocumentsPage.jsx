import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { getDocuments, uploadDocument, deleteDocument, getStoredUser } from "../api";

export default function DocumentsPage({ user }) {
  const currentUser = user || getStoredUser();

  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [notification, setNotification] = useState(null);
  const fileInputRef = useRef(null);

  // Four-chip role selection state
  const [roles, setRoles] = useState({
    executive: true,
    hr: true,
    employee: true,
  });

  const isEveryone = roles.executive && roles.hr && roles.employee;
  const noneSelected = !roles.executive && !roles.hr && !roles.employee;

  const toggleEveryone = () => {
    if (isEveryone) {
      setRoles({ executive: false, hr: false, employee: false });
    } else {
      setRoles({ executive: true, hr: true, employee: true });
    }
  };

  const toggleRole = (roleKey) => {
    setRoles((prev) => ({ ...prev, [roleKey]: !prev[roleKey] }));
  };

  const getAllowedRolesString = () => {
    if (isEveryone) return "everyone";
    const active = [];
    if (roles.executive) active.push("executive");
    if (roles.hr) active.push("hr");
    if (roles.employee) active.push("employee");
    return active.join(",");
  };

  const fetchDocs = async () => {
    try {
      setLoading(true);
      const data = await getDocuments();
      setDocuments(data.documents || []);
    } catch (err) {
      showNotice(err.message || "Could not load cupboard files.", "vermilion");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, []);

  const showNotice = (text, type = "verdigris") => {
    setNotification({ text, type });
    setTimeout(() => {
      setNotification(null);
    }, 4000);
  };

  const handleFileUpload = async (file) => {
    if (!file) return;

    if (noneSelected) {
      showNotice("Select at least one role under 'Who can see this file?' before uploading.", "vermilion");
      return;
    }

    const ext = file.name.split(".").pop().toLowerCase();
    if (!["txt", "pdf"].includes(ext)) {
      showNotice("Only .pdf and .txt files can be kept in Almaari.", "vermilion");
      return;
    }

    const allowedRolesStr = getAllowedRolesString();

    try {
      setUploading(true);
      const res = await uploadDocument(file, allowedRolesStr);
      showNotice(`Filed away: ${file.name} (${res.chunk_count} chunks)`, "verdigris");
      fetchDocs();
    } catch (err) {
      showNotice(err.message || "Upload failed.", "vermilion");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (noneSelected) {
      showNotice("Select at least one role under 'Who can see this file?' before uploading.", "vermilion");
      return;
    }
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleDelete = async (docId, docName) => {
    try {
      await deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      showNotice(`Removed '${docName}' from the cupboard.`, "mustard");
    } catch (err) {
      showNotice(err.message || "Failed to remove document.", "vermilion");
    }
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  return (
    <div style={{ maxWidth: "1000px", margin: "0 auto", padding: "36px 20px" }}>
      {/* Header section */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          flexWrap: "wrap",
          gap: "16px",
          marginBottom: "28px",
          borderBottom: "1px dashed rgba(21, 26, 23, 0.25)",
          paddingBottom: "18px",
        }}
      >
        <div>
          <h1
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: "34px",
              lineHeight: 1.1,
            }}
          >
            The Filing Shelves
          </h1>
          <p
            style={{
              color: "var(--ink-muted)",
              fontSize: "14px",
              marginTop: "4px",
            }}
          >
            Access is filtered by role (<strong>{currentUser?.role || "employee"}</strong>). Documents are read, chunked, and indexed.
          </p>
        </div>

        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <span className="stamp-tag verdigris">
            {documents.length} {documents.length === 1 ? "file" : "files"} visible
          </span>
          <span className="stamp-tag mustard" style={{ textTransform: "uppercase" }}>
            role: {currentUser?.role || "employee"}
          </span>
        </div>
      </div>

      {/* Notification Toast */}
      <AnimatePresence>
        {notification && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className={`stamp-tag ${notification.type}`}
            style={{
              display: "block",
              marginBottom: "20px",
              padding: "10px 16px",
              fontSize: "14px",
            }}
          >
            {notification.text}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Upload Zone & Role Selector Box */}
      <div
        className="archive-card"
        style={{
          marginBottom: "36px",
          backgroundColor: "var(--paper-light)",
          padding: "24px",
        }}
      >
        {/* 'Who can see this file?' Selector */}
        <div style={{ marginBottom: "20px" }}>
          <div
            style={{
              fontSize: "13px",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "var(--ink)",
              marginBottom: "10px",
            }}
          >
            Who can see this file?
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", alignItems: "center" }}>
            {/* Everyone chip */}
            <motion.button
              type="button"
              whileTap={{ scale: 0.94 }}
              transition={{ type: "spring", stiffness: 450, damping: 22 }}
              onClick={toggleEveryone}
              className="btn btn-sm"
              style={{
                backgroundColor: isEveryone ? "var(--vermilion)" : "var(--paper-card)",
                color: isEveryone ? "#fff" : "var(--ink)",
                border: "1.5px solid var(--ink)",
                boxShadow: isEveryone ? "2px 2px 0px var(--ink)" : "var(--shadow-sm)",
              }}
            >
              Everyone
            </motion.button>

            {/* Executives chip */}
            <motion.button
              type="button"
              whileTap={{ scale: 0.94 }}
              transition={{ type: "spring", stiffness: 450, damping: 22 }}
              onClick={() => toggleRole("executive")}
              className="btn btn-sm"
              style={{
                backgroundColor: roles.executive ? "var(--vermilion)" : "var(--paper-card)",
                color: roles.executive ? "#fff" : "var(--ink)",
                border: "1.5px solid var(--ink)",
                boxShadow: roles.executive ? "2px 2px 0px var(--ink)" : "var(--shadow-sm)",
              }}
            >
              Executives
            </motion.button>

            {/* HR chip */}
            <motion.button
              type="button"
              whileTap={{ scale: 0.94 }}
              transition={{ type: "spring", stiffness: 450, damping: 22 }}
              onClick={() => toggleRole("hr")}
              className="btn btn-sm"
              style={{
                backgroundColor: roles.hr ? "var(--vermilion)" : "var(--paper-card)",
                color: roles.hr ? "#fff" : "var(--ink)",
                border: "1.5px solid var(--ink)",
                boxShadow: roles.hr ? "2px 2px 0px var(--ink)" : "var(--shadow-sm)",
              }}
            >
              HR
            </motion.button>

            {/* Employees chip */}
            <motion.button
              type="button"
              whileTap={{ scale: 0.94 }}
              transition={{ type: "spring", stiffness: 450, damping: 22 }}
              onClick={() => toggleRole("employee")}
              className="btn btn-sm"
              style={{
                backgroundColor: roles.employee ? "var(--vermilion)" : "var(--paper-card)",
                color: roles.employee ? "#fff" : "var(--ink)",
                border: "1.5px solid var(--ink)",
                boxShadow: roles.employee ? "2px 2px 0px var(--ink)" : "var(--shadow-sm)",
              }}
            >
              Employees
            </motion.button>

            {noneSelected && (
              <span style={{ fontSize: "12px", color: "var(--vermilion)", fontStyle: "italic", marginLeft: "6px" }}>
                * At least one role is required to upload
              </span>
            )}
          </div>
        </div>

        {/* Drag & Drop Upload Zone */}
        <motion.div
          onDragOver={(e) => {
            e.preventDefault();
            if (!noneSelected) setIsDragOver(true);
          }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
          onClick={() => {
            if (!noneSelected && !uploading) fileInputRef.current?.click();
          }}
          animate={{
            scale: isDragOver ? 1.02 : 1,
            backgroundColor: noneSelected
              ? "var(--paper-card)"
              : isDragOver
              ? "var(--verdigris-light)"
              : "var(--paper-card)",
            borderColor: noneSelected ? "rgba(21, 26, 23, 0.3)" : isDragOver ? "var(--verdigris)" : "var(--ink)",
            opacity: noneSelected ? 0.6 : 1,
          }}
          transition={{ type: "spring", stiffness: 300, damping: 25 }}
          style={{
            border: "2px dashed var(--ink)",
            padding: "32px 20px",
            textAlign: "center",
            cursor: noneSelected ? "not-allowed" : "pointer",
            boxShadow: isDragOver ? "4px 4px 0px var(--verdigris)" : "var(--shadow-sm)",
            position: "relative",
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt"
            disabled={noneSelected || uploading}
            style={{ display: "none" }}
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                handleFileUpload(e.target.files[0]);
              }
            }}
          />

          <div style={{ marginBottom: "10px" }}>
            <svg
              width="36"
              height="36"
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--ink)"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{ display: "inline-block" }}
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="12" y1="18" x2="12" y2="12" />
              <line x1="9" y1="15" x2="15" y2="15" />
            </svg>
          </div>

          <div
            style={{
              fontFamily: "var(--font-serif)",
              fontSize: "18px",
              fontWeight: 500,
              marginBottom: "4px",
            }}
          >
            {uploading
              ? "Reading and filing document into Almaari..."
              : noneSelected
              ? "Select who can see this file above to enable upload"
              : isDragOver
              ? "Release to deposit document into the cupboard"
              : "Drop a file here, or click to browse"}
          </div>
          <p style={{ color: "var(--ink-muted)", fontSize: "13px" }}>
            Accepts <strong className="mono">.pdf</strong> and <strong className="mono">.txt</strong> files (~500 words per chunk indexed)
          </p>
        </motion.div>
      </div>

      {/* Documents List */}
      <div>
        <h2
          style={{
            fontFamily: "var(--font-serif)",
            fontSize: "20px",
            marginBottom: "16px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <span>Filed Documents</span>
          <span style={{ fontSize: "12px", fontFamily: "var(--font-sans)", color: "var(--ink-muted)", fontWeight: 400 }}>
            (Visible to your role)
          </span>
        </h2>

        {loading ? (
          <div style={{ padding: "40px", textAlign: "center", color: "var(--ink-muted)", fontStyle: "italic" }}>
            Searching the shelves...
          </div>
        ) : documents.length === 0 ? (
          <div
            className="archive-card"
            style={{
              textAlign: "center",
              padding: "48px 20px",
              backgroundColor: "var(--paper-light)",
            }}
          >
            <p
              style={{
                fontFamily: "var(--font-serif)",
                fontSize: "18px",
                color: "var(--ink)",
                marginBottom: "6px",
              }}
            >
              No documents visible for role: {currentUser?.role || "employee"}.
            </p>
            <p style={{ color: "var(--ink-muted)", fontSize: "14px" }}>
              Upload a document above or sign in with another role to view restricted files.
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
            <AnimatePresence>
              {documents.map((doc) => (
                <DocumentCard
                  key={doc.id}
                  doc={doc}
                  currentUser={currentUser}
                  formatBytes={formatBytes}
                  onDelete={handleDelete}
                />
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Formats allowed_roles string into readable labels
 */
function formatAllowedRoles(allowedRolesStr) {
  if (!allowedRolesStr) return "Everyone";
  const parts = allowedRolesStr.split(",").map((s) => s.trim().toLowerCase());
  if (
    parts.includes("everyone") ||
    (parts.includes("executive") && parts.includes("hr") && parts.includes("employee"))
  ) {
    return "Everyone";
  }
  const labels = [];
  if (parts.includes("hr")) labels.push("HR");
  if (parts.includes("executive")) labels.push("Executives");
  if (parts.includes("employee")) labels.push("Employees");
  return labels.join(", ") || allowedRolesStr;
}

/**
 * DocumentCard with:
 * - Access role tags (e.g. "HR, Executives" or "Everyone")
 * - Uploader mono text (e.g. "by: hr")
 * - Swipe left to delete ONLY if permitted (uploader or executive)
 */
function DocumentCard({ doc, currentUser, formatBytes, onDelete }) {
  const canDelete = currentUser?.role === "executive" || doc.uploader === currentUser?.username;

  return (
    <div
      style={{
        position: "relative",
        overflow: "hidden",
        backgroundColor: canDelete ? "var(--vermilion-light)" : "var(--paper-card)",
        border: "var(--border-ink)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {/* Background Delete Action (Only rendered if user is permitted to delete) */}
      {canDelete && (
        <div
          style={{
            position: "absolute",
            top: 0,
            right: 0,
            bottom: 0,
            width: "120px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            paddingRight: "16px",
          }}
        >
          <button
            onClick={() => onDelete(doc.id, doc.original_name)}
            className="btn btn-accent btn-sm"
            style={{ width: "90px" }}
          >
            Delete
          </button>
        </div>
      )}

      {/* Foreground Card */}
      <motion.div
        layout
        initial={{ opacity: 0, y: 15, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, x: -100 }}
        transition={{ type: "spring", stiffness: 260, damping: 20 }}
        drag={canDelete ? "x" : false}
        dragConstraints={{ left: -110, right: 0 }}
        dragElastic={0.15}
        whileHover={{ rotate: -0.3, y: -2 }}
        style={{
          position: "relative",
          zIndex: 2,
          backgroundColor: "var(--paper-card)",
          padding: "16px 20px",
          cursor: canDelete ? "grab" : "default",
          userSelect: "none",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "12px",
          }}
        >
          {/* File details */}
          <div style={{ display: "flex", alignItems: "center", gap: "14px", minWidth: 0 }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                backgroundColor: "var(--paper-light)",
                border: "1px solid var(--ink)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--ink)" strokeWidth="1.8">
                <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
                <polyline points="13 2 13 9 20 9" />
              </svg>
            </div>

            <div style={{ minWidth: 0 }}>
              <div
                className="mono"
                style={{
                  fontWeight: 600,
                  fontSize: "15px",
                  color: "var(--ink)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
                title={doc.original_name}
              >
                {doc.original_name}
              </div>
              <div
                style={{
                  fontSize: "12px",
                  color: "var(--ink-muted)",
                  marginTop: "3px",
                  display: "flex",
                  gap: "10px",
                  flexWrap: "wrap",
                  alignItems: "center",
                }}
              >
                <span className="mono">by: {doc.uploader || "admin"}</span>
                <span>•</span>
                <span>Filed: {doc.uploaded_at || "Recent"}</span>
                <span>•</span>
                <span>{formatBytes(doc.file_size)}</span>
              </div>
            </div>
          </div>

          {/* Access Tags, Chunk Tag, and Delete button if authorized */}
          <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
            {/* Allowed Roles Tag */}
            <span
              className="stamp-tag mustard"
              title={`Permitted to: ${doc.allowed_roles || "everyone"}`}
            >
              access: {formatAllowedRoles(doc.allowed_roles)}
            </span>

            {/* Chunk Count */}
            <span className="stamp-tag verdigris">
              {doc.chunk_count} {doc.chunk_count === 1 ? "chunk" : "chunks"}
            </span>

            {/* Remove button if permitted */}
            {canDelete && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(doc.id, doc.original_name);
                }}
                className="btn btn-sm"
                title="Remove file from cupboard"
                style={{
                  backgroundColor: "transparent",
                  color: "var(--vermilion)",
                  borderColor: "rgba(21, 26, 23, 0.3)",
                }}
              >
                Remove
              </button>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
}
