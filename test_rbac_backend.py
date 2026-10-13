import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
import db

client = TestClient(app)

print("=" * 65)
print(" Almaari RBAC Backend Verification Test (Stage 1)")
print("=" * 65)

# 1. Test Login & Role for all 3 users
print("\n[+] 1. Testing Login & Roles...")
r_exec = client.post("/login", json={"username": "executive", "password": "executive123"})
assert r_exec.status_code == 200, f"Executive login failed: {r_exec.text}"
exec_token = r_exec.json()["token"]
assert r_exec.json()["role"] == "executive"
print(f"  - executive logged in: role={r_exec.json()['role']}, token prefix={exec_token[:20]}...")

r_hr = client.post("/login", json={"username": "hr", "password": "hr123"})
assert r_hr.status_code == 200, f"HR login failed: {r_hr.text}"
hr_token = r_hr.json()["token"]
assert r_hr.json()["role"] == "hr"
print(f"  - hr logged in: role={r_hr.json()['role']}, token prefix={hr_token[:20]}...")

r_emp = client.post("/login", json={"username": "employee", "password": "employee123"})
assert r_emp.status_code == 200, f"Employee login failed: {r_emp.text}"
emp_token = r_emp.json()["token"]
assert r_emp.json()["role"] == "employee"
print(f"  - employee logged in: role={r_emp.json()['role']}, token prefix={emp_token[:20]}...")

# 2. Test 401 when no token is provided
print("\n[+] 2. Testing 401 Unauthorized protection on endpoints...")
r_no_auth = client.get("/documents")
assert r_no_auth.status_code == 401, f"Expected 401, got {r_no_auth.status_code}"
print("  - GET /documents without token returned 401 as expected.")

r_bad_auth = client.get("/documents", headers={"Authorization": "Bearer fake_token_12345"})
assert r_bad_auth.status_code == 401, f"Expected 401, got {r_bad_auth.status_code}"
print("  - GET /documents with invalid token returned 401 as expected.")

# 3. Test /upload with role validation
print("\n[+] 3. Testing Upload & Role Validation...")
# 3a. Reject empty allowed_roles
r_empty_roles = client.post(
    "/upload",
    files={"file": ("test_empty.txt", b"Some content", "text/plain")},
    data={"allowed_roles": ""},
    headers={"Authorization": f"Bearer {hr_token}"}
)
assert r_empty_roles.status_code == 400, f"Expected 400 for empty roles, got {r_empty_roles.status_code}"
print("  - Empty allowed_roles rejected with 400.")

# 3b. Reject invalid role
r_invalid_role = client.post(
    "/upload",
    files={"file": ("test_invalid.txt", b"Some content", "text/plain")},
    data={"allowed_roles": "hr,superadmin"},
    headers={"Authorization": f"Bearer {hr_token}"}
)
assert r_invalid_role.status_code == 400, f"Expected 400 for invalid role, got {r_invalid_role.status_code}"
print("  - Invalid role 'superadmin' rejected with 400.")

# 3c. Upload HR & Executive restricted file (Confidential Salary Scale)
hr_content = b"Confidential Compensation: HR Director salary is 250,000 PKR and executive bonuses are approved annually."
r_upload_hr = client.post(
    "/upload",
    files={"file": ("hr_salaries.txt", hr_content, "text/plain")},
    data={"allowed_roles": "hr,executive"},
    headers={"Authorization": f"Bearer {hr_token}"}
)
assert r_upload_hr.status_code == 200, f"HR upload failed: {r_upload_hr.text}"
hr_doc_id = r_upload_hr.json()["id"]
assert r_upload_hr.json()["uploader"] == "hr"
assert r_upload_hr.json()["allowed_roles"] == "hr,executive"
print(f"  - Uploaded 'hr_salaries.txt' with allowed_roles='hr,executive', uploader='hr' (ID: {hr_doc_id})")

# 3d. Upload Employee accessible file (Cafeteria Menu)
emp_content = b"Cafeteria Menu: Daily lunch features vegetable biryani on Mondays and chicken karahi on Thursdays."
r_upload_emp = client.post(
    "/upload",
    files={"file": ("cafeteria_menu.txt", emp_content, "text/plain")},
    data={"allowed_roles": "everyone"},
    headers={"Authorization": f"Bearer {emp_token}"}
)
assert r_upload_emp.status_code == 200, f"Employee upload failed: {r_upload_emp.text}"
emp_doc_id = r_upload_emp.json()["id"]
assert r_upload_emp.json()["uploader"] == "employee"
print(f"  - Uploaded 'cafeteria_menu.txt' with allowed_roles='everyone', uploader='employee' (ID: {emp_doc_id})")

# 4. Test /documents filtering by role
print("\n[+] 4. Testing Document Visibility by Role...")
# Employee should see cafeteria_menu.txt, but NOT hr_salaries.txt
emp_docs = client.get("/documents", headers={"Authorization": f"Bearer {emp_token}"}).json()["documents"]
emp_doc_names = [d["original_name"] for d in emp_docs]
assert "cafeteria_menu.txt" in emp_doc_names, "Employee should see cafeteria_menu.txt"
assert "hr_salaries.txt" not in emp_doc_names, "Employee MUST NOT see hr_salaries.txt"
print(f"  - Employee visible files: {emp_doc_names} (hr_salaries.txt correctly hidden)")

# HR should see both
hr_docs = client.get("/documents", headers={"Authorization": f"Bearer {hr_token}"}).json()["documents"]
hr_doc_names = [d["original_name"] for d in hr_docs]
assert "hr_salaries.txt" in hr_doc_names, "HR should see hr_salaries.txt"
assert "cafeteria_menu.txt" in hr_doc_names, "HR should see cafeteria_menu.txt"
print(f"  - HR visible files: {hr_doc_names} (both visible)")

# 5. Test Pre-Filtered /ask
print("\n[+] 5. Testing ChromaDB Pre-Filtered /ask...")
# Employee asks about salary -> MUST NOT retrieve hr_salaries.txt chunk
q_salary = "What is the HR Director salary?"
emp_ask = client.post("/ask", json={"question": q_salary}, headers={"Authorization": f"Bearer {emp_token}"}).json()
print(f"  - Employee asked about salary:")
print(f"    Answer: {emp_ask['answer']}")
print(f"    Sources: {emp_ask.get('sources', [])}")
assert "hr_salaries.txt" not in emp_ask.get("sources", []), "Employee MUST NOT receive hr_salaries.txt sources"
assert "250,000" not in emp_ask["answer"], "Employee MUST NOT receive confidential salary info"

# HR asks about salary -> ChromaDB retrieves hr_salaries.txt chunk
hr_ask = client.post("/ask", json={"question": q_salary}, headers={"Authorization": f"Bearer {hr_token}"}).json()
print(f"  - HR asked about salary:")
print(f"    Answer: {hr_ask['answer']}")
print(f"    Sources: {hr_ask.get('sources', [])}")
assert "hr_salaries.txt" in hr_ask.get("sources", []), "HR must receive hr_salaries.txt source"

# 6. Test DELETE /documents/{id} Permissions (403 Forbidden vs Allowed)
print("\n[+] 6. Testing DELETE Permissions...")
# Employee attempts to delete HR document -> MUST GET 403 Forbidden
r_del_forbidden = client.delete(f"/documents/{hr_doc_id}", headers={"Authorization": f"Bearer {emp_token}"})
assert r_del_forbidden.status_code == 403, f"Expected 403, got {r_del_forbidden.status_code}"
print("  - Employee attempting to delete HR document received 403 Forbidden as expected.")

# Executive attempts to delete HR document -> Allowed (executive privilege)
r_del_exec = client.delete(f"/documents/{hr_doc_id}", headers={"Authorization": f"Bearer {exec_token}"})
assert r_del_exec.status_code == 200, f"Executive delete failed: {r_del_exec.status_code}"
print("  - Executive deleting HR document succeeded (200 OK).")

# Clean up employee document by uploader
r_del_emp = client.delete(f"/documents/{emp_doc_id}", headers={"Authorization": f"Bearer {emp_token}"})
assert r_del_emp.status_code == 200, f"Uploader delete failed: {r_del_emp.status_code}"
print("  - Employee deleting own cafeteria document succeeded (200 OK).")

print("\n" + "=" * 65)
print(" ALL STAGE 1 BACKEND RBAC REQUIREMENTS VERIFIED SUCCESSFULLY!")
print("=" * 65)
