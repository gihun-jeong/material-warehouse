from flask import (
    Flask, request, redirect, url_for, jsonify,
    send_from_directory, render_template, flash, abort
)
import sqlite3
import os
import uuid
from datetime import datetime, date
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "demo-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "material_demo.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

DEFAULT_TEST_IMAGE_PATH = r"E:\test\sample.png"

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
REQUEST_TYPE_OPTIONS = ["입고", "출고", "수정"]
REQUEST_ACTION_OPTIONS = ["입고의뢰", "출고의뢰", "보관정보수정"]

RETENTION_RULES = {
    "Running 자재": "1년",
    "PM자재": "1년",
    "유휴자재": "1년 6개월",
    "사후관리자재": "최대 5년",
    "Open 자재": "6개월",
}


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


def get_inventory_by_id(inv_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM material_inventory WHERE id=?", (inv_id,))
    row = cur.fetchone()
    conn.close()
    return row


def get_transaction_by_id(tx_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            t.*,
            r.po_no, r.item_name, r.item_spec, r.grade, r.material_category,
            r.building_name, r.process_name, r.generation_name, r.module_name,
            r.requester, r.purchase_requester, r.vendor_name, r.request_reason,
            r.inbound_type, r.purchase_type, r.usability_status, r.retention_period,
            r.project_name, r.actual_user, r.attachment_path, r.status AS request_status,
            r.admin_comment, r.request_action
        FROM material_transactions t
        LEFT JOIN material_requests r ON t.request_id = r.id
        WHERE t.id=?
        """,
        (tx_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row


def row_to_dict(row):
    return dict(row) if row else None


def build_image_view_url(image_path):
    if not image_path:
        return None
    return url_for("file_preview") + f"?path={image_path}"


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS material_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_type TEXT NOT NULL,
            request_action TEXT DEFAULT '입고의뢰',
            target_inventory_id INTEGER,
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

    ensure_column("material_requests", "request_action", "TEXT DEFAULT '입고의뢰'")
    ensure_column("material_requests", "target_inventory_id", "INTEGER")
    ensure_column("material_inventory", "attachment_path", "TEXT")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM material_requests")
    cnt = cur.fetchone()["cnt"]

    if cnt == 0:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        demo_requests = [
            (
                "입고", "입고의뢰", None, "MAT-1001", "PO-2026-0001", "세라믹 챔버 링", "Ø220 / High Temp",
                "A등급", "Running 자재", "POR", "A동", "Etcher", "양산", "ESC Module",
                5, "김테스트", "박구매", "ABC Tech", "예비품 보관", "신규입고", "가공품",
                "사용가능", "1년", "Project Atlas", "이실사용", DEFAULT_TEST_IMAGE_PATH, "승인", "", now, now
            ),
            (
                "입고", "입고의뢰", None, "MAT-1002", "PO-2026-0002", "쿼츠 라이너", "QZ-LN-ETCH-01",
                "B등급", "유휴자재", "SPLIT", "B동", "CVD", "베타", "Shower Head",
                2, "정사용", "오구매", "Quartz Co", "라인 이관 보관", "재입고", "상용품",
                "세정완료", "1년 6개월", "Project Nova", "한실사용", DEFAULT_TEST_IMAGE_PATH, "대기", "", now, None
            ),
        ]

        cur.executemany(
            """
            INSERT INTO material_requests (
                request_type, request_action, target_inventory_id, material_code, po_no, item_name, item_spec,
                grade, material_category, approval_type, building_name, process_name, generation_name, module_name,
                quantity, requester, purchase_requester, vendor_name, request_reason, inbound_type, purchase_type,
                usability_status, retention_period, project_name, actual_user, attachment_path, status, admin_comment,
                created_at, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            demo_requests
        )
        conn.commit()

        cur.execute("SELECT * FROM material_requests WHERE status='승인' AND request_action='입고의뢰'")
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


def apply_approved_request(request_row):
    conn = get_db_connection()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    request_type = request_row["request_type"]
    request_action = request_row["request_action"]
    target_inventory_id = request_row["target_inventory_id"]

    if request_type == "입고" and request_action == "입고의뢰":
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
                    request_row["id"], request_row["material_code"], request_row["item_name"], request_row["item_spec"],
                    request_row["grade"], request_row["material_category"], request_row["building_name"], request_row["process_name"],
                    request_row["generation_name"], request_row["module_name"], request_row["quantity"], request_row["usability_status"],
                    request_row["retention_period"], request_row["project_name"], request_row["actual_user"], request_row["attachment_path"],
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
                    request_row["material_code"], request_row["item_name"], request_row["item_spec"], request_row["grade"],
                    request_row["material_category"], request_row["building_name"], request_row["process_name"],
                    request_row["generation_name"], request_row["module_name"], request_row["quantity"], request_row["usability_status"],
                    request_row["retention_period"], request_row["project_name"], request_row["actual_user"], request_row["attachment_path"],
                    now, request_row["id"]
                )
            )

        cur.execute(
            """
            INSERT INTO material_transactions (request_id, material_code, tx_type, quantity, tx_status, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (request_row["id"], request_row["material_code"], "입고", request_row["quantity"], "완료", "입고 의뢰 승인", now)
        )

    elif request_type == "수정" and request_action == "보관정보수정":
        cur.execute("SELECT * FROM material_inventory WHERE id=?", (target_inventory_id,))
        inv = cur.fetchone()
        if inv:
            cur.execute(
                """
                UPDATE material_inventory
                SET material_code=?, item_name=?, item_spec=?, grade=?, material_category=?, building_name=?,
                    process_name=?, generation_name=?, module_name=?, quantity=?, usability_status=?,
                    retention_period=?, project_name=?, actual_user=?, attachment_path=?, last_updated_at=?
                WHERE id=?
                """,
                (
                    request_row["material_code"], request_row["item_name"], request_row["item_spec"], request_row["grade"],
                    request_row["material_category"], request_row["building_name"], request_row["process_name"],
                    request_row["generation_name"], request_row["module_name"], request_row["quantity"], request_row["usability_status"],
                    request_row["retention_period"], request_row["project_name"], request_row["actual_user"], request_row["attachment_path"],
                    now, target_inventory_id
                )
            )
            cur.execute(
                """
                INSERT INTO material_transactions (request_id, material_code, tx_type, quantity, tx_status, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (request_row["id"], request_row["material_code"], "수정", request_row["quantity"], "완료", "보관정보 수정 승인", now)
            )

    elif request_type == "출고" and request_action == "출고의뢰":
        cur.execute("SELECT * FROM material_inventory WHERE id=?", (target_inventory_id,))
        inv = cur.fetchone()
        if inv:
            new_qty = max((inv["quantity"] or 0) - (request_row["quantity"] or 0), 0)
            storage_status = "보관중" if new_qty > 0 else "출고완료"

            cur.execute(
                """
                UPDATE material_inventory
                SET quantity=?, storage_status=?, last_updated_at=?
                WHERE id=?
                """,
                (new_qty, storage_status, now, target_inventory_id)
            )

            cur.execute(
                """
                INSERT INTO material_transactions (request_id, material_code, tx_type, quantity, tx_status, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (request_row["id"], request_row["material_code"], "출고", request_row["quantity"], "완료", "출고 의뢰 승인", now)
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
        SET request_type=?, request_action=?, target_inventory_id=?, material_code=?, po_no=?, item_name=?, item_spec=?,
            grade=?, material_category=?, approval_type=?, building_name=?, process_name=?, generation_name=?, module_name=?,
            quantity=?, requester=?, purchase_requester=?, vendor_name=?, request_reason=?, inbound_type=?, purchase_type=?,
            usability_status=?, retention_period=?, project_name=?, actual_user=?, attachment_path=?, admin_comment=?
        WHERE id=?
        """,
        (
            payload.get("request_type"), payload.get("request_action"), payload.get("target_inventory_id"),
            material_code, po_no, item_name, item_spec, payload.get("grade"), payload.get("material_category"),
            payload.get("approval_type"), payload.get("building_name"), payload.get("process_name"),
            payload.get("generation_name"), payload.get("module_name"), quantity, payload.get("requester"),
            payload.get("purchase_requester"), payload.get("vendor_name"), payload.get("request_reason"),
            payload.get("inbound_type"), payload.get("purchase_type"), payload.get("usability_status"),
            payload.get("retention_period"), payload.get("project_name"), payload.get("actual_user"),
            attachment_path, payload.get("admin_comment", existing["admin_comment"]), req_id
        )
    )

    updated = get_request_by_id(req_id)
    data = row_to_dict(updated)
    data["image_view_url"] = build_image_view_url(data.get("attachment_path")) if data.get("attachment_path") else None
    data["detail_type"] = "request"
    return jsonify({"success": True, "message": "요청 내역이 수정되었습니다.", "data": data})


@app.route("/api/inventory/<int:inv_id>")
def api_inventory_detail(inv_id):
    row = get_inventory_by_id(inv_id)
    if not row:
        return jsonify({"success": False, "message": "데이터를 찾을 수 없습니다."}), 404
    data = row_to_dict(row)
    data["image_view_url"] = build_image_view_url(data.get("attachment_path")) if data.get("attachment_path") else None
    data["detail_type"] = "inventory"
    return jsonify({"success": True, "data": data})


@app.route("/api/transaction/<int:tx_id>")
def api_transaction_detail(tx_id):
    row = get_transaction_by_id(tx_id)
    if not row:
        return jsonify({"success": False, "message": "데이터를 찾을 수 없습니다."}), 404
    data = row_to_dict(row)
    data["image_view_url"] = build_image_view_url(data.get("attachment_path")) if data.get("attachment_path") else None
    data["detail_type"] = "transaction"
    return jsonify({"success": True, "data": data})


@app.route("/api/inventory/<int:inv_id>/request-update", methods=["POST"])
def api_inventory_request_update(inv_id):
    inv = get_inventory_by_id(inv_id)
    if not inv:
        return jsonify({"success": False, "message": "보관 자재를 찾을 수 없습니다."}), 404

    payload = request.get_json(silent=True) or {}
    quantity = int(payload.get("quantity") or 0)
    if quantity <= 0:
        return jsonify({"success": False, "message": "수량은 1 이상이어야 합니다."}), 400

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    req_id = execute_write(
        """
        INSERT INTO material_requests (
            request_type, request_action, target_inventory_id, material_code, po_no, item_name, item_spec,
            grade, material_category, approval_type, building_name, process_name, generation_name, module_name,
            quantity, requester, purchase_requester, vendor_name, request_reason, inbound_type, purchase_type,
            usability_status, retention_period, project_name, actual_user, attachment_path, status, admin_comment,
            created_at, approved_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '대기', '', ?, NULL)
        """,
        (
            "수정", "보관정보수정", inv_id,
            payload.get("material_code"), payload.get("po_no"), payload.get("item_name"), payload.get("item_spec"),
            payload.get("grade"), payload.get("material_category"), payload.get("approval_type", "N/A"),
            payload.get("building_name"), payload.get("process_name"), payload.get("generation_name"),
            payload.get("module_name"), quantity, payload.get("requester"), payload.get("purchase_requester"),
            payload.get("vendor_name"), payload.get("request_reason"), payload.get("inbound_type"),
            payload.get("purchase_type"), payload.get("usability_status"), payload.get("retention_period"),
            payload.get("project_name"), payload.get("actual_user"), payload.get("attachment_path") or DEFAULT_TEST_IMAGE_PATH,
            created_at
        )
    )

    return jsonify({"success": True, "message": f"보관정보 수정 요청이 등록되었습니다. (요청ID: {req_id})"})


@app.route("/api/inventory/<int:inv_id>/request-outbound", methods=["POST"])
def api_inventory_request_outbound(inv_id):
    inv = get_inventory_by_id(inv_id)
    if not inv:
        return jsonify({"success": False, "message": "보관 자재를 찾을 수 없습니다."}), 404

    payload = request.get_json(silent=True) or {}
    quantity = int(payload.get("quantity") or 0)
    if quantity <= 0:
        return jsonify({"success": False, "message": "출고 수량은 1 이상이어야 합니다."}), 400

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    req_id = execute_write(
        """
        INSERT INTO material_requests (
            request_type, request_action, target_inventory_id, material_code, po_no, item_name, item_spec,
            grade, material_category, approval_type, building_name, process_name, generation_name, module_name,
            quantity, requester, purchase_requester, vendor_name, request_reason, inbound_type, purchase_type,
            usability_status, retention_period, project_name, actual_user, attachment_path, status, admin_comment,
            created_at, approved_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '대기', '', ?, NULL)
        """,
        (
            "출고", "출고의뢰", inv_id,
            inv["material_code"], None, inv["item_name"], inv["item_spec"], inv["grade"], inv["material_category"],
            "N/A", inv["building_name"], inv["process_name"], inv["generation_name"], inv["module_name"],
            quantity, payload.get("requester"), payload.get("purchase_requester"), payload.get("vendor_name"),
            payload.get("request_reason"), "재입고", payload.get("purchase_type"), inv["usability_status"],
            inv["retention_period"], inv["project_name"], inv["actual_user"], inv["attachment_path"],
            created_at
        )
    )

    return jsonify({"success": True, "message": f"출고 의뢰가 등록되었습니다. (요청ID: {req_id})"})


@app.route("/materials", methods=["GET", "POST"])
def materials_page():
    if request.method == "POST":
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
                request_type, request_action, target_inventory_id, material_code, po_no, item_name, item_spec,
                grade, material_category, approval_type, building_name, process_name, generation_name, module_name,
                quantity, requester, purchase_requester, vendor_name, request_reason, inbound_type, purchase_type,
                usability_status, retention_period, project_name, actual_user, attachment_path, status, admin_comment,
                created_at, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '대기', '', ?, NULL)
            """,
            (
                "입고", "입고의뢰", None, material_code, po_no, item_name, item_spec,
                request.form.get("grade"), request.form.get("material_category"), request.form.get("approval_type"),
                request.form.get("building_name"), request.form.get("process_name"), request.form.get("generation_name"),
                request.form.get("module_name"), int(request.form.get("quantity") or 0), request.form.get("requester"),
                request.form.get("purchase_requester"), request.form.get("vendor_name"), request.form.get("request_reason"),
                request.form.get("inbound_type"), request.form.get("purchase_type"), request.form.get("usability_status"),
                request.form.get("retention_period"), request.form.get("project_name"), request.form.get("actual_user"),
                attachment_path, created_at
            )
        )
        flash("입고 의뢰가 등록되었습니다.")
        return redirect(url_for("materials_page"))

    today_str = date.today().strftime("%Y-%m-%d")
    request_date_from = (request.args.get("request_date_from") or today_str).strip()
    request_date_to = (request.args.get("request_date_to") or today_str).strip()

    requests_data = fetch_all_dicts(
        """
        SELECT *
        FROM material_requests
        WHERE date(created_at) BETWEEN date(?) AND date(?)
        ORDER BY id DESC
        """,
        [request_date_from, request_date_to]
    )

    inventory_data = fetch_all_dicts(
        """
        SELECT *
        FROM material_inventory
        WHERE quantity >= 1
        ORDER BY id DESC
        """
    )

    tx_data = fetch_all_dicts("SELECT * FROM material_transactions ORDER BY id DESC")

    return render_template(
        "materials.html",        
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
        request_date_from=request_date_from,
        request_date_to=request_date_to,
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
        apply_approved_request(row)
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


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
