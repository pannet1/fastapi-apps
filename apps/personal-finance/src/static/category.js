// static/category.js

async function updateCat(index, value) {
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

        if (response.ok) {
            location.reload();
        } else {
            alert("Error updating category.");
        }
    } catch (err) {
        alert("Network error updating category: " + err.message);
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
