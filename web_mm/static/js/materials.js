function createTableManager({
    tableId,
    paginationId,
    searchInputId = null,
    extraFilter = null,
    pageSize = 10,
    maxPageButtons = 10
}) {
    const table = document.getElementById(tableId);
    const tbody = table.querySelector("tbody");
    const originalRows = Array.from(tbody.querySelectorAll("tr"));
    const pagination = document.getElementById(paginationId);
    const searchInput = searchInputId ? document.getElementById(searchInputId) : null;
    const headers = Array.from(table.querySelectorAll("thead th.sortable"));

    let filteredRows = [...originalRows];
    let currentPage = 1;
    let pageGroup = 0;
    let sortColumnIndex = null;
    let sortDirection = null; // null -> 원상태, asc, desc

    headers.forEach((header) => {
        header.dataset.colIndex = String(header.cellIndex);
        header.classList.add("none");
    });

    function getCellValue(row, index) {
        return (row.children[index]?.innerText || "").replace(/\s+/g, " ").trim();
    }

    function normalizeValue(value, type) {
        const raw = String(value ?? "").trim();

        if (type === "number") {
            const num = parseFloat(raw.replace(/[^0-9.\-]/g, ""));
            return Number.isNaN(num) ? 0 : num;
        }

        return raw.toLowerCase();
    }

    function getBaseRows() {
        const keyword = (searchInput?.value || "").toLowerCase().trim();

        return originalRows.filter((row) => {
            const text = row.innerText.toLowerCase();
            const keywordMatch = !keyword || text.includes(keyword);
            const extraMatch = typeof extraFilter === "function" ? extraFilter(row) : true;
            return keywordMatch && extraMatch;
        });
    }

    function sortRows(rows) {
        if (sortColumnIndex === null || sortDirection === null) {
            return [...rows];
        }

        const header = headers.find(
            (h) => Number(h.dataset.colIndex) === sortColumnIndex
        );
        const type = header?.dataset.sortType || "text";

        return [...rows].sort((a, b) => {
            const av = normalizeValue(getCellValue(a, sortColumnIndex), type);
            const bv = normalizeValue(getCellValue(b, sortColumnIndex), type);

            let cmp = 0;
            if (type === "number") {
                cmp = av - bv;
            } else {
                cmp = String(av).localeCompare(String(bv), "ko");
            }

            return sortDirection === "asc" ? cmp : -cmp;
        });
    }

    function updateHeaderState(activeHeader = null) {
        headers.forEach((h) => {
            h.classList.remove("asc", "desc", "none");
            h.classList.add("none");
        });

        if (!activeHeader || !sortDirection) {
            return;
        }

        activeHeader.classList.remove("none");
        activeHeader.classList.add(sortDirection);
    }

    function applyFilters() {
        const baseRows = getBaseRows();
        filteredRows = sortRows(baseRows);
        currentPage = 1;
        pageGroup = 0;
        render();
    }

    function render() {
        originalRows.forEach((row) => {
            row.style.display = "none";
        });

        const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
        if (currentPage > totalPages) currentPage = totalPages;

        const start = (currentPage - 1) * pageSize;
        const pageRows = filteredRows.slice(start, start + pageSize);

        pageRows.forEach((row) => {
            row.style.display = "";
        });

        renderPagination(totalPages);
    }

    function renderPagination(totalPages) {
        pagination.innerHTML = "";

        const startPage = pageGroup * maxPageButtons + 1;
        const endPage = Math.min(startPage + maxPageButtons - 1, totalPages);

        if (startPage > 1) {
            const prev = document.createElement("button");
            prev.className = "page-btn";
            prev.textContent = "<";
            prev.addEventListener("click", () => {
                pageGroup -= 1;
                currentPage = pageGroup * maxPageButtons + 1;
                render();
            });
            pagination.appendChild(prev);
        }

        for (let i = startPage; i <= endPage; i++) {
            const btn = document.createElement("button");
            btn.className = "page-btn" + (i === currentPage ? " active" : "");
            btn.textContent = `[${i}]`;
            btn.addEventListener("click", () => {
                currentPage = i;
                render();
            });
            pagination.appendChild(btn);
        }

        if (endPage < totalPages) {
            const next = document.createElement("button");
            next.className = "page-btn";
            next.textContent = ">";
            next.addEventListener("click", () => {
                pageGroup += 1;
                currentPage = pageGroup * maxPageButtons + 1;
                render();
            });
            pagination.appendChild(next);
        }
    }

    headers.forEach((header) => {
        header.addEventListener("click", () => {
            const actualIndex = Number(header.dataset.colIndex);

            if (sortColumnIndex !== actualIndex) {
                sortColumnIndex = actualIndex;
                sortDirection = "asc";
            } else if (sortDirection === "asc") {
                sortDirection = "desc";
            } else if (sortDirection === "desc") {
                sortDirection = null;
                sortColumnIndex = null;
            } else {
                sortColumnIndex = actualIndex;
                sortDirection = "asc";
            }

            updateHeaderState(sortColumnIndex === null ? null : header);
            applyFilters();
        });
    });

    searchInput?.addEventListener("input", applyFilters);

    return {
        render,
        applyFilters
    };
}