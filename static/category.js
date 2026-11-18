// static/category.js

function showToast(message, type = "success") {
    let container = document.getElementById("pf-toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "pf-toast-container";
        container.className = "fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none";
        document.body.appendChild(container);
    }
    const toast = document.createElement("div");
    const isError = type === "error";
    toast.className = `px-4 py-2.5 rounded-xl border shadow-2xl text-xs font-semibold flex items-center gap-2 transform transition-all duration-300 translate-y-3 opacity-0 pointer-events-auto backdrop-blur-md ${
        isError ? "bg-rose-950/90 text-rose-200 border-rose-800" : "bg-slate-900/95 text-emerald-300 border-slate-700"
    }`;
    const icon = isError ? '<i class="fa-solid fa-circle-exclamation text-rose-400"></i>' : '<i class="fa-solid fa-circle-check text-emerald-400"></i>';
    toast.innerHTML = `${icon} <span>${message}</span>`;
    container.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.remove("translate-y-3", "opacity-0");
    });

    setTimeout(() => {
        toast.classList.add("opacity-0", "translate-y-3");
        setTimeout(() => toast.remove(), 300);
    }, 2800);
}

function updateTxCounters(countRemoved = 1) {
    const totalRowsNum = document.getElementById("tx-total-rows-num");
    if (totalRowsNum) {
        let current = parseInt(totalRowsNum.textContent.replace(/,/g, ""), 10);
        if (!isNaN(current)) {
            const nextVal = Math.max(0, current - countRemoved);
            totalRowsNum.textContent = nextVal.toLocaleString();
        }
    }
    const totalMatched = document.getElementById("tx-total-matched");
    if (totalMatched) {
        const match = totalMatched.textContent.replace(/,/g, "").match(/\d+/);
        if (match) {
            let current = parseInt(match[0], 10);
            const nextVal = Math.max(0, current - countRemoved);
            totalMatched.textContent = `(${nextVal.toLocaleString()} matched)`;
        }
    }
}

function removeTxRow(rowEl) {
    if (!rowEl) return;
    rowEl.style.transition = "opacity 0.22s ease-out, transform 0.22s ease-out";
    rowEl.style.opacity = "0";
    rowEl.style.transform = "translateX(25px)";
    setTimeout(() => {
        rowEl.remove();
        checkEmptyTxTable();
    }, 220);
}

function checkEmptyTxTable() {
    const tbody = document.getElementById("tx-tbody");
    if (!tbody) return;
    const remainingRows = tbody.querySelectorAll("tr[id^='tx-row-']");
    const noRow = document.getElementById("no-tx-row");
    if (remainingRows.length === 0 && noRow) {
        noRow.classList.remove("hidden");
        const cell = noRow.querySelector("td");
        if (cell) {
            cell.innerHTML = '<span class="inline-flex items-center gap-2 text-emerald-400 font-semibold"><i class="fa-solid fa-circle-check text-sm"></i> All transactions in this view have been classified!</span>';
        }
    }
}

async function updateCat(index, value, selectEl) {
    const rowEl = selectEl ? selectEl.closest("tr") : document.getElementById("tx-row-" + index);
    const prevCat = selectEl ? (selectEl.dataset.currentCat || "") : (rowEl ? rowEl.dataset.category : "");
    const urlParams = new URLSearchParams(window.location.search);
    const filterCat = urlParams.get("category");

    // "once uncategorized is allocated to a proper category envelope, it should immediately dissappear from the list"
    const isAllocatingUncategorized = (prevCat === "Uncategorized" || (rowEl && rowEl.dataset.category === "Uncategorized")) && (value !== "Uncategorized");
    const isLeavingFilterCategory = Boolean(filterCat && filterCat.toLowerCase() !== value.toLowerCase());
    const shouldDisappear = isAllocatingUncategorized || isLeavingFilterCategory;

    // Optimistically remove row from view immediately without full page reload
    if (shouldDisappear && rowEl) {
        removeTxRow(rowEl);
        updateTxCounters(1);
    } else if (selectEl) {
        selectEl.dataset.currentCat = value;
    }

    let formData = new FormData();
    formData.append("row_index", index);
    formData.append("category", value);

    const baseUrl = window.location.pathname.includes("/personal-finance") 
        ? "/personal-finance" 
        : "";

    try {
        const response = await fetch(`${baseUrl}/update-category`, {
            method: "POST",
            body: formData,
        });

        const data = await response.json().catch(() => ({}));

        if (response.ok && data.status === "success") {
            const updatedCount = data.updated_count || 1;
            const vendorMsg = data.vendor ? ` matching "${data.vendor}"` : "";
            showToast(`Allocated to ${value} (${updatedCount} transaction${updatedCount > 1 ? "s" : ""}${vendorMsg})`);

            // If other rows on the current page were updated forward and should also disappear
            if (Array.isArray(data.updated_indices) && data.updated_indices.length > 1) {
                let siblingRemovedCount = 0;
                data.updated_indices.forEach(idx => {
                    if (idx !== index) {
                        const siblingRow = document.getElementById("tx-row-" + idx);
                        if (siblingRow) {
                            if (shouldDisappear) {
                                removeTxRow(siblingRow);
                                siblingRemovedCount++;
                            } else {
                                const sel = siblingRow.querySelector("select");
                                if (sel) {
                                    sel.value = value;
                                    sel.dataset.currentCat = value;
                                }
                            }
                        }
                    }
                });
                if (siblingRemovedCount > 0) {
                    updateTxCounters(siblingRemovedCount);
                }
            }
        } else {
            showToast(data.message || "Error updating category.", "error");
            setTimeout(() => location.reload(), 1500);
        }
    } catch (err) {
        showToast("Network error: " + err.message, "error");
        setTimeout(() => location.reload(), 1500);
    }
}

// Global handler for the CSV upload form
async function handleUpload(event) {
    event.preventDefault();
    const fileInput = document.getElementById("csvFile");
    const status = document.getElementById("statusMessage");

    if (!fileInput || !fileInput.files[0]) {
        if (status) status.innerHTML = '<span class="text-rose-400 font-semibold">Please select a CSV file first.</span>';
        return;
    }

    let formData = new FormData();
    formData.append("file", fileInput.files[0]);

    if (status) {
        status.innerHTML = '<span class="text-amber-400 font-semibold"><i class="fa-solid fa-spinner fa-spin mr-1"></i> Parsing and merging transactions...</span>';
    }

    const baseUrl = window.location.pathname.includes("/personal-finance") 
        ? "/personal-finance" 
        : "";
    const uploadUrl = (event.target && event.target.getAttribute("action")) || `${baseUrl}/upload`;

    try {
        const response = await fetch(uploadUrl, {
            method: "POST",
            body: formData,
        });

        const data = await response.json().catch(() => ({}));

        if (response.ok) {
            const addedCount = data.added !== undefined ? data.added : (data.count || 0);
            const totalCount = data.total !== undefined ? ` (Total: ${data.total})` : "";
            if (status) {
                status.innerHTML = `<span class="text-emerald-400 font-bold"><i class="fa-solid fa-circle-check mr-1"></i> Successfully imported! ${addedCount} new transactions merged${totalCount}. Redirecting...</span>`;
            }
            setTimeout(() => {
                window.location.href = `${baseUrl}/transactions`;
            }, 1200);
        } else {
            const errMsg = data.detail || data.message || "Upload failed. Please check CSV format.";
            if (status) {
                status.innerHTML = `<span class="text-rose-400 font-bold"><i class="fa-solid fa-circle-xmark mr-1"></i> ${errMsg}</span>`;
            }
        }
    } catch (err) {
        if (status) {
            status.innerHTML = `<span class="text-rose-400 font-bold"><i class="fa-solid fa-circle-xmark mr-1"></i> Upload error: ${err.message}</span>`;
        }
    }
}
