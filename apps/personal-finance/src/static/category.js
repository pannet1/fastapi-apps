// static/category.js

async function updateCat(index, value) {
    let formData = new FormData();
    formData.append("row_index", index);
    formData.append("category", value);

    const response = await fetch("/update-category", {
        method: "POST",
        body: formData,
    });

    if (response.ok) {
        location.reload();
    } else {
        alert("Error updating category.");
    }
}

// Global handler for the CSV upload form
async function handleUpload(event) {
    event.preventDefault();
    const fileInput = document.getElementById("csvFile");
    const status = document.getElementById("statusMessage");

    if (!fileInput.files[0]) return;

    let formData = new FormData();
    formData.append("file", fileInput.files[0]);

    status.innerHTML = "Processing...";

    const response = await fetch("/upload", {
        method: "POST",
        body: formData,
    });

    if (response.ok) {
        status.innerHTML = '<span class="text-success">Master updated!</span>';
        setTimeout(() => location.reload(), 1000);
    } else {
        status.innerHTML = '<span class="text-danger">Upload failed.</span>';
    }
}
