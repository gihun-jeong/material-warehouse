from flask import Flask, request, redirect, url_for, jsonify, send_from_directory, render_template_string, flash, abort
import sqlite3
import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "demo-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "material_demo.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MATERIAL_MASTER = {
    "MAT-1001": {"po_no": "PO-2026-0001", "item_name": "세라믹 챔버 링", "spec": "Ø220 / High Temp"},
    "MAT-1002": {"po_no": "PO-2026-0002", "item_name": "쿼츠 라이너", "spec": "QZ-LN-ETCH-01"},
    "MAT-1003": {"po_no": "PO-2026-0003", "item_name": "오링 세트", "spec": "FKM / Vacuum Grade"},
    "MAT-1004": {"po_no": "PO-2026-0004", "item_name": "샤워헤드 Assy", "spec": "CVD-SH-A TYPE"},
    "MAT-1005": {"po_no": "PO-2026-0005", "item_name": "가스 노즐 블록", "spec": "AL6061 / Anodizing"},
}

PROCESS_MODULES = {
    "Etcher": ["ESC Module", "RF Module", "Gas Box", "Vacuum Chamber", "Transfer Module"],
    "CVD": ["Shower Head", "Heater Module", "Gas Line", "Exhaust Module"],
    "IMP": ["Source Module", "Beam Line", "Loadlock", "End Station"],
    "Diffusion": ["Tube Module", "Boat Loader", "Gas Cabinet"],
    "Clean": ["Spin Module", "Chemical Unit", "Dry Module"],
    "Litho": ["Stage Module", "Optics Module", "Loader"],
}

GRADE_OPTIONS = ["ALL", "A등급", "B등급"]
MATERIAL_TYPE_OPTIONS = ["ALL", "Running 자재", "PM자재", "유휴자재", "Open 자재", "사후관리자재"]
APPROVAL_OPTIONS = ["ALL", "POR", "SPLIT", "N/A"]
BUILDING_OPTIONS = ["A동", "B동"]
PROCESS_OPTIONS = ["Etcher", "CVD", "IMP", "Diffusion", "Clean", "Litho"]
GENERATION_OPTIONS = ["ALL", "알파", "베타", "JDP/JEP", "양산"]
INBOUND_TYPE_OPTIONS = ["ALL", "신규입고", "재입고"]
PURCHASE_TYPE_OPTIONS = ["ALL", "가공품", "상용품"]
USABILITY_OPTIONS = ["ALL", "세정완료", "사용가능", "사용불가"]
REQUEST_TYPE_OPTIONS = ["입고", "출고"]
REQUEST_STATUS_OPTIONS = ["대기", "승인", "반려"]

RETENTION_RULES = {
    "Running 자재": "1년",
    "PM자재": "1년",
    "유휴자재": "1년 6개월",
    "사후관리자재": "최대 5년",
    "Open 자재": "6개월",
}

DEFAULT_TEST_IMAGE_PATH = r"E:\test\sample.png"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def table_has_column(table_name, column_name):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    cols = [row[1] for row in cur.fetchall()]
    conn.close()
    return column_name in cols


def ensure_column(table_name, column_name, col_def):
    if not table_has_column(table_name, column_name):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {col_def}")
        conn.commit()
        conn.close()


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS material_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_type TEXT NOT NULL,
            material_code TEXT NOT NULL,
            po_no TEXT,
            item_name TEXT,
            item_spec TEXT,
            grade TEXT,
            material_category TEXT,
            approval_type TEXT,
            building_name TEXT,
            process_name TEXT,
            generation_name TEXT,
            module_name TEXT,
            quantity INTEGER NOT NULL,
            requester TEXT,
            purchase_requester TEXT,
            vendor_name TEXT,
            request_reason TEXT,
            inbound_type TEXT,
            purchase_type TEXT,
            usability_status TEXT,
            retention_period TEXT,
            project_name TEXT,
            actual_user TEXT,
            attachment_path TEXT,
            status TEXT DEFAULT '대기',
            admin_comment TEXT,
            created_at TEXT NOT NULL,
            approved_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS material_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            material_code TEXT NOT NULL,
            item_name TEXT,
            item_spec TEXT,
            grade TEXT,
            material_category TEXT,
            building_name TEXT,
            process_name TEXT,
            generation_name TEXT,
            module_name TEXT,
            quantity INTEGER NOT NULL,
            usability_status TEXT,
            retention_period TEXT,
            project_name TEXT,
            actual_user TEXT,
            attachment_path TEXT,
            storage_status TEXT DEFAULT '보관중',
            created_at TEXT NOT NULL,
            last_updated_at TEXT NOT NULL,
            FOREIGN KEY(request_id) REFERENCES material_requests(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS material_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            material_code TEXT NOT NULL,
            tx_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            tx_status TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(request_id) REFERENCES material_requests(id)
        )
        """
    )
    conn.commit()
    conn.close()

    ensure_column("material_inventory", "attachment_path", "TEXT")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM material_requests")
    cnt = cur.fetchone()["cnt"]

    if cnt == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        demo_requests = [
            (
                "입고", "MAT-1001", "PO-2026-0001", "세라믹 챔버 링", "Ø220 / High Temp",
                "A등급", "Running 자재", "POR", "A동", "Etcher", "양산", "ESC Module",
                5, "김테스트", "박구매", "ABC Tech", "예비품 보관", "신규입고", "가공품",
                "사용가능", "1년", "Project Atlas", "이실사용", DEFAULT_TEST_IMAGE_PATH, "승인", "", now, now
            ),
            (
                "입고", "MAT-1002", "PO-2026-0002", "쿼츠 라이너", "QZ-LN-ETCH-01",
                "B등급", "유휴자재", "SPLIT", "B동", "CVD", "베타", "Shower Head",
                2, "정사용", "오구매", "Quartz Co", "라인 이관 보관", "재입고", "상용품",
                "세정완료", "1년 6개월", "Project Nova", "한실사용", DEFAULT_TEST_IMAGE_PATH, "대기", "", now, None
            ),
            (
                "출고", "MAT-1001", "PO-2026-0001", "세라믹 챔버 링", "Ø220 / High Temp",
                "A등급", "Running 자재", "POR", "A동", "Etcher", "양산", "ESC Module",
                1, "최출고", "박구매", "ABC Tech", "교체 작업 출고", "재입고", "가공품",
                "사용가능", "1년", "Project Atlas", "이실사용", DEFAULT_TEST_IMAGE_PATH, "대기", "", now, None
            ),
        ]
        cur.executemany(
            """
            INSERT INTO material_requests (
                request_type, material_code, po_no, item_name, item_spec,
                grade, material_category, approval_type, building_name, process_name,
                generation_name, module_name, quantity, requester, purchase_requester,
                vendor_name, request_reason, inbound_type, purchase_type, usability_status,
                retention_period, project_name, actual_user, attachment_path, status,
                admin_comment, created_at, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            demo_requests,
        )
        conn.commit()

        cur.execute("SELECT * FROM material_requests WHERE status='승인' AND request_type='입고'")
        for row in cur.fetchall():
            cur.execute(
                """
                INSERT INTO material_inventory (
                    request_id, material_code, item_name, item_spec, grade, material_category,
                    building_name, process_name, generation_name, module_name, quantity,
                    usability_status, retention_period, project_name, actual_user,
                    attachment_path, storage_status, created_at, last_updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"], row["material_code"], row["item_name"], row["item_spec"], row["grade"], row["material_category"],
                    row["building_name"], row["process_name"], row["generation_name"], row["module_name"], row["quantity"],
                    row["usability_status"], row["retention_period"], row["project_name"], row["actual_user"],
                    row["attachment_path"], "보관중", row["created_at"], row["approved_at"] or row["created_at"]
                )
            )
            cur.execute(
                """
                INSERT INTO material_transactions (request_id, material_code, tx_type, quantity, tx_status, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (row["id"], row["material_code"], "입고", row["quantity"], "완료", "초기 샘플 데이터", row["created_at"])
            )
        conn.commit()

    conn.close()


def fetch_all_dicts(query, params=None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, params or [])
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def execute_write(query, params=None):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(query, params or [])
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def get_request_by_id(req_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM material_requests WHERE id=?", (req_id,))
    row = cur.fetchone()
    conn.close()
    return row


def row_to_dict(row):
    return dict(row) if row else None


def build_image_view_url(image_path):
    if not image_path:
        return None
    return url_for("file_preview") + f"?path={image_path}"


def upsert_inventory_from_request(request_row):
    conn = get_db_connection()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if request_row["request_type"] == "입고" and request_row["status"] == "승인":
        cur.execute("SELECT id FROM material_inventory WHERE request_id=?", (request_row["id"],))
        existed = cur.fetchone()
        if existed is None:
            cur.execute(
                """
                INSERT INTO material_inventory (
                    request_id, material_code, item_name, item_spec, grade, material_category,
                    building_name, process_name, generation_name, module_name, quantity,
                    usability_status, retention_period, project_name, actual_user,
                    attachment_path, storage_status, created_at, last_updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_row["id"], request_row["material_code"], request_row["item_name"], request_row["item_spec"], request_row["grade"], request_row["material_category"],
                    request_row["building_name"], request_row["process_name"], request_row["generation_name"], request_row["module_name"], request_row["quantity"],
                    request_row["usability_status"], request_row["retention_period"], request_row["project_name"], request_row["actual_user"], request_row["attachment_path"],
                    "보관중", now, now
                )
            )
        else:
            cur.execute(
                """
                UPDATE material_inventory
                SET material_code=?, item_name=?, item_spec=?, grade=?, material_category=?, building_name=?,
                    process_name=?, generation_name=?, module_name=?, quantity=?, usability_status=?,
                    retention_period=?, project_name=?, actual_user=?, attachment_path=?, last_updated_at=?
                WHERE request_id=?
                """,
                (
                    request_row["material_code"], request_row["item_name"], request_row["item_spec"], request_row["grade"], request_row["material_category"], request_row["building_name"],
                    request_row["process_name"], request_row["generation_name"], request_row["module_name"], request_row["quantity"], request_row["usability_status"],
                    request_row["retention_period"], request_row["project_name"], request_row["actual_user"], request_row["attachment_path"], now, request_row["id"]
                )
            )
        cur.execute(
            "INSERT INTO material_transactions (request_id, material_code, tx_type, quantity, tx_status, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (request_row["id"], request_row["material_code"], "입고", request_row["quantity"], "완료", "관리자 승인 처리", now)
        )

    elif request_row["request_type"] == "출고" and request_row["status"] == "승인":
        cur.execute("SELECT * FROM material_inventory WHERE material_code=? ORDER BY id ASC LIMIT 1", (request_row["material_code"],))
        inv = cur.fetchone()
        if inv:
            new_qty = max((inv["quantity"] or 0) - (request_row["quantity"] or 0), 0)
            storage_status = "보관중" if new_qty > 0 else "출고완료"
            cur.execute("UPDATE material_inventory SET quantity=?, storage_status=?, last_updated_at=? WHERE id=?", (new_qty, storage_status, now, inv["id"]))
            cur.execute(
                "INSERT INTO material_transactions (request_id, material_code, tx_type, quantity, tx_status, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (request_row["id"], request_row["material_code"], "출고", request_row["quantity"], "완료", "관리자 승인 처리", now)
            )

    conn.commit()
    conn.close()


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/file-preview")
def file_preview():
    file_path = request.args.get("path", "").strip()
    if not file_path or not os.path.exists(file_path) or not os.path.isfile(file_path):
        abort(404)
    return send_from_directory(os.path.dirname(file_path), os.path.basename(file_path))


@app.route("/api/material-lookup")
def api_material_lookup():
    material_code = request.args.get("material_code", "").strip()
    data = MATERIAL_MASTER.get(material_code)
    if data:
        return jsonify({"success": True, "data": data})
    return jsonify({"success": False, "message": "자재코드를 찾을 수 없습니다."}), 404


@app.route("/api/modules")
def api_modules():
    process_name = request.args.get("process_name", "")
    return jsonify({"success": True, "data": PROCESS_MODULES.get(process_name, [])})


@app.route("/api/retention")
def api_retention():
    material_category = request.args.get("material_category", "")
    return jsonify({"success": True, "data": RETENTION_RULES.get(material_category, "직접선택")})


@app.route("/api/request/<int:req_id>")
def api_request_detail(req_id):
    row = get_request_by_id(req_id)
    if not row:
        return jsonify({"success": False, "message": "데이터를 찾을 수 없습니다."}), 404
    data = row_to_dict(row)
    data["image_view_url"] = build_image_view_url(data.get("attachment_path")) if data.get("attachment_path") else None
    data["detail_type"] = "request"
    return jsonify({"success": True, "data": data})


@app.route("/api/request/<int:req_id>/update", methods=["POST"])
def api_request_update(req_id):
    existing = get_request_by_id(req_id)
    if not existing:
        return jsonify({"success": False, "message": "데이터를 찾을 수 없습니다."}), 404

    payload = request.get_json(silent=True) or {}
    quantity = int(payload.get("quantity") or 0)
    if quantity <= 0:
        return jsonify({"success": False, "message": "수량은 1 이상이어야 합니다."}), 400

    material_code = (payload.get("material_code") or "").strip()
    lookup = MATERIAL_MASTER.get(material_code, {})
    attachment_path = (payload.get("attachment_path") or existing["attachment_path"] or DEFAULT_TEST_IMAGE_PATH).strip()
    po_no = (payload.get("po_no") or lookup.get("po_no") or "").strip()
    item_name = (payload.get("item_name") or lookup.get("item_name") or "").strip()
    item_spec = (payload.get("item_spec") or lookup.get("spec") or "").strip()

    execute_write(
        """
        UPDATE material_requests
        SET request_type=?, material_code=?, po_no=?, item_name=?, item_spec=?, grade=?, material_category=?, approval_type=?, building_name=?,
            process_name=?, generation_name=?, module_name=?, quantity=?, requester=?, purchase_requester=?, vendor_name=?, request_reason=?,
            inbound_type=?, purchase_type=?, usability_status=?, retention_period=?, project_name=?, actual_user=?, attachment_path=?, admin_comment=?
        WHERE id=?
        """,
        (
            payload.get("request_type"), material_code, po_no, item_name, item_spec, payload.get("grade"), payload.get("material_category"), payload.get("approval_type"), payload.get("building_name"),
            payload.get("process_name"), payload.get("generation_name"), payload.get("module_name"), quantity, payload.get("requester"), payload.get("purchase_requester"), payload.get("vendor_name"),
            payload.get("request_reason"), payload.get("inbound_type"), payload.get("purchase_type"), payload.get("usability_status"), payload.get("retention_period"), payload.get("project_name"),
            payload.get("actual_user"), attachment_path, payload.get("admin_comment", existing["admin_comment"]), req_id
        )
    )

    updated = get_request_by_id(req_id)
    if updated and updated["status"] == "승인":
        upsert_inventory_from_request(updated)

    data = row_to_dict(updated)
    data["image_view_url"] = build_image_view_url(data.get("attachment_path")) if data.get("attachment_path") else None
    data["detail_type"] = "request"
    return jsonify({"success": True, "message": "상세내역이 수정되었습니다.", "data": data})


@app.route("/api/inventory/<int:inv_id>")
def api_inventory_detail(inv_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM material_inventory WHERE id=?", (inv_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"success": False, "message": "데이터를 찾을 수 없습니다."}), 404
    data = row_to_dict(row)
    data["image_view_url"] = build_image_view_url(data.get("attachment_path")) if data.get("attachment_path") else None
    data["detail_type"] = "inventory"
    return jsonify({"success": True, "data": data})


@app.route("/api/transaction/<int:tx_id>")
def api_transaction_detail(tx_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT t.*, r.po_no, r.item_name, r.item_spec, r.grade, r.material_category, r.building_name, r.process_name,
               r.generation_name, r.module_name, r.requester, r.purchase_requester, r.vendor_name, r.request_reason,
               r.inbound_type, r.purchase_type, r.usability_status, r.retention_period, r.project_name,
               r.actual_user, r.attachment_path, r.status AS request_status, r.admin_comment
        FROM material_transactions t
        LEFT JOIN material_requests r ON t.request_id = r.id
        WHERE t.id=?
        """,
        (tx_id,)
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"success": False, "message": "데이터를 찾을 수 없습니다."}), 404
    data = row_to_dict(row)
    data["image_view_url"] = build_image_view_url(data.get("attachment_path")) if data.get("attachment_path") else None
    data["detail_type"] = "transaction"
    return jsonify({"success": True, "data": data})


@app.route("/materials", methods=["GET", "POST"])
def materials_page():
    if request.method == "POST":
        request_type = request.form.get("request_type", "입고")
        material_code = request.form.get("material_code", "").strip()
        lookup = MATERIAL_MASTER.get(material_code, {})

        po_no = request.form.get("po_no") or lookup.get("po_no", "")
        item_name = request.form.get("item_name") or lookup.get("item_name", "")
        item_spec = request.form.get("item_spec") or lookup.get("spec", "")

        attachment_path = DEFAULT_TEST_IMAGE_PATH
        file = request.files.get("attachment")
        if file and file.filename:
            ext = os.path.splitext(file.filename)[1]
            unique_name = secure_filename(f"{uuid.uuid4().hex}{ext}")
            save_path = os.path.join(UPLOAD_DIR, unique_name)
            file.save(save_path)
            attachment_path = save_path

        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        execute_write(
            """
            INSERT INTO material_requests (
                request_type, material_code, po_no, item_name, item_spec,
                grade, material_category, approval_type, building_name, process_name,
                generation_name, module_name, quantity, requester, purchase_requester,
                vendor_name, request_reason, inbound_type, purchase_type, usability_status,
                retention_period, project_name, actual_user, attachment_path, status,
                admin_comment, created_at, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '대기', '', ?, NULL)
            """,
            (
                request_type, material_code, po_no, item_name, item_spec,
                request.form.get("grade"), request.form.get("material_category"), request.form.get("approval_type"), request.form.get("building_name"), request.form.get("process_name"),
                request.form.get("generation_name"), request.form.get("module_name"), int(request.form.get("quantity") or 0), request.form.get("requester"), request.form.get("purchase_requester"),
                request.form.get("vendor_name"), request.form.get("request_reason"), request.form.get("inbound_type"), request.form.get("purchase_type"), request.form.get("usability_status"),
                request.form.get("retention_period"), request.form.get("project_name"), request.form.get("actual_user"), attachment_path, created_at,
            )
        )
        flash("입/출고 의뢰가 등록되었습니다.")
        return redirect(url_for("materials_page"))

    requests_data = fetch_all_dicts("SELECT * FROM material_requests ORDER BY id DESC")
    inventory_data = fetch_all_dicts("SELECT * FROM material_inventory ORDER BY id DESC")
    tx_data = fetch_all_dicts("SELECT * FROM material_transactions ORDER BY id DESC")

    return render_template_string(
        TEMPLATE,
        requests_data=requests_data,
        inventory_data=inventory_data,
        tx_data=tx_data,
        grade_options=GRADE_OPTIONS,
        material_type_options=MATERIAL_TYPE_OPTIONS,
        approval_options=APPROVAL_OPTIONS,
        building_options=BUILDING_OPTIONS,
        process_options=PROCESS_OPTIONS,
        generation_options=GENERATION_OPTIONS,
        inbound_type_options=INBOUND_TYPE_OPTIONS,
        purchase_type_options=PURCHASE_TYPE_OPTIONS,
        usability_options=USABILITY_OPTIONS,
        request_type_options=REQUEST_TYPE_OPTIONS,
    )


@app.route("/materials/admin/approve/<int:req_id>", methods=["POST"])
def approve_request(req_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execute_write(
        "UPDATE material_requests SET status='승인', approved_at=?, admin_comment=? WHERE id=?",
        (now, request.form.get("admin_comment", ""), req_id),
    )
    row = get_request_by_id(req_id)
    if row:
        upsert_inventory_from_request(row)
    flash(f"요청 #{req_id} 가 승인되었습니다.")
    return redirect(url_for("materials_page") + "#request-status")


@app.route("/materials/admin/reject/<int:req_id>", methods=["POST"])
def reject_request(req_id):
    execute_write(
        "UPDATE material_requests SET status='반려', admin_comment=? WHERE id=?",
        (request.form.get("admin_comment", ""), req_id),
    )
    flash(f"요청 #{req_id} 가 반려되었습니다.")
    return redirect(url_for("materials_page") + "#request-status")


TEMPLATE = r'''
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>자재 관리 페이지 데모</title>
<style>
:root {
    --bg:#f5f7fb; --card:#fff; --text:#1f2937; --muted:#6b7280; --line:#e5e7eb;
    --primary:#111827; --accent:#2563eb; --green:#059669; --red:#dc2626;
    --shadow:0 10px 30px rgba(17,24,39,.08); --radius:18px;
}
*{box-sizing:border-box}
body{margin:0;background:linear-gradient(180deg,#eff4ff 0%,var(--bg) 30%,#f9fafb 100%);font-family:"Segoe UI","Apple SD Gothic Neo",sans-serif;color:var(--text)}
.page{width:min(1600px,calc(100% - 32px));margin:24px auto 60px}
.hero{background:linear-gradient(135deg,#0f172a 0%,#1d4ed8 100%);color:#fff;border-radius:28px;padding:28px;box-shadow:var(--shadow);display:grid;grid-template-columns:1.6fr 1fr;gap:20px;align-items:center}
.hero h1{margin:0 0 10px;font-size:32px}.hero p{margin:0;line-height:1.7;opacity:.95}
.hero-stats,.grid-3{display:grid;gap:12px}.hero-stats{grid-template-columns:repeat(3,1fr)}.grid-3{margin-top:20px;grid-template-columns:repeat(3,1fr);gap:16px}
.mini-stat,.card{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow)}
.mini-stat{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.14);padding:16px}.mini-stat .label{font-size:12px;opacity:.8}.mini-stat .value{font-size:24px;font-weight:700;margin-top:6px}
.card{border:1px solid rgba(229,231,235,.8)}.summary-card{padding:18px 20px}.summary-card .label{color:var(--muted);font-size:13px}.summary-card .value{font-size:28px;font-weight:700;margin-top:10px}
.section{margin-top:22px;padding:22px}.section-header{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:18px;flex-wrap:wrap}.section-header h2{margin:0;font-size:22px}.section-header p{margin:6px 0 0;color:var(--muted)}
.tabs{display:flex;gap:10px;flex-wrap:wrap}.tab-btn{border:1px solid var(--line);background:#fff;border-radius:999px;padding:10px 16px;font-weight:600;cursor:pointer}.tab-btn.active{background:var(--primary);color:#fff;border-color:var(--primary)}
.tab-panel{display:none}.tab-panel.active{display:block}
.form-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.field{display:flex;flex-direction:column;gap:8px}.field label{font-size:13px;font-weight:700;color:#374151}.field input,.field select,.field textarea{width:100%;border:1px solid var(--line);border-radius:12px;padding:12px 14px;font-size:14px;background:#fff}.field textarea{min-height:92px;resize:vertical}.field.full{grid-column:1/-1}.field.span-2{grid-column:span 2}.inline-row{display:flex;gap:8px;align-items:end}
.btn{border:none;border-radius:12px;padding:12px 16px;font-weight:700;cursor:pointer;transition:.15s ease}.btn:hover{transform:translateY(-1px)}.btn-primary{background:var(--accent);color:#fff}.btn-dark{background:var(--primary);color:#fff}.btn-green{background:var(--green);color:#fff}.btn-red{background:var(--red);color:#fff}.btn-outline{background:#fff;color:var(--primary);border:1px solid var(--line)}.btn-small{padding:8px 12px;font-size:12px;border-radius:10px}
.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:16px}table{width:100%;border-collapse:collapse;min-width:1280px;background:#fff}thead th{position:sticky;top:0;background:#f8fafc;font-size:13px;color:#334155;z-index:1;user-select:none}th,td{border-bottom:1px solid var(--line);padding:12px 10px;text-align:left;vertical-align:top;font-size:13px}tbody tr:hover{background:#f8fbff}tbody tr.clickable-row{cursor:pointer}
.badge{display:inline-flex;align-items:center;padding:6px 10px;border-radius:999px;font-size:12px;font-weight:700}.badge.waiting{background:#fff7ed;color:#c2410c}.badge.approved{background:#ecfdf5;color:#047857}.badge.rejected{background:#fef2f2;color:#b91c1c}.badge.storage{background:#eff6ff;color:#1d4ed8}
.hint{font-size:12px;color:var(--muted)}.flash{margin:18px 0;padding:14px 16px;border-radius:14px;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;font-weight:600}
.admin-box{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.admin-box form{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.admin-box input{border:1px solid var(--line);border-radius:10px;padding:8px 10px;min-width:180px}
.toolbar{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:14px}.filter-row{display:flex;gap:10px;flex-wrap:wrap}.filter-row input,.filter-row select{border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:#fff}
.sortable{cursor:pointer;white-space:nowrap}.sortable::after{content:' ⇅';color:#94a3b8;font-weight:400}.sortable.asc::after{content:' ↑';color:#2563eb}.sortable.desc::after{content:' ↓';color:#2563eb}.sortable.none::after{content:' ⇅';color:#94a3b8}
.pagination{display:flex;justify-content:flex-end;gap:8px;margin-top:12px;flex-wrap:wrap}.page-btn{min-width:34px;height:34px;border:1px solid var(--line);background:#fff;border-radius:10px;cursor:pointer;font-weight:700}.page-btn.active{background:var(--primary);color:#fff;border-color:var(--primary)}
.modal-overlay{position:fixed;inset:0;background:rgba(15,23,42,.55);display:none;align-items:center;justify-content:center;z-index:1000;padding:20px}.modal-overlay.show{display:flex}.modal{width:min(1200px,100%);max-height:90vh;overflow:auto;background:#fff;border-radius:22px;box-shadow:0 20px 60px rgba(0,0,0,.25);padding:22px}.modal-header{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:16px;position:sticky;top:0;background:#fff;padding-bottom:12px;z-index:2}.modal-header h3{margin:0}.close-btn{background:#f3f4f6;border:none;width:40px;height:40px;border-radius:12px;cursor:pointer;font-size:18px}.detail-layout{display:grid;grid-template-columns:1.4fr 1fr;gap:20px}.detail-card{border:1px solid var(--line);border-radius:18px;padding:18px}.detail-image{width:100%;aspect-ratio:4/3;object-fit:contain;border:1px solid var(--line);border-radius:16px;background:#f8fafc}.detail-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.detail-grid .field.full{grid-column:1/-1}.detail-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:16px;flex-wrap:wrap}.empty-note{color:var(--muted);padding:12px 0}
@media (max-width:1280px){.form-grid{grid-template-columns:repeat(3,1fr)}.hero,.detail-layout{grid-template-columns:1fr}}
@media (max-width:900px){.grid-3,.hero-stats{grid-template-columns:1fr}.form-grid,.detail-grid{grid-template-columns:repeat(2,1fr)}}
@media (max-width:640px){.page{width:min(100% - 20px,100%)}.form-grid,.detail-grid{grid-template-columns:1fr}.field.span-2{grid-column:span 1}}
</style>
</head>
<body>
<div class="page">
    <div class="hero card">
        <div>
            <h1>자재 보관/입출고 관리 데모</h1>
            <p>입/출고 의뢰, 신청 현황, 보관 자재 현황, 입출고 이력을 한 화면에서 테스트할 수 있는 버전입니다.</p>
        </div>
        <div class="hero-stats">
            <div class="mini-stat"><div class="label">전체 의뢰 건수</div><div class="value">{{ requests_data|length }}</div></div>
            <div class="mini-stat"><div class="label">보관 자재 건수</div><div class="value">{{ inventory_data|length }}</div></div>
            <div class="mini-stat"><div class="label">입출고 이력 건수</div><div class="value">{{ tx_data|length }}</div></div>
        </div>
    </div>

    <div class="grid-3">
        <div class="card summary-card"><div class="label">대기중 요청</div><div class="value">{{ requests_data | selectattr('status', 'equalto', '대기') | list | length }}</div></div>
        <div class="card summary-card"><div class="label">승인 완료</div><div class="value">{{ requests_data | selectattr('status', 'equalto', '승인') | list | length }}</div></div>
        <div class="card summary-card"><div class="label">반려 건수</div><div class="value">{{ requests_data | selectattr('status', 'equalto', '반려') | list | length }}</div></div>
    </div>

    {% with messages = get_flashed_messages() %}
      {% if messages %}
        {% for msg in messages %}
          <div class="flash">{{ msg }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}

    <div class="card section">
        <div class="section-header">
            <div>
                <h2>업무 화면</h2>
                <p>탭 구조로 화면 수를 줄이고 작업 흐름을 단순화했습니다.</p>
            </div>
            <div class="tabs">
                <button class="tab-btn active" data-tab="request-form">입/출고 의뢰 등록</button>
                <button class="tab-btn" data-tab="request-status">입출고 신청 현황</button>
                <button class="tab-btn" data-tab="inventory-status">보관 자재 현황</button>
                <button class="tab-btn" data-tab="transaction-status">입출고 이력</button>
            </div>
        </div>

        <div class="tab-panel active" id="request-form">
            <form method="POST" enctype="multipart/form-data" id="requestForm">
                <div class="form-grid">
                    <div class="field">
                        <label>입/출고 구분</label>
                        <select name="request_type" id="request_type">{% for opt in request_type_options %}<option value="{{ opt }}">{{ opt }}</option>{% endfor %}</select>
                    </div>
                    <div class="field span-2">
                        <label>자재코드</label>
                        <div class="inline-row">
                            <input type="text" id="material_code" name="material_code" placeholder="예: MAT-1001" required>
                            <button type="button" class="btn btn-dark" id="lookupBtn">조회</button>
                        </div>
                        <div class="hint">자재코드 입력 후 Enter를 누르면 의뢰 등록이 아니라 조회가 실행됩니다.</div>
                    </div>
                    <div class="field"><label>발주번호</label><input type="text" name="po_no" id="po_no" readonly></div>
                    <div class="field span-2"><label>품명</label><input type="text" name="item_name" id="item_name" readonly></div>
                    <div class="field span-2"><label>규격</label><input type="text" name="item_spec" id="item_spec" readonly></div>
                    <div class="field"><label>등급</label><select name="grade">{% for opt in grade_options %}<option value="{{ opt }}">{{ opt }}</option>{% endfor %}</select></div>
                    <div class="field"><label>자재구분</label><select name="material_category" id="material_category">{% for opt in material_type_options %}<option value="{{ opt }}">{{ opt }}</option>{% endfor %}</select></div>
                    <div class="field"><label>승인여부</label><select name="approval_type">{% for opt in approval_options %}<option value="{{ opt }}">{{ opt }}</option>{% endfor %}</select></div>
                    <div class="field"><label>건물명</label><select name="building_name">{% for opt in building_options %}<option value="{{ opt }}">{{ opt }}</option>{% endfor %}</select></div>
                    <div class="field"><label>설비공정</label><select name="process_name" id="process_name"><option value="">선택</option>{% for opt in process_options %}<option value="{{ opt }}">{{ opt }}</option>{% endfor %}</select></div>
                    <div class="field"><label>세대/개발호기</label><select name="generation_name">{% for opt in generation_options %}<option value="{{ opt }}">{{ opt }}</option>{% endfor %}</select></div>
                    <div class="field"><label>모듈명</label><select name="module_name" id="module_name"><option value="">설비공정 선택</option></select></div>
                    <div class="field"><label>수량</label><input type="number" name="quantity" min="1" value="1" required></div>
                    <div class="field"><label>요청자</label><input type="text" name="requester"></div>
                    <div class="field"><label>구매의뢰자</label><input type="text" name="purchase_requester"></div>
                    <div class="field"><label>업체명</label><input type="text" name="vendor_name"></div>
                    <div class="field"><label>입고유형</label><select name="inbound_type">{% for opt in inbound_type_options %}<option value="{{ opt }}">{{ opt }}</option>{% endfor %}</select></div>
                    <div class="field"><label>구매유형</label><select name="purchase_type">{% for opt in purchase_type_options %}<option value="{{ opt }}">{{ opt }}</option>{% endfor %}</select></div>
                    <div class="field"><label>사용가능여부</label><select name="usability_status">{% for opt in usability_options %}<option value="{{ opt }}">{{ opt }}</option>{% endfor %}</select></div>
                    <div class="field"><label>보관기간</label><input type="text" name="retention_period" id="retention_period"></div>
                    <div class="field"><label>프로젝트명</label><input type="text" name="project_name"></div>
                    <div class="field span-2"><label>실사용자</label><input type="text" name="actual_user"></div>
                    <div class="field span-2"><label>사진첨부</label><input type="file" name="attachment" accept="image/*"><div class="hint">첨부하지 않으면 기본 경로 E:\test\sample.png 저장</div></div>
                    <div class="field full"><label>요청사유</label><textarea name="request_reason"></textarea></div>
                </div>
                <div style="margin-top:18px;display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap;">
                    <button type="button" class="btn btn-outline" id="fillDemoBtn">데모값 채우기</button>
                    <button type="submit" class="btn btn-primary" id="submitRequestBtn">의뢰 등록</button>
                </div>
            </form>
        </div>

        <div class="tab-panel" id="request-status">
            <div class="toolbar">
                <div><h3 style="margin:0 0 4px;">입출고 신청 현황</h3><div class="hint">행 클릭 시 상세팝업, 헤더 클릭 시 정렬, 10건 단위 페이징</div></div>
                <div class="filter-row"><input type="text" id="requestSearch" placeholder="자재코드 / 품명 / 요청자 검색"><select id="requestStatusFilter"><option value="">전체 상태</option><option value="대기">대기</option><option value="승인">승인</option><option value="반려">반려</option></select></div>
            </div>
            <div class="table-wrap">
                <table id="requestTable">
                    <thead><tr>
                        <th class="sortable" data-sort-type="number">ID</th><th class="sortable">상태</th><th class="sortable">입/출고</th><th class="sortable">자재코드</th><th class="sortable">발주번호</th><th class="sortable">품명/규격</th><th class="sortable">등급</th><th class="sortable">자재구분</th><th class="sortable">건물/공정/모듈</th><th class="sortable" data-sort-type="number">수량</th><th class="sortable">요청자</th><th class="sortable">구매의뢰자</th><th class="sortable">프로젝트</th><th>사유</th><th>첨부</th><th class="sortable">등록일</th><th>관리자처리</th>
                    </tr></thead>
                    <tbody>
                    {% for row in requests_data %}
                        <tr class="clickable-row detail-row" data-detail-type="request" data-detail-id="{{ row.id }}">
                            <td>{{ row.id }}</td>
                            <td>{% if row.status == '대기' %}<span class="badge waiting">대기</span>{% elif row.status == '승인' %}<span class="badge approved">승인</span>{% else %}<span class="badge rejected">반려</span>{% endif %}</td>
                            <td>{{ row.request_type }}</td><td>{{ row.material_code }}</td><td>{{ row.po_no or '-' }}</td><td>{{ row.item_name }}<br><span class="hint">{{ row.item_spec }}</span></td><td>{{ row.grade }}</td><td>{{ row.material_category }}</td><td>{{ row.building_name }} / {{ row.process_name }} / {{ row.module_name }}</td><td>{{ row.quantity }}</td><td>{{ row.requester }}</td><td>{{ row.purchase_requester }}</td><td>{{ row.project_name }}</td><td>{{ row.request_reason }}</td><td>{% if row.attachment_path %}<span class="hint">저장됨</span>{% else %}-{% endif %}</td><td>{{ row.created_at }}</td>
                            <td>
                            {% if row.status == '대기' %}
                                <div class="admin-box">
                                    <form method="POST" action="{{ url_for('approve_request', req_id=row.id) }}" class="row-action-form confirm-form" data-confirm-message="해당 요청을 승인하시겠습니까?">
                                        <input type="text" name="admin_comment" placeholder="승인/반려 코멘트">
                                        <button class="btn btn-green btn-small" type="submit">승인</button>
                                    </form>
                                    <form method="POST" action="{{ url_for('reject_request', req_id=row.id) }}" class="row-action-form confirm-form" data-confirm-message="해당 요청을 반려하시겠습니까?">
                                        <input type="hidden" name="admin_comment" value="">
                                        <button class="btn btn-red btn-small transfer-comment-btn" type="submit">반려</button>
                                    </form>
                                </div>
                            {% else %}
                                <div>{{ row.admin_comment or '-' }}</div><div class="hint">{{ row.approved_at or '-' }}</div>
                            {% endif %}
                            </td>
                        </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
            <div class="pagination" id="requestPagination"></div>
        </div>

        <div class="tab-panel" id="inventory-status">
            <div class="toolbar"><div><h3 style="margin:0 0 4px;">보관 자재 현황</h3><div class="hint">행 클릭 시 상세팝업</div></div><div class="filter-row"><input type="text" id="inventorySearch" placeholder="자재코드 / 품명 / 프로젝트 검색"></div></div>
            <div class="table-wrap">
                <table id="inventoryTable">
                    <thead><tr>
                        <th class="sortable" data-sort-type="number">ID</th><th class="sortable">보관상태</th><th class="sortable">자재코드</th><th class="sortable">품명/규격</th><th class="sortable">등급/자재구분</th><th class="sortable">건물/공정/모듈</th><th class="sortable" data-sort-type="number">수량</th><th class="sortable">사용가능여부</th><th class="sortable">보관기간</th><th class="sortable">프로젝트명</th><th class="sortable">실사용자</th><th class="sortable">최종갱신일</th>
                    </tr></thead>
                    <tbody>
                    {% for row in inventory_data %}
                        <tr class="clickable-row detail-row" data-detail-type="inventory" data-detail-id="{{ row.id }}">
                            <td>{{ row.id }}</td><td><span class="badge storage">{{ row.storage_status }}</span></td><td>{{ row.material_code }}</td><td>{{ row.item_name }}<br><span class="hint">{{ row.item_spec }}</span></td><td>{{ row.grade }} / {{ row.material_category }}</td><td>{{ row.building_name }} / {{ row.process_name }} / {{ row.module_name }}</td><td>{{ row.quantity }}</td><td>{{ row.usability_status }}</td><td>{{ row.retention_period }}</td><td>{{ row.project_name }}</td><td>{{ row.actual_user }}</td><td>{{ row.last_updated_at }}</td>
                        </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
            <div class="pagination" id="inventoryPagination"></div>
        </div>

        <div class="tab-panel" id="transaction-status">
            <div class="toolbar"><div><h3 style="margin:0 0 4px;">입출고 이력</h3><div class="hint">행 클릭 시 상세팝업</div></div><div class="filter-row"><input type="text" id="txSearch" placeholder="자재코드 / 구분 / 메모 검색"></div></div>
            <div class="table-wrap">
                <table id="txTable">
                    <thead><tr>
                        <th class="sortable" data-sort-type="number">ID</th><th class="sortable" data-sort-type="number">요청ID</th><th class="sortable">자재코드</th><th class="sortable">구분</th><th class="sortable" data-sort-type="number">수량</th><th class="sortable">처리상태</th><th class="sortable">비고</th><th class="sortable">처리일시</th>
                    </tr></thead>
                    <tbody>
                    {% for row in tx_data %}
                        <tr class="clickable-row detail-row" data-detail-type="transaction" data-detail-id="{{ row.id }}">
                            <td>{{ row.id }}</td><td>{{ row.request_id }}</td><td>{{ row.material_code }}</td><td>{{ row.tx_type }}</td><td>{{ row.quantity }}</td><td>{{ row.tx_status }}</td><td>{{ row.note }}</td><td>{{ row.created_at }}</td>
                        </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
            <div class="pagination" id="txPagination"></div>
        </div>
    </div>
</div>

<div class="modal-overlay" id="detailModalOverlay">
    <div class="modal">
        <div class="modal-header"><h3 id="detailTitle">상세내역</h3><button class="close-btn" id="detailModalClose">✕</button></div>
        <div class="detail-layout">
            <div class="detail-card">
                <div class="detail-grid">
                    <div class="field"><label>ID</label><input type="text" id="detail_id" readonly></div>
                    <div class="field"><label>상태</label><input type="text" id="detail_status" readonly></div>
                    <div class="field"><label>입/출고 구분</label><input type="text" id="detail_request_type"></div>
                    <div class="field"><label>자재코드</label><input type="text" id="detail_material_code"></div>
                    <div class="field"><label>발주번호</label><input type="text" id="detail_po_no"></div>
                    <div class="field"><label>품명</label><input type="text" id="detail_item_name"></div>
                    <div class="field"><label>규격</label><input type="text" id="detail_item_spec"></div>
                    <div class="field"><label>등급</label><input type="text" id="detail_grade"></div>
                    <div class="field"><label>자재구분</label><input type="text" id="detail_material_category"></div>
                    <div class="field"><label>건물명</label><input type="text" id="detail_building_name"></div>
                    <div class="field"><label>설비공정</label><input type="text" id="detail_process_name"></div>
                    <div class="field"><label>세대/개발호기</label><input type="text" id="detail_generation_name"></div>
                    <div class="field"><label>모듈명</label><input type="text" id="detail_module_name"></div>
                    <div class="field"><label>수량</label><input type="number" id="detail_quantity" min="1"></div>
                    <div class="field"><label>요청자</label><input type="text" id="detail_requester"></div>
                    <div class="field"><label>구매의뢰자</label><input type="text" id="detail_purchase_requester"></div>
                    <div class="field"><label>업체명</label><input type="text" id="detail_vendor_name"></div>
                    <div class="field"><label>입고유형</label><input type="text" id="detail_inbound_type"></div>
                    <div class="field"><label>구매유형</label><input type="text" id="detail_purchase_type"></div>
                    <div class="field"><label>사용가능여부</label><input type="text" id="detail_usability_status"></div>
                    <div class="field"><label>보관기간</label><input type="text" id="detail_retention_period"></div>
                    <div class="field"><label>프로젝트명</label><input type="text" id="detail_project_name"></div>
                    <div class="field"><label>실사용자</label><input type="text" id="detail_actual_user"></div>
                    <div class="field full"><label>이미지 경로</label><input type="text" id="detail_attachment_path"></div>
                    <div class="field full"><label>요청사유 / 비고</label><textarea id="detail_request_reason"></textarea></div>
                    <div class="field full"><label>관리자 코멘트</label><textarea id="detail_admin_comment"></textarea></div>
                </div>
                <div class="detail-actions">
                    <button class="btn btn-outline" type="button" id="detailLookupBtn">자재코드 다시조회</button>
                    <button class="btn btn-primary" type="button" id="detailSaveBtn">수정 저장</button>
                </div>
            </div>
            <div class="detail-card">
                <h4 style="margin-top:0;">첨부 이미지</h4>
                <img id="detailImage" class="detail-image" alt="첨부 이미지">
                <div id="detailImageEmpty" class="empty-note">이미지 경로가 없거나 파일을 찾을 수 없습니다.</div>
                <div style="margin-top:14px">
                    <div class="hint">기본 테스트 경로: E:\test\sample.png</div>
                    <div class="hint" id="detailCreatedAt"></div>
                    <div class="hint" id="detailApprovedAt"></div>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
const requestForm = document.getElementById('requestForm');
const materialCodeInput = document.getElementById('material_code');
const lookupBtn = document.getElementById('lookupBtn');
const submitRequestBtn = document.getElementById('submitRequestBtn');

const tabButtons = document.querySelectorAll('.tab-btn');
const tabPanels = document.querySelectorAll('.tab-panel');
tabButtons.forEach(btn => btn.addEventListener('click', () => {
    tabButtons.forEach(b => b.classList.remove('active'));
    tabPanels.forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(btn.dataset.tab).classList.add('active');
    history.replaceState(null, '', '#' + btn.dataset.tab);
}));
const hash = location.hash.replace('#', '');
if (hash) {
    const btn = document.querySelector(`.tab-btn[data-tab="${hash}"]`);
    const panel = document.getElementById(hash);
    if (btn && panel) { tabButtons.forEach(b => b.classList.remove('active')); tabPanels.forEach(p => p.classList.remove('active')); btn.classList.add('active'); panel.classList.add('active'); }
}

async function lookupMaterial(codeValue = null, targetPrefix = '') {
    const materialCode = (codeValue ?? document.getElementById(targetPrefix + 'material_code').value).trim();
    if (!materialCode) { alert('자재코드를 먼저 입력하세요.'); return false; }
    const res = await fetch(`/api/material-lookup?material_code=${encodeURIComponent(materialCode)}`);
    if (!res.ok) { alert('자재코드를 찾을 수 없습니다.'); return false; }
    const json = await res.json();
    document.getElementById(targetPrefix + 'po_no').value = json.data.po_no || '';
    document.getElementById(targetPrefix + 'item_name').value = json.data.item_name || '';
    document.getElementById(targetPrefix + 'item_spec').value = json.data.spec || '';
    return true;
}
lookupBtn.addEventListener('click', () => lookupMaterial());
materialCodeInput.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        await lookupMaterial();
    }
});
requestForm.addEventListener('submit', (e) => {
    if (!confirm('입/출고 의뢰를 등록하시겠습니까?')) e.preventDefault();
});

async function fetchModules(processName) {
    const res = await fetch(`/api/modules?process_name=${encodeURIComponent(processName || '')}`);
    const json = await res.json();
    return json.data || [];
}
async function loadModules() {
    const processName = document.getElementById('process_name').value;
    const select = document.getElementById('module_name');
    select.innerHTML = '<option value="">불러오는 중...</option>';
    const items = await fetchModules(processName);
    select.innerHTML = '<option value="">선택</option>';
    items.forEach(item => {
        const opt = document.createElement('option');
        opt.value = item;
        opt.textContent = item;
        select.appendChild(opt);
    });
}
document.getElementById('process_name').addEventListener('change', loadModules);
async function autoRetention() {
    const materialCategory = document.getElementById('material_category').value;
    const res = await fetch(`/api/retention?material_category=${encodeURIComponent(materialCategory)}`);
    const json = await res.json();
    document.getElementById('retention_period').value = json.data || '';
}
document.getElementById('material_category').addEventListener('change', autoRetention);

document.getElementById('fillDemoBtn').addEventListener('click', async () => {
    document.getElementById('request_type').value = '입고';
    document.getElementById('material_code').value = 'MAT-1003';
    await lookupMaterial();
    document.querySelector('[name="grade"]').value = 'A등급';
    document.getElementById('material_category').value = 'PM자재';
    await autoRetention();
    document.querySelector('[name="approval_type"]').value = 'POR';
    document.querySelector('[name="building_name"]').value = 'A동';
    document.getElementById('process_name').value = 'Etcher';
    await loadModules();
    document.getElementById('module_name').value = 'Gas Box';
    document.querySelector('[name="generation_name"]').value = '알파';
    document.querySelector('[name="quantity"]').value = '3';
    document.querySelector('[name="requester"]').value = '정기훈';
    document.querySelector('[name="purchase_requester"]').value = '구매담당';
    document.querySelector('[name="vendor_name"]').value = 'Demo Vendor';
    document.querySelector('[name="inbound_type"]').value = '신규입고';
    document.querySelector('[name="purchase_type"]').value = '상용품';
    document.querySelector('[name="usability_status"]').value = '사용가능';
    document.querySelector('[name="project_name"]').value = 'Project Titan';
    document.querySelector('[name="actual_user"]').value = '실사용 담당자';
    document.querySelector('[name="request_reason"]').value = '라인 유지보수용 예비품 보관 테스트';
});

document.querySelectorAll('.row-action-form').forEach(form => {
    form.addEventListener('click', (e) => e.stopPropagation());
    form.addEventListener('submit', (e) => {
        const msg = form.dataset.confirmMessage || '진행하시겠습니까?';
        const sharedInput = form.parentElement.querySelector('input[type="text"]');
        const hiddenInput = form.querySelector('input[type="hidden"][name="admin_comment"]');
        if (hiddenInput && sharedInput) hiddenInput.value = sharedInput.value;
        if (!confirm(msg)) e.preventDefault();
    });
});

function createTableManager({ tableId, paginationId, searchInputId = null, extraFilter = null, pageSize = 10, maxPageButtons = 10 }) {
    const table = document.getElementById(tableId);
    const tbody = table.querySelector('tbody');
    const originalRows = Array.from(tbody.querySelectorAll('tr'));
    const pagination = document.getElementById(paginationId);
    const searchInput = searchInputId ? document.getElementById(searchInputId) : null;
    const headers = Array.from(table.querySelectorAll('thead th.sortable'));

    let filteredRows = [...originalRows];
    let currentPage = 1;
    let pageGroup = 0;
    let sortColumnIndex = null;
    let sortDirection = null; // null -> 원상태

    function getCellValue(row, index) {
        return (row.children[index]?.innerText || '').trim();
    }
    function normalizeValue(value, type) {
        if (type === 'number') return parseFloat(String(value).replace(/[^0-9.-]/g, '')) || 0;
        return String(value).trim();
    }
    function applyFilters() {
        const keyword = (searchInput?.value || '').toLowerCase().trim();
        filteredRows = originalRows.filter(row => {
            const text = row.innerText.toLowerCase();
            const keywordMatch = !keyword || text.includes(keyword);
            const extraMatch = typeof extraFilter === 'function' ? extraFilter(row) : true;
            return keywordMatch && extraMatch;
        });

        if (sortColumnIndex !== null && sortDirection !== null) {
            const header = headers.find(h => Number(h.dataset.colIndex) === sortColumnIndex);
            const type = header?.dataset.sortType || 'text';
            filteredRows.sort((a, b) => {
                const av = normalizeValue(getCellValue(a, sortColumnIndex), type);
                const bv = normalizeValue(getCellValue(b, sortColumnIndex), type);
                let cmp = 0;
                if (type === 'number') cmp = av - bv;
                else cmp = String(av).localeCompare(String(bv), 'ko');
                return sortDirection === 'asc' ? cmp : -cmp;
            });
        } else {
            filteredRows = originalRows.filter(row => {
                const text = row.innerText.toLowerCase();
                const keywordMatch = !keyword || text.includes(keyword);
                const extraMatch = typeof extraFilter === 'function' ? extraFilter(row) : true;
                return keywordMatch && extraMatch;
            });
        }
        currentPage = 1;
        pageGroup = 0;
        render();
    }
    function render() {
        originalRows.forEach(row => row.style.display = 'none');
        const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
        if (currentPage > totalPages) currentPage = totalPages;
        const start = (currentPage - 1) * pageSize;
        filteredRows.slice(start, start + pageSize).forEach(row => row.style.display = '');
        renderPagination(totalPages);
    }
    function renderPagination(totalPages) {
        pagination.innerHTML = '';
        const startPage = pageGroup * maxPageButtons + 1;
        const endPage = Math.min(startPage + maxPageButtons - 1, totalPages);

        if (startPage > 1) {
            const prev = document.createElement('button');
            prev.className = 'page-btn'; prev.textContent = '<';
            prev.addEventListener('click', () => { pageGroup -= 1; currentPage = pageGroup * maxPageButtons + 1; render(); });
            pagination.appendChild(prev);
        }
        for (let i = startPage; i <= endPage; i++) {
            const btn = document.createElement('button');
            btn.className = 'page-btn' + (i === currentPage ? ' active' : '');
            btn.textContent = `[${i}]`;
            btn.addEventListener('click', () => { currentPage = i; render(); });
            pagination.appendChild(btn);
        }
        if (endPage < totalPages) {
            const next = document.createElement('button');
            next.className = 'page-btn'; next.textContent = '>';
            next.addEventListener('click', () => { pageGroup += 1; currentPage = pageGroup * maxPageButtons + 1; render(); });
            pagination.appendChild(next);
        }
    }

    headers.forEach(header => {
        const actualIndex = header.cellIndex;
        header.dataset.colIndex = actualIndex;
        header.classList.add('none');
        header.addEventListener('click', () => {
            headers.forEach(h => h.classList.remove('asc', 'desc', 'none'));
            if (sortColumnIndex !== actualIndex) {
                sortColumnIndex = actualIndex;
                sortDirection = 'asc';
            } else if (sortDirection === 'asc') {
                sortDirection = 'desc';
            } else if (sortDirection === 'desc') {
                sortDirection = null;
                sortColumnIndex = null;
            } else {
                sortDirection = 'asc';
            }
            if (sortColumnIndex === null || sortDirection === null) {
                headers.forEach(h => h.classList.add('none'));
            } else {
                headers.forEach(h => h.classList.add('none'));
                header.classList.remove('none');
                header.classList.add(sortDirection);
            }
            applyFilters();
        });
    });

    searchInput?.addEventListener('input', applyFilters);
    return { render, applyFilters };
}

const requestStatusFilter = document.getElementById('requestStatusFilter');
const requestManager = createTableManager({
    tableId: 'requestTable', paginationId: 'requestPagination', searchInputId: 'requestSearch',
    extraFilter: (row) => !requestStatusFilter.value || row.children[1]?.innerText.includes(requestStatusFilter.value)
});
requestStatusFilter.addEventListener('change', requestManager.applyFilters);
const inventoryManager = createTableManager({ tableId: 'inventoryTable', paginationId: 'inventoryPagination', searchInputId: 'inventorySearch' });
const txManager = createTableManager({ tableId: 'txTable', paginationId: 'txPagination', searchInputId: 'txSearch' });
requestManager.render(); inventoryManager.render(); txManager.render();

const detailModalOverlay = document.getElementById('detailModalOverlay');
const detailModalClose = document.getElementById('detailModalClose');
const detailTitle = document.getElementById('detailTitle');
let currentDetailType = null;
let currentDetailId = null;
function openModal(){ detailModalOverlay.classList.add('show'); }
function closeModal(){ detailModalOverlay.classList.remove('show'); }
detailModalClose.addEventListener('click', closeModal);
detailModalOverlay.addEventListener('click', (e) => { if (e.target === detailModalOverlay) closeModal(); });

function setValue(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    el.value = value ?? '';
}
function toggleDetailEditable(editable) {
    ['detail_request_type','detail_material_code','detail_po_no','detail_item_name','detail_item_spec','detail_grade','detail_material_category','detail_building_name','detail_process_name','detail_generation_name','detail_module_name','detail_quantity','detail_requester','detail_purchase_requester','detail_vendor_name','detail_inbound_type','detail_purchase_type','detail_usability_status','detail_retention_period','detail_project_name','detail_actual_user','detail_attachment_path','detail_request_reason','detail_admin_comment']
    .forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') el.readOnly = !editable;
    });
    document.getElementById('detailSaveBtn').style.display = editable ? '' : 'none';
    document.getElementById('detailLookupBtn').style.display = editable ? '' : 'none';
}

async function openDetail(type, id) {
    const endpoint = type === 'request' ? `/api/request/${id}` : (type === 'inventory' ? `/api/inventory/${id}` : `/api/transaction/${id}`);
    const res = await fetch(endpoint);
    if (!res.ok) { alert('상세내역을 불러오지 못했습니다.'); return; }
    const json = await res.json();
    const d = json.data;
    currentDetailType = type;
    currentDetailId = id;
    detailTitle.textContent = type === 'request' ? '입출고 신청 상세내역' : (type === 'inventory' ? '보관 자재 상세내역' : '입출고 이력 상세내역');

    setValue('detail_id', d.id);
    setValue('detail_status', d.status || d.request_status || d.tx_status || d.storage_status || '');
    setValue('detail_request_type', d.request_type || d.tx_type || '');
    setValue('detail_material_code', d.material_code);
    setValue('detail_po_no', d.po_no);
    setValue('detail_item_name', d.item_name);
    setValue('detail_item_spec', d.item_spec);
    setValue('detail_grade', d.grade);
    setValue('detail_material_category', d.material_category);
    setValue('detail_building_name', d.building_name);
    setValue('detail_process_name', d.process_name);
    setValue('detail_generation_name', d.generation_name);
    setValue('detail_module_name', d.module_name);
    setValue('detail_quantity', d.quantity);
    setValue('detail_requester', d.requester);
    setValue('detail_purchase_requester', d.purchase_requester);
    setValue('detail_vendor_name', d.vendor_name);
    setValue('detail_inbound_type', d.inbound_type);
    setValue('detail_purchase_type', d.purchase_type);
    setValue('detail_usability_status', d.usability_status);
    setValue('detail_retention_period', d.retention_period);
    setValue('detail_project_name', d.project_name);
    setValue('detail_actual_user', d.actual_user);
    setValue('detail_attachment_path', d.attachment_path);
    setValue('detail_request_reason', d.request_reason || d.note || '');
    setValue('detail_admin_comment', d.admin_comment || '');
    document.getElementById('detailCreatedAt').textContent = `등록일/처리일: ${d.created_at || '-'}`;
    document.getElementById('detailApprovedAt').textContent = `승인일/최종갱신일: ${d.approved_at || d.last_updated_at || '-'}`;

    const img = document.getElementById('detailImage');
    const empty = document.getElementById('detailImageEmpty');
    if (d.image_view_url) {
        img.src = d.image_view_url;
        img.style.display = '';
        empty.style.display = 'none';
        img.onerror = () => { img.style.display = 'none'; empty.style.display = ''; };
    } else {
        img.removeAttribute('src');
        img.style.display = 'none';
        empty.style.display = '';
    }

    toggleDetailEditable(type === 'request');
    openModal();
}

document.querySelectorAll('.detail-row').forEach(row => {
    row.addEventListener('click', () => openDetail(row.dataset.detailType, row.dataset.detailId));
});

document.getElementById('detailLookupBtn').addEventListener('click', async () => {
    await lookupMaterial(document.getElementById('detail_material_code').value, 'detail_');
});

document.getElementById('detailSaveBtn').addEventListener('click', async () => {
    if (currentDetailType !== 'request' || !currentDetailId) return;
    if (!confirm('상세내역을 수정 저장하시겠습니까?')) return;
    const payload = {
        request_type: document.getElementById('detail_request_type').value,
        material_code: document.getElementById('detail_material_code').value,
        po_no: document.getElementById('detail_po_no').value,
        item_name: document.getElementById('detail_item_name').value,
        item_spec: document.getElementById('detail_item_spec').value,
        grade: document.getElementById('detail_grade').value,
        material_category: document.getElementById('detail_material_category').value,
        building_name: document.getElementById('detail_building_name').value,
        process_name: document.getElementById('detail_process_name').value,
        generation_name: document.getElementById('detail_generation_name').value,
        module_name: document.getElementById('detail_module_name').value,
        quantity: document.getElementById('detail_quantity').value,
        requester: document.getElementById('detail_requester').value,
        purchase_requester: document.getElementById('detail_purchase_requester').value,
        vendor_name: document.getElementById('detail_vendor_name').value,
        request_reason: document.getElementById('detail_request_reason').value,
        inbound_type: document.getElementById('detail_inbound_type').value,
        purchase_type: document.getElementById('detail_purchase_type').value,
        usability_status: document.getElementById('detail_usability_status').value,
        retention_period: document.getElementById('detail_retention_period').value,
        project_name: document.getElementById('detail_project_name').value,
        actual_user: document.getElementById('detail_actual_user').value,
        attachment_path: document.getElementById('detail_attachment_path').value,
        admin_comment: document.getElementById('detail_admin_comment').value,
    };
    const res = await fetch(`/api/request/${currentDetailId}/update`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
    });
    const json = await res.json();
    if (!res.ok || !json.success) { alert(json.message || '저장에 실패했습니다.'); return; }
    alert('수정이 완료되었습니다.');
    location.reload();
});

autoRetention();
</script>
</body>
</html>
'''


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
