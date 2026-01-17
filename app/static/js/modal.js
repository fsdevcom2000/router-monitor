// static/js/modal.js

function createModal({ title, message, buttons }) {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";

    const modal = document.createElement("div");
    modal.className = "modal";

    if (title) {
        const h = document.createElement("h3");
        h.textContent = title;
        modal.appendChild(h);
    }

    const p = document.createElement("p");
    p.textContent = message;
    modal.appendChild(p);

    const actions = document.createElement("div");
    actions.className = "modal-actions";

    let modalResolve;

    buttons.forEach(({ text, value, className }) => {
        const btn = document.createElement("button");
        btn.textContent = text;
        btn.className = className;
        btn.onclick = () => {
            // старт анимации скрытия
            overlay.classList.remove("show");
            modal.classList.remove("show");

            // удаляем после анимации
            setTimeout(() => overlay.remove(), 300);

            modalResolve(value);
        };
        actions.appendChild(btn);
    });

    modal.appendChild(actions);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // запускаем анимацию появления
    requestAnimationFrame(() => {
        overlay.classList.add("show");
        modal.classList.add("show");
    });

    return new Promise(resolve => {
        modalResolve = resolve;
    });
}

/* ===== EXPORT API ===== */

export function alertModal(message, title = "Routers") {
    return createModal({
        title,
        message,
        buttons: [
            { text: "OK", value: true, className: "btn-primary" }
        ]
    });
}

export function confirmModal(message, title = "Routers") {
    return createModal({
        title,
        message,
        buttons: [
            { text: "No", value: false, className: "btn-secondary" },
            { text: "Yes", value: true, className: "btn-yes" }
        ]
    });
}
