(function () {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');

    function applyTheme(e) {
        if (e.matches) {
            document.body.classList.add('dark-mode');
        } else {
            document.body.classList.remove('dark-mode');
        }
    }

    // first state
    applyTheme(mq);


    if (typeof mq.addEventListener === "function") {
        mq.addEventListener('change', applyTheme);
    } else {
        // fallback for old browser
        mq.addListener(applyTheme);
    }
})();
