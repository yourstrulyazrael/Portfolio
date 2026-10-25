(function () {
    var root = document.documentElement;
    var KEY = "portfolio-theme";
    var media = window.matchMedia("(prefers-color-scheme: dark)");

    function load() {
        try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { return {}; }
    }

    function save(prefs) {
        try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch (e) {  }
    }

    function sync() {
        document.querySelectorAll("[data-theme-mode]").forEach(function (input) {
            input.checked = input.value === root.dataset.mode;
        });
        document.querySelectorAll("[data-theme-accent]").forEach(function (input) {
            input.checked = input.value === root.dataset.accent;
        });
        document.querySelectorAll("[data-status-theme]").forEach(function (item) {
            item.textContent = root.dataset.mode + " · " + root.dataset.accent;
        });
    }

    function apply(mode, accent) {
        var dark = mode === "dark" || (mode === "system" && media.matches);
        root.setAttribute("data-bs-theme", dark ? "dark" : "light");
        root.dataset.mode = mode;
        root.dataset.accent = accent;
        sync();
    }

    document.addEventListener("change", function (event) {
        var input = event.target;
        var isMode = input.matches("[data-theme-mode]");
        if (!isMode && !input.matches("[data-theme-accent]")) return;

        var prefs = load();
        prefs[isMode ? "mode" : "accent"] = input.value;
        save(prefs);
        apply(prefs.mode || root.dataset.mode, prefs.accent || root.dataset.accent);
    });

    window.portfolioTheme = {
        accents: Array.prototype.map.call(document.querySelectorAll("[data-theme-accent]"), function (input) {
            return input.value;
        }).filter(function (value, index, all) { return all.indexOf(value) === index; }),
        get: function () { return { mode: root.dataset.mode, accent: root.dataset.accent }; },
        set: function (mode, accent) {
            var prefs = load();
            if (mode) prefs.mode = mode;
            if (accent) prefs.accent = accent;
            save(prefs);
            apply(prefs.mode || root.dataset.mode, prefs.accent || root.dataset.accent);
        }
    };

    media.addEventListener("change", function () {
        if (root.dataset.mode === "system") apply("system", root.dataset.accent);
    });

    window.addEventListener("storage", function (event) {
        if (event.key !== KEY) return;
        var prefs = load();
        apply(prefs.mode || root.dataset.defaultMode, prefs.accent || root.dataset.defaultAccent);
    });

    sync();
})();

document.addEventListener("keydown", function (event) {
    if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;
    var target = event.target;
    if (target.closest("input, textarea, select, [contenteditable]")) return;
    var search = document.getElementById("projectSearch") || document.getElementById("searchInput");
    if (!search) return;
    event.preventDefault();
    search.focus();
    search.select();
});

document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-copy]");
    if (!button) return;

    function copied() {
        button.classList.add("is-copied");
        clearTimeout(button._copiedTimer);
        button._copiedTimer = setTimeout(function () { button.classList.remove("is-copied"); }, 1500);
    }

    function selectFallback() {
        var value = button.parentElement.querySelector("code");
        if (!value) return;
        var range = document.createRange();
        range.selectNodeContents(value);
        var selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
    }

    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(button.dataset.copy).then(copied, selectFallback);
    } else {
        selectFallback();
    }
});

document.querySelectorAll("img[data-skeleton]").forEach(function (img) {
    var frame = img.closest(".skeleton-media");
    if (!frame) return;

    function done() {
        frame.classList.add("is-loaded");
        if (!img.naturalWidth) frame.classList.add("is-broken");
    }

    if (img.complete) {
        done();
    } else {
        img.addEventListener("load", done, { once: true });
        img.addEventListener("error", done, { once: true });
    }
});

(function () {
    var progress = document.getElementById("navProgress");
    var timer = null;

    function skeletonFor(url) {
        if (/^\/projects\/\d+/.test(url.pathname)) return "detail";
        if (/^\/(contact|login)|\/(add|edit)-/.test(url.pathname)) return "form";
        return "grid";
    }

    function start(url) {
        progress.classList.add("is-active");
        clearTimeout(timer);
        timer = setTimeout(function () {
            document.body.dataset.skeleton = skeletonFor(url);
            document.body.classList.add("is-navigating");
            window.scrollTo(0, 0);
        }, 150);
    }

    function reset() {
        clearTimeout(timer);
        document.body.classList.remove("is-navigating");
        progress.classList.remove("is-active");
        document.querySelectorAll("[data-original-html]").forEach(function (button) {
            button.innerHTML = button.dataset.originalHtml;
            button.removeAttribute("data-original-html");
            button.disabled = false;
        });
    }

    document.addEventListener("click", function (event) {
        if (event.defaultPrevented || event.button !== 0 ||
            event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

        var link = event.target.closest("a[href]");
        if (!link || link.hasAttribute("download") || (link.target && link.target !== "_self")) return;

        var url = new URL(link.href, location.href);
        if (url.origin !== location.origin) return;
        if (url.pathname === location.pathname && url.search === location.search) return;

        start(url);
    });

    document.addEventListener("submit", function (event) {
        if (event.defaultPrevented) return;

        var form = event.target;
        var button = event.submitter || form.querySelector("[type=submit]");

        if (form.method.toLowerCase() === "get") {
            start(new URL(form.action, location.href));
            return;
        }

        progress.classList.add("is-active");

        if (button && !button.classList.contains("search-submit")) {
            var label = button.dataset.loadingText;
            if (!label) {
                var hasFiles = Array.from(form.querySelectorAll("input[type=file]"))
                    .some(function (input) { return input.files.length > 0; });
                var text = button.textContent.trim().toLowerCase();
                label = hasFiles ? "Uploading..." :
                    text.startsWith("delete") ? "Deleting..." :
                        text.startsWith("login") || text.startsWith("sign in") ? "Signing in..." : "Saving...";
            }
            button.dataset.originalHtml = button.innerHTML;
            button.innerHTML = '<span class="btn-spinner" aria-hidden="true"></span>' + label;
            setTimeout(function () { button.disabled = true; }, 0);
        }
    });

    window.addEventListener("pageshow", function (event) {
        if (event.persisted) reset();
    });
})();

document.querySelectorAll("input[type=file][data-preview]").forEach(function (input) {
    var preview = document.getElementById(input.dataset.preview);
    var urls = [];

    input.addEventListener("change", function () {
        urls.forEach(URL.revokeObjectURL);
        urls = [];
        preview.replaceChildren();

        Array.from(input.files).forEach(function (file, index) {
            var item = document.createElement("div");
            item.className = "upload-preview-item";

            if (file.type.startsWith("image/")) {
                var url = URL.createObjectURL(file);
                urls.push(url);
                var img = document.createElement("img");
                img.src = url;
                img.alt = file.name;
                item.appendChild(img);
            } else {
                item.classList.add("is-file");
                item.textContent = file.name.split(".").pop().toUpperCase();
            }

            if (index === 0 && input.multiple) {
                var tag = document.createElement("span");
                tag.className = "upload-preview-tag";
                tag.textContent = "Cover";
                item.appendChild(tag);
            }

            preview.appendChild(item);
        });
    });
});

(function () {
    var dialog = document.getElementById("commandPalette");
    if (!dialog || typeof dialog.showModal !== "function") return;

    var input = document.getElementById("paletteInput");
    var list = document.getElementById("paletteList");
    var status = document.getElementById("paletteStatus");
    var isAdmin = document.body.hasAttribute("data-admin");
    var data = null;
    var loading = null;
    var shown = [];
    var active = 0;

    function go(url) { return function () { location.href = url; }; }

    function copy(text, label) {
        return function () {
            if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text);
            flashStatus(label + " copied");
        };
    }

    function flashStatus(text) {
        var toast = document.createElement("div");
        toast.className = "palette-toast";
        toast.setAttribute("role", "status");
        toast.textContent = text;
        document.body.appendChild(toast);
        setTimeout(function () { toast.remove(); }, 1800);
    }

    function baseItems() {
        var items = [];
        var theme = window.portfolioTheme;
        if (theme) {
            [["light", "Light"], ["dark", "Dark"], ["system", "System"]].forEach(function (mode) {
                items.push({ group: "Theme", label: "Theme: " + mode[1], hint: "appearance",
                    run: function () { theme.set(mode[0]); } });
            });
            theme.accents.forEach(function (accent) {
                items.push({ group: "Theme", label: "Accent: " + accent, hint: "colour",
                    run: function () { theme.set(null, accent); } });
            });
        }
        items.push({ group: "Actions", label: "Copy link to this page", hint: "share", run: copy(location.href, "Link") });
        if (isAdmin) {
            [["Dashboard", "/admin"], ["Add project", "/admin/add-project"], ["Messages", "/admin/messages"],
             ["Profile & CV", "/admin/profile"], ["Add testimonial", "/admin/add-testimonial"]].forEach(function (entry) {
                items.push({ group: "Admin", label: entry[0], hint: entry[1], run: go(entry[1]) });
            });
        }
        return items;
    }

    function dataItems() {
        if (!data) return [];
        var items = [];
        data.pages.forEach(function (page) {
            items.push({ group: "Go to", label: page.title, hint: page.file, run: go(page.url) });
        });
        data.projects.forEach(function (project) {
            items.push({ group: "Projects", label: project.title, hint: project.technologies.join(", ") || "project",
                keywords: project.description, run: go(project.url) });
            if (project.live_url) {
                items.push({ group: "Projects", label: "Live demo: " + project.title, hint: "opens in a new tab",
                    run: function () { window.open(project.live_url, "_blank", "noopener"); } });
            }
        });
        var profile = data.profile;
        Object.keys(profile.links).forEach(function (key) {
            items.push({ group: "Links", label: key.charAt(0).toUpperCase() + key.slice(1), hint: profile.links[key],
                run: function () { window.open(profile.links[key], "_blank", "noopener"); } });
        });
        if (profile.email) items.push({ group: "Links", label: "Copy email address", hint: profile.email, run: copy(profile.email, "Email") });
        if (profile.cv) items.push({ group: "Links", label: "Download CV", hint: "PDF", run: go(profile.cv + "?download=1") });
        return items;
    }

    function score(text, query) {
        text = text.toLowerCase();
        var position = -1, total = 0, streak = 0;
        for (var i = 0; i < query.length; i++) {
            var found = text.indexOf(query[i], position + 1);
            if (found === -1) return -1;
            streak = found === position + 1 ? streak + 1 : 0;
            total += 10 - Math.min(found, 9) + streak * 3;
            position = found;
        }
        var exact = text.indexOf(query);
        if (exact === 0) total += 60;
        else if (exact > 0) total += 40;
        return total;
    }

    function render() {
        var query = input.value.trim().toLowerCase();
        var items = dataItems().concat(baseItems());

        if (query) {
            items = items.map(function (item) {
                var best = Math.max(score(item.label, query), score(item.group + " " + item.label, query) - 5,
                    item.keywords ? score(item.keywords, query) - 20 : -1);
                return { item: item, score: best };
            }).filter(function (entry) { return entry.score >= 0; })
              .sort(function (a, b) { return b.score - a.score; })
              .map(function (entry) { return entry.item; });
        }
        shown = items.slice(0, 40);
        active = 0;

        list.replaceChildren();
        var lastGroup = null;
        shown.forEach(function (item, index) {
            if (!query && item.group !== lastGroup) {
                var heading = document.createElement("li");
                heading.className = "palette-group";
                heading.setAttribute("role", "presentation");
                heading.textContent = item.group;
                list.appendChild(heading);
                lastGroup = item.group;
            }
            var option = document.createElement("li");
            option.id = "palette-option-" + index;
            option.className = "palette-option";
            option.setAttribute("role", "option");
            var label = document.createElement("span");
            label.className = "palette-label";
            label.textContent = item.label;
            var hint = document.createElement("span");
            hint.className = "palette-hint-text";
            hint.textContent = item.hint || "";
            option.append(label, hint);
            option.addEventListener("mousemove", function () { if (active !== index) setActive(index); });
            option.addEventListener("click", function () { run(index); });
            list.appendChild(option);
        });

        if (!shown.length) {
            var empty = document.createElement("li");
            empty.className = "palette-empty";
            empty.setAttribute("role", "presentation");
            empty.textContent = loading && !data ? "Loading..." : "No matches";
            list.appendChild(empty);
        }
        setActive(0);
        status.textContent = shown.length + " result" + (shown.length === 1 ? "" : "s");
    }

    function setActive(index) {
        var options = list.querySelectorAll("[role=option]");
        if (!options.length) { input.removeAttribute("aria-activedescendant"); return; }
        active = (index + options.length) % options.length;
        options.forEach(function (option, i) { option.setAttribute("aria-selected", String(i === active)); });
        input.setAttribute("aria-activedescendant", options[active].id);
        options[active].scrollIntoView({ block: "nearest" });
    }

    function run(index) {
        var item = shown[index];
        if (!item) return;
        dialog.close();
        item.run();
    }

    function open() {
        var explorer = document.getElementById("explorer");
        if (explorer && window.bootstrap && explorer.classList.contains("show")) {
            bootstrap.Offcanvas.getOrCreateInstance(explorer).hide();
        }
        if (dialog.open) return;
        input.value = "";
        render();
        dialog.showModal();
        input.focus();
        if (!data && !loading) {
            loading = fetch(dialog.dataset.source, { headers: { Accept: "application/json" } })
                .then(function (response) { return response.json(); })
                .then(function (json) { data = json; if (dialog.open) render(); })
                .catch(function () { loading = null; });
        }
    }

    input.addEventListener("input", render);
    input.addEventListener("keydown", function (event) {
        if (event.key === "ArrowDown") { event.preventDefault(); setActive(active + 1); }
        else if (event.key === "ArrowUp") { event.preventDefault(); setActive(active - 1); }
        else if (event.key === "Enter") { event.preventDefault(); run(active); }
    });

    dialog.addEventListener("click", function (event) {
        if (event.target === dialog) dialog.close();
    });

    document.addEventListener("keydown", function (event) {
        if ((event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === "k") {
            event.preventDefault();
            dialog.open ? dialog.close() : open();
        }
    });

    document.querySelectorAll("[data-open-palette]").forEach(function (button) {
        button.addEventListener("click", open);
    });
})();
