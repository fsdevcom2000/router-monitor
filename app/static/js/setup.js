(function () {
    const form = document.getElementById('createUserForm');
    if (!form) return;

    form.addEventListener('submit', function (e) {
        const p1 = document.getElementById('password1').value;
        const p2 = document.getElementById('password2').value;

        if (p1 !== p2) {
            e.preventDefault();
            alert('Passwords do not match!');
            return;
        }

        if (p1.length < 3) {
            e.preventDefault();
            alert('Password must be at least 3 characters long!');
        }
    });
})();
