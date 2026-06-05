const form = document.getElementById("upload-form");
const fileInput = document.getElementById("file-input");

if (form && fileInput) {
  form.addEventListener("submit", () => {
    form.querySelector("button[type='submit']").textContent = "Uploading...";
  });
}
