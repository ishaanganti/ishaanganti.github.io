(function () {
    function build() {
        var article = document.querySelector('article');
        if (!article) return;
        var headings = article.querySelectorAll('h2[id]');
        if (headings.length < 2) return;

        var aside = document.createElement('aside');
        aside.className = 'toc';
        var nav = document.createElement('nav');
        nav.setAttribute('aria-label', 'Contents');
        var ul = document.createElement('ul');

        var links = [];
        headings.forEach(function (h) {
            var li = document.createElement('li');
            li.className = 'toc-' + h.tagName.toLowerCase();
            var a = document.createElement('a');
            a.href = '#' + h.id;
            a.textContent = h.textContent.trim();
            li.appendChild(a);
            ul.appendChild(li);
            links.push({ id: h.id, a: a, h: h });
        });

        nav.appendChild(ul);
        aside.appendChild(nav);
        var page = document.querySelector('.page');
        if (page) page.insertBefore(aside, page.firstChild); else document.body.appendChild(aside);

        function setActive(id) {
            links.forEach(function (l) {
                if (l.id === id) l.a.classList.add('active');
                else l.a.classList.remove('active');
            });
        }

        var visible = new Set();
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (e) {
                if (e.isIntersecting) visible.add(e.target); else visible.delete(e.target);
            });
            if (visible.size) {
                var arr = Array.from(visible).sort(function (a, b) {
                    return a.getBoundingClientRect().top - b.getBoundingClientRect().top;
                });
                setActive(arr[0].id);
            } else {
                // nothing intersecting the middle band — pick the last heading above viewport
                var scrollY = window.scrollY;
                var last = null;
                links.forEach(function (l) {
                    if (l.h.getBoundingClientRect().top + scrollY <= scrollY + 120) last = l;
                });
                if (last) setActive(last.id);
            }
        }, { rootMargin: '-100px 0px -60% 0px', threshold: 0 });

        headings.forEach(function (h) { observer.observe(h); });

        links.forEach(function (l) {
            l.a.addEventListener('click', function () { setActive(l.id); });
        });

        if (links.length) setActive(links[0].id);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', build);
    } else {
        build();
    }
})();
