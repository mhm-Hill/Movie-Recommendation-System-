function validateForm() {
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value.trim();
    const errorMsg = document.getElementById("error-msg");

    if (email === "" || password === "") {
        errorMsg.textContent = "يرجى تعبئة جميع الحقول.";
        errorMsg.style.display = "block";
        return false;
    }

    if (password.length < 4) {
        errorMsg.textContent = "كلمة المرور يجب أن تكون 4 أحرف على الأقل.";
        errorMsg.style.display = "block";
        return false;
    }

    errorMsg.style.display = "none";
    return true;
}
