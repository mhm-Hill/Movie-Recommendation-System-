document.addEventListener("DOMContentLoaded", function () {
    const forms = document.querySelectorAll(".rating-form");

    forms.forEach(form => {
        form.addEventListener("submit", function (e) {
            e.preventDefault(); 

            const select = form.querySelector("select");
            const button = form.querySelector("button");
            const feedbackEl = form.querySelector(".rating-feedback");

            
            feedbackEl.textContent = "";
            feedbackEl.className = "rating-feedback";
            select.style.border = "1px solid #800080";

            
            if (select.value === "") {
                select.style.border = "2px solid #e74c3c";
                feedbackEl.textContent = "يرجى اختيار تقييم أولاً.";
                feedbackEl.classList.add("error");
                return;
            }

            

            const formData = new FormData(form);
            
            const urlEncodedData = new URLSearchParams(formData).toString();
            const actionURL = form.getAttribute("action");

            
            button.disabled = true;
            button.textContent = "جاري الإرسال...";

            fetch(actionURL, {
                method: 'POST',
                
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                
                body: urlEncodedData
            })
            
            .then(response => {
                if (response.ok) {
                    return response.text();
                }
                throw new Error('فشل الاتصال بالخادم. يرجى المحاولة مرة أخرى.');
            })
            .then(data => {
                feedbackEl.textContent = "شكراً لتقييمك!";
                feedbackEl.classList.add("success");
                select.disabled = true;
                button.textContent = "تم التقييم";
            })
            .catch(error => {
                feedbackEl.textContent = error.message;
                feedbackEl.classList.add("error");
                button.disabled = false;
                button.textContent = "إرسال التقييم";
            });
        });
    });
});