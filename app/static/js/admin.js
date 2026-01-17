// static/js/admin.js
import { alertModal, confirmModal } from "./modal.js";
import { showToast } from "./toast.js";

//Delete router confirmation /templates/admin_routers.html
document.querySelectorAll(".delete-router-form").forEach(form => {
    const btn = form.querySelector("button");

    btn.addEventListener("click", async e => {
        e.preventDefault();

        const routerName = btn.dataset.router;

        const ok = await confirmModal(`Delete ${routerName}?`, "Confirmation");

        if (ok) {
            form.submit();
        }

    });
});


//Delete user confirmation /templates/admin_users.html
document.querySelectorAll(".delete-user-form").forEach(form => {
    const btn = form.querySelector("button");

    btn.addEventListener("click", async e => {
        e.preventDefault();

        const userName = btn.dataset.user;

        const ok = await confirmModal(`Delete ${userName}?`, "Confirmation");

        if (ok) {
            form.submit();
        }

    });
});


//Check if device with name exist /templates/admin_router_form.html
document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("routerForm");

    if (!form) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const formData = new FormData(form);

        const response = await fetch(window.location.pathname, {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            const data = await response.json();
            showToast(data.error, "error");

            return;
        }

        window.location.href = "/admin/routers";
    });
});


//Check if user with name exist /templates/admin_user_form.html
document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("userForm");

    if (!form) return;

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const formData = new FormData(form);

        const response = await fetch(window.location.pathname, {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            const data = await response.json();
            showToast(data.error, "error");
            return;
        }

        window.location.href = "/admin/users";
    });
});

