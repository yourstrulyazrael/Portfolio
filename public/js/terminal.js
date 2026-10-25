(function () {
    var terminal = document.getElementById("terminal");
    if (!terminal) return;

    var form = document.getElementById("terminalForm");
    var input = document.getElementById("terminalInput");
    var log = document.getElementById("terminalLog");
    var scroller = document.getElementById("terminalScroll");
    var history = [];
    var historyIndex = 0;
    var data = null;

    var ready = fetch(terminal.dataset.source, { headers: { Accept: "application/json" } })
        .then(function (response) { return response.json(); })
        .then(function (json) { data = json; })
        .catch(function () { data = null; });

    function line(parts, className) {
        var row = document.createElement("div");
        row.className = "term-line" + (className ? " " + className : "");
        (Array.isArray(parts) ? parts : [parts]).forEach(function (part) {
            if (part == null) return;
            row.appendChild(typeof part === "string" ? document.createTextNode(part) : part);
        });
        log.appendChild(row);
        return row;
    }

    function link(text, href, external) {
        var a = document.createElement("a");
        a.textContent = text;
        a.href = href;
        if (external) { a.target = "_blank"; a.rel = "noopener noreferrer"; }
        return a;
    }

    function span(text, className) {
        var el = document.createElement("span");
        el.className = className;
        el.textContent = text;
        return el;
    }

    function echoCommand(text) {
        line([span("james@portfolio", "prompt"), ":", span("~", "prompt-path"), "$ " + text], "term-echo");
    }

    function error(text) { line(text, "term-error"); }

    function pageUrl(name) {
        var page = (data ? data.pages : []).filter(function (p) {
            return p.title.toLowerCase() === name || p.file.toLowerCase().replace(/\/$/, "") === name;
        })[0];
        return page && page.url;
    }

    function findProject(arg) {
        if (!data || !arg) return null;
        var projects = data.projects;
        var n = parseInt(arg, 10);
        if (String(n) === arg && projects[n - 1]) return projects[n - 1];
        arg = arg.toLowerCase();
        return projects.filter(function (p) { return p.title.toLowerCase() === arg; })[0] ||
            projects.filter(function (p) { return p.title.toLowerCase().indexOf(arg) > -1; })[0] || null;
    }

    function navigate(url, label) {
        line(["Opening " + label + "..."], "term-muted");
        setTimeout(function () { location.href = url; }, 350);
    }

    var commands = {
        help: {
            about: "list commands",
            run: function () {
                Object.keys(commands).forEach(function (name) {
                    if (commands[name].hidden) return;
                    line([span(name.padEnd(10), "hl"), commands[name].about]);
                });
                line("Tip: Tab completes, ↑/↓ browse history. Ctrl+K opens the command palette.", "term-muted");
            }
        },
        whoami: {
            about: "who I am",
            run: function () {
                var p = data.profile;
                line(p.name + " · " + p.headline);
                if (p.location) line("Based in " + p.location, "term-muted");
                if (p.availability) line(["Status: ", span(p.availability, "hl")]);
                line(["More: ", link("about.md", pageUrl("about"))]);
            }
        },
        ls: {
            about: "list files (try: ls projects)",
            run: function (args) {
                var target = (args[0] || "").replace(/\/$/, "").toLowerCase();
                if (target === "projects") return commands.projects.run();
                if (target === "skills" || target === "skills.json") return commands.skills.run();
                if (target) return error("ls: cannot access '" + args[0] + "': No such file or directory");
                line(data.pages.map(function (p) { return p.file; }).join("   "));
            }
        },
        projects: {
            about: "list my projects",
            run: function () {
                if (!data.projects.length) return line("No projects yet.", "term-muted");
                data.projects.forEach(function (project, index) {
                    line([span(String(index + 1).padStart(2) + "  ", "term-muted"), link(project.title, project.url),
                        project.technologies.length ? span("  [" + project.technologies.join(", ") + "]", "term-muted") : null]);
                });
                line("Open one with: open <number or name>", "term-muted");
            }
        },
        skills: {
            about: "what I work with",
            run: function () {
                var groups = Object.keys(data.skills);
                if (!groups.length) return line("Still learning... check back soon.", "term-muted");
                groups.forEach(function (group) {
                    line([span(group + ": ", "hl"), data.skills[group].join(", ")]);
                });
            }
        },
        open: {
            about: "open a page or project (open 1, open contact)",
            run: function (args) {
                var arg = args.join(" ").toLowerCase();
                if (!arg) return error("usage: open <project number | project name | page>");
                var url = pageUrl(arg);
                if (url) return navigate(url, arg);
                var project = findProject(arg);
                if (project) return navigate(project.url, project.title);
                error("open: nothing called '" + arg + "'. Try 'projects' or 'ls'.");
            }
        },
        cd: {
            about: "go to a page (cd projects)",
            run: function (args) {
                var arg = (args[0] || "~").replace(/\/$/, "").toLowerCase();
                if (arg === "~" || arg === "/" || arg === "..") return line("You're already home.", "term-muted");
                var url = pageUrl(arg);
                url ? navigate(url, arg) : error("cd: no such directory: " + args[0]);
            }
        },
        contact: {
            about: "how to reach me",
            run: function () {
                var p = data.profile;
                if (p.email) line(["email     ", link(p.email, "mailto:" + p.email)]);
                Object.keys(p.links).forEach(function (key) {
                    line([key.padEnd(10), link(p.links[key], p.links[key], true)]);
                });
                line(["message   ", link("contact.sh", pageUrl("contact"))]);
            }
        },
        cv: {
            about: "download my CV",
            run: function () {
                if (!data.profile.cv) return line("The CV isn't uploaded yet. Try 'contact' instead.", "term-muted");
                line(["Downloading... ", link("or view it here", data.profile.cv, true)]);
                location.href = data.profile.cv + "?download=1";
            }
        },
        theme: {
            about: "light | dark | system",
            run: function (args) {
                var mode = (args[0] || "").toLowerCase();
                if (["light", "dark", "system"].indexOf(mode) === -1) {
                    return line("usage: theme light | dark | system   (now: " + window.portfolioTheme.get().mode + ")", "term-muted");
                }
                window.portfolioTheme.set(mode);
                line("Theme set to " + mode + ".");
            }
        },
        accent: {
            about: "change the accent colour",
            run: function (args) {
                var accents = window.portfolioTheme.accents;
                var accent = (args[0] || "").toLowerCase();
                if (accents.indexOf(accent) === -1) {
                    return line("usage: accent " + accents.join(" | ") + "   (now: " + window.portfolioTheme.get().accent + ")", "term-muted");
                }
                window.portfolioTheme.set(null, accent);
                line("Accent set to " + accent + ".");
            }
        },
        clear: { about: "clear the screen", run: function () {
            log.replaceChildren();
            terminal.querySelector(".terminal-intro").hidden = true;
        } },
        history: { about: "show previous commands", run: function () {
            history.forEach(function (cmd, i) { line([span(String(i + 1).padStart(3) + "  ", "term-muted"), cmd]); });
        } },
        date: { about: "print the date", run: function () { line(new Date().toString()); } },
        echo: { hidden: true, run: function (args) { line(args.join(" ")); } },
        sudo: { hidden: true, run: function () { error("james is not in the sudoers file. This incident will be reported."); } },
        rm: { hidden: true, run: function () { error("rm: permission denied. Nice try, though."); } },
        exit: { hidden: true, run: function () { line("There's no escape. Type 'help' instead.", "term-muted"); } },
        vim: { hidden: true, run: function () { line("You're stuck now. (Just kidding: :q works everywhere but here.)", "term-muted"); } },
        cat: {
            hidden: true,
            run: function (args) {
                var file = (args[0] || "").toLowerCase();
                if (file === "skills.json") return commands.skills.run();
                if (file === "about.md" || file === "readme.md") return commands.whoami.run();
                var url = pageUrl(file);
                url ? navigate(url, file) : error("cat: " + (args[0] || "") + ": No such file or directory");
            }
        }
    };
    commands.about = commands.whoami;
    commands.about.hidden = false;

    function execute(text) {
        echoCommand(text);
        var words = text.trim().split(/\s+/);
        var name = words[0].toLowerCase();
        var command = commands[name];
        if (!command) {
            error(name + ": command not found. Type 'help' for a list.");
            return;
        }
        if (!data) {
            error("Couldn't load the site data. Check your connection and try again.");
            return;
        }
        command.run(words.slice(1));
    }

    form.addEventListener("submit", function (event) {
        event.preventDefault();
        var text = input.value.trim();
        input.value = "";
        if (!text) return;
        history.push(text);
        historyIndex = history.length;
        ready.then(function () {
            execute(text);
            scroller.scrollTop = scroller.scrollHeight;
        });
    });

    input.addEventListener("keydown", function (event) {
        if (event.key === "ArrowUp" && history.length) {
            event.preventDefault();
            historyIndex = Math.max(0, historyIndex - 1);
            input.value = history[historyIndex];
        } else if (event.key === "ArrowDown" && history.length) {
            event.preventDefault();
            historyIndex = Math.min(history.length, historyIndex + 1);
            input.value = history[historyIndex] || "";
        } else if (event.key === "Tab" && input.value && input.value.indexOf(" ") === -1) {
            var matches = Object.keys(commands).filter(function (name) {
                return !commands[name].hidden && name.indexOf(input.value.toLowerCase()) === 0;
            });
            if (matches.length === 1) {
                event.preventDefault();
                input.value = matches[0] + " ";
            } else if (matches.length > 1) {
                event.preventDefault();
                line(matches.join("   "), "term-muted");
                scroller.scrollTop = scroller.scrollHeight;
            }
        } else if (event.key === "l" && event.ctrlKey) {
            event.preventDefault();
            commands.clear.run();
        }
    });

    terminal.addEventListener("click", function (event) {
        if (event.target.closest("a") || String(window.getSelection())) return;
        input.focus({ preventScroll: true });
    });
})();
