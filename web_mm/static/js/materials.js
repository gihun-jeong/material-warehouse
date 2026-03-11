const requestForm = document.getElementById("requestForm");
const materialCodeInput = document.getElementById("material_code");
const lookupBtn = document.getElementById("lookupBtn");

const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanels = document.querySelectorAll(".tab-panel");

tabButtons.forEach(btn => btn.addEventListener("click", () => {
    tabButtons.forEach(b => b.classList.remove("active"));
    tabPanels.forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
    history.replaceState(null, "", "#" + btn.dataset.tab);
}));

const hash = location.hash.replace("#", "");
if (hash) {
    const btn = document.querySelector(`.tab-btn[data-tab="${hash}"]`);
    const panel = document.getElementById(hash);
    if (btn && panel) {
        tabButtons.forEach(b => b.classList.remove("active"));
        tabPanels.forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        panel.classList.add("active");
    }
}

async function lookupMaterial(codeValue = null, targetPrefix = "") {
    const materialCode = (codeValue ?? document.getElementById(targetPrefix + "material_code").value).trim();
    if (!materialCode) {
        alert("자재코드를 먼저 입력하세요.");
        return false;
    }
    const res = await fetch(`/api/material-lookup?material_code=${encodeURIComponent(materialCode)}`);
    if (!res.ok) {
        alert("자재코드를 찾을 수 없습니다.");
        return false;
    }
    const json = await res.json();
    document.getElementById(targetPrefix + "po_no").value = json.data.po_no || "";
    document.getElementById(targetPrefix + "item_name").value = json.data.item_name || "";
    document.getElementById(targetPrefix + "item_spec").value = json.data.spec || "";
    return true;
}

lookupBtn.addEventListener("click", () => lookupMaterial());

materialCodeInput.addEventListener("keydown", async (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        await lookupMaterial();
    }
});

requestForm.addEventListener("submit", (e) => {
    if (!confirm("입고 의뢰를 등록하시겠습니까?")) {
        e.preventDefault();
    }
});

async function fetchModules(processName) {
    const res = await fetch(`/api/modules?process_name=${encodeURIComponent(processName || "")}`);
    const json = await res.json();
    return json.data || [];
}

async function loadModules() {
    const processName = document.getElementById("process_name").value;
    const select = document.getElementById("module_name");
    select.innerHTML = '<option value="">불러오는 중...</option>';
    const items = await fetchModules(processName);
    select.innerHTML = '<option value="">선택</option>';
    items.forEach(item => {
        const opt = document.createElement("option");
        opt.value = item;
        opt.textContent = item;
        select.appendChild(opt);
    });
}

document.getElementById("process_name").addEventListener("change", loadModules);

async function autoRetention() {
    const materialCategory = document.getElementById("material_category").value;
    const res = await fetch(`/api/retention?material_category=${encodeURIComponent(materialCategory)}`);
    const json = await res.json();
    document.getElementById("retention_period").value = json.data || "";
}

document.getElementById("material_category").addEventListener("change", autoRetention);

document.getElementById("fillDemoBtn").addEventListener("click", async () => {
    document.getElementById("material_code").value = "MAT-1003";
    await lookupMaterial();
    document.querySelector('[name="grade"]').value = "A등급";
    document.getElementById("material_category").value = "PM자재";
    await autoRetention();
    document.querySelector('[name="approval_type"]').value = "POR";
    document.querySelector('[name="building_name"]').value = "A동";
    document.getElementById("process_name").value = "Etcher";
    await loadModules();
    document.getElementById("module_name").value = "Gas Box";
    document.querySelector('[name="generation_name"]').value = "알파";
    document.querySelector('[name="quantity"]').value = "3";
    document.querySelector('[name="requester"]').value = "정기훈";
    document.querySelector('[name="purchase_requester"]').value = "구매담당";
    document.querySelector('[name="vendor_name"]').value = "Demo Vendor";
    document.querySelector('[name="inbound_type"]').value = "신규입고";
    document.querySelector('[name="purchase_type"]').value = "상용품";
    document.querySelector('[name="usability_status"]').value = "사용가능";
    document.querySelector('[name="project_name"]').value = "Project Titan";
    document.querySelector('[name="actual_user"]').value = "실사용 담당자";
    document.querySelector('[name="request_reason"]').value = "라인 유지보수용 예비품 보관 테스트";
});

document.querySelectorAll(".row-action-form").forEach(form => {
    form.addEventListener("click", (e) => e.stopPropagation());
    form.addEventListener("submit", (e) => {
        const msg = form.dataset.confirmMessage || "진행하시겠습니까?";
        if (!confirm(msg)) {
            e.preventDefault();
        }
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
    let sortDirection = null; // null -> 원상태, asc, desc

    function getCellValue(row, index) {
        return (row.children[index]?.innerText || '').replace(/\s+/g, ' ').trim();
    }

    function normalizeValue(value, type) {
        const raw = String(value ?? '').trim();
        if (type === 'number') {
            const num = parseFloat(raw.replace(/[^0-9.-]/g, ''));
            return Number.isNaN(num) ? 0 : num;
        }
        return raw.toLowerCase();
    }

    function getBaseRows() {
        const keyword = (searchInput?.value || '').toLowerCase().trim();
        return originalRows.filter((row) => {
            const text = row.innerText.toLowerCase();
            const keywordMatch = !keyword || text.includes(keyword);
            const extraMatch = typeof extraFilter === 'function' ? extraFilter(row) : true;
            return keywordMatch && extraMatch;
        });
    }

    function updateHeaderState(activeHeader = null) {
        headers.forEach((h) => {
            h.classList.remove('asc', 'desc', 'none');
            h.classList.add('none');
        });
        if (!activeHeader || !sortDirection) return;
        activeHeader.classList.remove('none');
        activeHeader.classList.add(sortDirection);
    }

    function getSortedCurrentPageRows(pageRows) {
        if (sortColumnIndex === null || sortDirection === null) {
            return [...pageRows];
        }

        const header = headers.find((h) => Number(h.dataset.colIndex) === sortColumnIndex);
        const type = header?.dataset.sortType || 'text';

        return [...pageRows].sort((a, b) => {
            const av = normalizeValue(getCellValue(a, sortColumnIndex), type);
            const bv = normalizeValue(getCellValue(b, sortColumnIndex), type);
            let cmp = 0;
            if (type === 'number') cmp = av - bv;
            else cmp = String(av).localeCompare(String(bv), 'ko');
            return sortDirection === 'asc' ? cmp : -cmp;
        });
    }

    function applyFilters() {
        filteredRows = getBaseRows();
        currentPage = 1;
        pageGroup = 0;
        render();
    }

    function render() {
        originalRows.forEach((row) => {
            row.style.display = 'none';
        });

        const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
        if (currentPage > totalPages) currentPage = totalPages;

        const start = (currentPage - 1) * pageSize;
        const currentPageRows = filteredRows.slice(start, start + pageSize);
        const sortedPageRows = getSortedCurrentPageRows(currentPageRows);

        sortedPageRows.forEach((row) => {
            row.style.display = '';
        });

        renderPagination(totalPages);
    }

    function renderPagination(totalPages) {
        pagination.innerHTML = '';
        const startPage = pageGroup * maxPageButtons + 1;
        const endPage = Math.min(startPage + maxPageButtons - 1, totalPages);

        if (startPage > 1) {
            const prev = document.createElement('button');
            prev.className = 'page-btn';
            prev.textContent = '<';
            prev.addEventListener('click', () => {
                pageGroup -= 1;
                currentPage = pageGroup * maxPageButtons + 1;
                render();
            });
            pagination.appendChild(prev);
        }

        for (let i = startPage; i <= endPage; i++) {
            const btn = document.createElement('button');
            btn.className = 'page-btn' + (i === currentPage ? ' active' : '');
            btn.textContent = `[${i}]`;
            btn.addEventListener('click', () => {
                currentPage = i;
                render();
            });
            pagination.appendChild(btn);
        }

        if (endPage < totalPages) {
            const next = document.createElement('button');
            next.className = 'page-btn';
            next.textContent = '>';
            next.addEventListener('click', () => {
                pageGroup += 1;
                currentPage = pageGroup * maxPageButtons + 1;
                render();
            });
            pagination.appendChild(next);
        }
    }

    headers.forEach((header) => {
        const actualIndex = header.cellIndex;
        header.dataset.colIndex = actualIndex;
        header.classList.add('none');

        header.addEventListener('click', () => {
            if (sortColumnIndex !== actualIndex) {
                sortColumnIndex = actualIndex;
                sortDirection = 'asc';
            } else if (sortDirection === 'asc') {
                sortDirection = 'desc';
            } else if (sortDirection === 'desc') {
                sortDirection = null;
                sortColumnIndex = null;
            } else {
                sortColumnIndex = actualIndex;
                sortDirection = 'asc';
            }

            updateHeaderState(sortColumnIndex === null ? null : header);
            render();
        });
    });

    searchInput?.addEventListener('input', applyFilters);

    return { render, applyFilters };
}

const requestStatusFilter = document.getElementById("requestStatusFilter");

const requestManager = createTableManager({
    tableId: "requestTable",
    paginationId: "requestPagination",
    searchInputId: "requestSearch",
    extraFilter: (row) => !requestStatusFilter.value || row.children[2]?.innerText.includes(requestStatusFilter.value)
});
requestStatusFilter.addEventListener("change", () => requestManager.applyFilters(true));

const inventoryManager = createTableManager({
    tableId: "inventoryTable",
    paginationId: "inventoryPagination",
    searchInputId: "inventorySearch"
});

const txManager = createTableManager({
    tableId: "txTable",
    paginationId: "txPagination",
    searchInputId: "txSearch"
});

requestManager.render();
inventoryManager.render();
txManager.render();

const detailModalOverlay = document.getElementById("detailModalOverlay");
const detailModalClose = document.getElementById("detailModalClose");
const detailTitle = document.getElementById("detailTitle");

let currentDetailType = null;
let currentDetailId = null;

function openModal() { detailModalOverlay.classList.add("show"); }
function closeModal() { detailModalOverlay.classList.remove("show"); }

detailModalClose.addEventListener("click", closeModal);
detailModalOverlay.addEventListener("click", (e) => {
    if (e.target === detailModalOverlay) closeModal();
});

function setValue(id, value) {
    const el = document.getElementById(id);
    if (el) el.value = value ?? "";
}

function setReadOnly(ids, value) {
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.readOnly = value;
    });
}

function toggleMode(type) {
    const editIds = [
        "detail_request_action", "detail_request_type", "detail_material_code", "detail_po_no", "detail_item_name",
        "detail_item_spec", "detail_grade", "detail_material_category", "detail_building_name", "detail_process_name",
        "detail_generation_name", "detail_module_name", "detail_quantity", "detail_requester", "detail_purchase_requester",
        "detail_vendor_name", "detail_inbound_type", "detail_purchase_type", "detail_usability_status",
        "detail_retention_period", "detail_project_name", "detail_actual_user", "detail_attachment_path",
        "detail_request_reason", "detail_admin_comment"
    ];

    if (type === "request") {
        setReadOnly(editIds, false);
        document.getElementById("detailSaveBtn").style.display = "";
        document.getElementById("detailLookupBtn").style.display = "";
        document.getElementById("inventoryUpdateRequestBtn").style.display = "none";
        document.getElementById("inventoryOutboundRequestBtn").style.display = "none";
    } else if (type === "inventory") {
        setReadOnly(editIds, false);
        document.getElementById("detailSaveBtn").style.display = "none";
        document.getElementById("detailLookupBtn").style.display = "";
        document.getElementById("inventoryUpdateRequestBtn").style.display = "";
        document.getElementById("inventoryOutboundRequestBtn").style.display = "";
    } else {
        setReadOnly(editIds, true);
        document.getElementById("detailSaveBtn").style.display = "none";
        document.getElementById("detailLookupBtn").style.display = "none";
        document.getElementById("inventoryUpdateRequestBtn").style.display = "none";
        document.getElementById("inventoryOutboundRequestBtn").style.display = "none";
    }
}

async function openDetail(type, id) {
    const endpoint = type === "request"
        ? `/api/request/${id}`
        : type === "inventory"
            ? `/api/inventory/${id}`
            : `/api/transaction/${id}`;

    const res = await fetch(endpoint);
    if (!res.ok) {
        alert("상세내역을 불러오지 못했습니다.");
        return;
    }

    const json = await res.json();
    const d = json.data;

    currentDetailType = type;
    currentDetailId = id;

    detailTitle.textContent =
        type === "request" ? "요청 상세내역" :
        type === "inventory" ? "보관 자재 상세내역" :
        "입출고 이력 상세내역";

    setValue("detail_id", d.id);
    setValue("detail_status", d.status || d.request_status || d.tx_status || d.storage_status || "");
    setValue("detail_request_action", d.request_action || "");
    setValue("detail_request_type", d.request_type || d.tx_type || "");
    setValue("detail_material_code", d.material_code);
    setValue("detail_po_no", d.po_no);
    setValue("detail_item_name", d.item_name);
    setValue("detail_item_spec", d.item_spec);
    setValue("detail_grade", d.grade);
    setValue("detail_material_category", d.material_category);
    setValue("detail_building_name", d.building_name);
    setValue("detail_process_name", d.process_name);
    setValue("detail_generation_name", d.generation_name);
    setValue("detail_module_name", d.module_name);
    setValue("detail_quantity", d.quantity);
    setValue("detail_requester", d.requester);
    setValue("detail_purchase_requester", d.purchase_requester);
    setValue("detail_vendor_name", d.vendor_name);
    setValue("detail_inbound_type", d.inbound_type);
    setValue("detail_purchase_type", d.purchase_type);
    setValue("detail_usability_status", d.usability_status);
    setValue("detail_retention_period", d.retention_period);
    setValue("detail_project_name", d.project_name);
    setValue("detail_actual_user", d.actual_user);
    setValue("detail_attachment_path", d.attachment_path);
    setValue("detail_request_reason", d.request_reason || d.note || "");
    setValue("detail_admin_comment", d.admin_comment || "");

    document.getElementById("detailCreatedAt").textContent = `등록일/처리일: ${d.created_at || "-"}`;
    document.getElementById("detailApprovedAt").textContent = `승인일/최종갱신일: ${d.approved_at || d.last_updated_at || "-"}`;

    const img = document.getElementById("detailImage");
    const empty = document.getElementById("detailImageEmpty");

    if (d.image_view_url) {
        img.src = d.image_view_url;
        img.style.display = "";
        empty.style.display = "none";
        img.onerror = () => {
            img.style.display = "none";
            empty.style.display = "";
        };
    } else {
        img.removeAttribute("src");
        img.style.display = "none";
        empty.style.display = "";
    }

    toggleMode(type);
    openModal();
}

document.querySelectorAll(".detail-row").forEach(row => {
    row.addEventListener("click", () => openDetail(row.dataset.detailType, row.dataset.detailId));
});

document.getElementById("detailLookupBtn").addEventListener("click", async () => {
    await lookupMaterial(document.getElementById("detail_material_code").value, "detail_");
});

document.getElementById("detailSaveBtn").addEventListener("click", async () => {
    if (currentDetailType !== "request" || !currentDetailId) return;
    if (!confirm("요청 내용을 수정 저장하시겠습니까?")) return;

    const payload = collectDetailPayload();
    const res = await fetch(`/api/request/${currentDetailId}/update`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    });
    const json = await res.json();
    if (!res.ok || !json.success) {
        alert(json.message || "저장에 실패했습니다.");
        return;
    }
    alert("요청 수정이 완료되었습니다.");
    location.reload();
});

document.getElementById("inventoryUpdateRequestBtn").addEventListener("click", async () => {
    if (currentDetailType !== "inventory" || !currentDetailId) return;
    if (!confirm("보관정보 수정 요청을 등록하시겠습니까? 승인 전까지 실제 데이터는 변경되지 않습니다.")) return;

    const payload = collectDetailPayload();
    const res = await fetch(`/api/inventory/${currentDetailId}/request-update`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    });
    const json = await res.json();
    if (!res.ok || !json.success) {
        alert(json.message || "수정 요청 등록에 실패했습니다.");
        return;
    }
    alert(json.message);
    closeModal();
    location.hash = "#request-status";
    location.reload();
});

document.getElementById("inventoryOutboundRequestBtn").addEventListener("click", async () => {
    if (currentDetailType !== "inventory" || !currentDetailId) return;
    if (!confirm("출고 의뢰를 등록하시겠습니까? 승인 전까지 실제 재고는 차감되지 않습니다.")) return;

    const payload = {
        quantity: document.getElementById("detail_quantity").value,
        requester: document.getElementById("detail_requester").value,
        purchase_requester: document.getElementById("detail_purchase_requester").value,
        vendor_name: document.getElementById("detail_vendor_name").value,
        request_reason: document.getElementById("detail_request_reason").value,
        purchase_type: document.getElementById("detail_purchase_type").value
    };

    const res = await fetch(`/api/inventory/${currentDetailId}/request-outbound`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    });
    const json = await res.json();
    if (!res.ok || !json.success) {
        alert(json.message || "출고 의뢰 등록에 실패했습니다.");
        return;
    }
    alert(json.message);
    closeModal();
    location.hash = "#request-status";
    location.reload();
});

function collectDetailPayload() {
    return {
        request_action: document.getElementById("detail_request_action").value,
        request_type: document.getElementById("detail_request_type").value,
        material_code: document.getElementById("detail_material_code").value,
        po_no: document.getElementById("detail_po_no").value,
        item_name: document.getElementById("detail_item_name").value,
        item_spec: document.getElementById("detail_item_spec").value,
        grade: document.getElementById("detail_grade").value,
        material_category: document.getElementById("detail_material_category").value,
        building_name: document.getElementById("detail_building_name").value,
        process_name: document.getElementById("detail_process_name").value,
        generation_name: document.getElementById("detail_generation_name").value,
        module_name: document.getElementById("detail_module_name").value,
        quantity: document.getElementById("detail_quantity").value,
        requester: document.getElementById("detail_requester").value,
        purchase_requester: document.getElementById("detail_purchase_requester").value,
        vendor_name: document.getElementById("detail_vendor_name").value,
        request_reason: document.getElementById("detail_request_reason").value,
        inbound_type: document.getElementById("detail_inbound_type").value,
        purchase_type: document.getElementById("detail_purchase_type").value,
        usability_status: document.getElementById("detail_usability_status").value,
        retention_period: document.getElementById("detail_retention_period").value,
        project_name: document.getElementById("detail_project_name").value,
        actual_user: document.getElementById("detail_actual_user").value,
        attachment_path: document.getElementById("detail_attachment_path").value,
        admin_comment: document.getElementById("detail_admin_comment").value,
        approval_type: "N/A"
    };
}

autoRetention();
