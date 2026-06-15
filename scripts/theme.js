(function () {
    var html = document.documentElement;

    var t = localStorage.getItem('theme');
    if (t) html.setAttribute('data-theme', t);

    function setTheme(theme) {
        if (html.getAttribute('data-theme') === theme) {
            html.removeAttribute('data-theme');
            localStorage.removeItem('theme');
        } else {
            html.setAttribute('data-theme', theme);
            localStorage.setItem('theme', theme);
        }
    }

    function makeBtn(id, label) {
        var btn = document.createElement('button');
        btn.id = id;
        btn.className = 'theme-toggle';
        btn.setAttribute('aria-label', label);
        return btn;
    }

    function init() {
        var darkBtn = document.getElementById('theme-toggle');
        var forestBtn = document.getElementById('forest-toggle');

        if (!darkBtn) {
            var wrap = document.createElement('div');
            wrap.className = 'theme-buttons';
            forestBtn = makeBtn('forest-toggle', 'Toggle forest theme');
            darkBtn = makeBtn('theme-toggle', 'Toggle dark mode');
            wrap.appendChild(forestBtn);
            wrap.appendChild(darkBtn);

            var backEl = document.querySelector('.back-link') || document.querySelector('.back');
            if (backEl) {
                var mb = window.getComputedStyle(backEl).marginBottom;
                var nav = document.createElement('div');
                nav.className = 'page-nav';
                nav.style.marginBottom = mb;
                backEl.style.marginBottom = '0';
                backEl.parentNode.insertBefore(nav, backEl);
                nav.appendChild(backEl);
                nav.appendChild(wrap);
            } else {
                wrap.classList.add('theme-buttons-fixed');
                document.body.appendChild(wrap);
            }
        }

        darkBtn.addEventListener('click', function () { setTheme('dark'); });
        if (forestBtn) forestBtn.addEventListener('click', function () { setTheme('forest'); });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
