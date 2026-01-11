
document.addEventListener("DOMContentLoaded", function() {
    const form = document.getElementById("edit-profile-form");
    const newPasswordField = document.getElementById("new_password");
    const confirmPasswordField = document.getElementById("confirm_password");
    const errorElement = document.getElementById("password-error");

    form.addEventListener("submit", function(event) {
        if (newPasswordField.value !== "" && newPasswordField.value !== confirmPasswordField.value) {
            
            event.preventDefault();
            errorElement.textContent = "كلمتا المرور غير متطابقتين.";
            errorElement.style.display = "block";
            confirmPasswordField.style.borderColor = "#e74c3c";
        } else {
            errorElement.style.display = "none";
            confirmPasswordField.style.borderColor = "#800080";
        }
    });
});