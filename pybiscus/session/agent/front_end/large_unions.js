// Unions with too many options for the options column (class pybiscus-tab-large, set by
// pydantic2html). The user chooses their representation with the setting next to the theme
// buttons: "chips" (selected option + a few alternatives, "+N" opening the radial menu, or a
// grouped list from the keyboard), "radial" (one trigger opening the radial menu) or "column".
// Every representation only clicks the original tab buttons: the page's own tab logic keeps
// data-pybiscus-status up to date, which is what traverseDOM reads to build the YAML.
window.pybiscusLargeUnions = (() => {

    const MODES = ["chips", "radial", "column"];
    const MODE_KEY = "pybiscus-large-union-mode";
    const MAX_ALTERNATIVES = 3;
    const OTHER = "Other";
    const HUES = [210, 280, 25, 145, 340, 55, 185];
    const CENTER_R = 52, GAP = 14;

    // ------------------------------------------------------------------ storage

    function storedMode() {
        try {
            const mode = localStorage.getItem(MODE_KEY);
            return MODES.includes(mode) ? mode : "chips";
        } catch (e) {
            return "chips";
        }
    }
    function storeMode(mode) {
        try { localStorage.setItem(MODE_KEY, mode); } catch (e) { /* not persisted: still applied */ }
    }
    function recentKey(container) {
        const fieldset = container.closest("[data-pybiscus-prefix]");
        return "pybiscus-recent-" + (fieldset ? fieldset.getAttribute("data-pybiscus-prefix") : "union");
    }
    function readRecent(container) {
        try { return JSON.parse(localStorage.getItem(recentKey(container)) || "[]"); } catch (e) { return []; }
    }
    function pushRecent(container, label) {
        try {
            const recent = [label, ...readRecent(container).filter(l => l !== label)].slice(0, 6);
            localStorage.setItem(recentKey(container), JSON.stringify(recent));
        } catch (e) { /* no history: same-family alternatives are still shown */ }
    }

    // ------------------------------------------------------------------ model

    function model(container) {
        const buttons = [...container.querySelectorAll(":scope > .pybiscus-tab-buttons > .pybiscus-tab-button")];
        const labels = buttons.map(b => b.textContent.trim());
        const groupOf = buttons.map(b => b.dataset.pybiscusGroup || OTHER);
        const families = [];
        groupOf.forEach((name, i) => {
            let family = families.find(f => f.name === name);
            if (!family) {
                family = { name, hue: HUES[families.length % HUES.length], members: [] };
                families.push(family);
            }
            family.members.push(labels[i]);
        });
        // the page activates a clicked tab only after its 600 ms switch: remember the request
        // so that the representation shows the choice at once
        let requested = null;
        const selectedIndex = () => {
            if (requested !== null && !buttons[requested].classList.contains("active")) {
                return requested;
            }
            requested = null;
            return buttons.findIndex(b => b.classList.contains("active"));
        };
        return {
            buttons, labels, families,
            familyOf: label => families.find(f => f.members.includes(label)),
            selectedLabel: () => labels[selectedIndex()],
            select: label => {
                const i = labels.indexOf(label);
                if (i < 0 || i === selectedIndex()) {
                    return;
                }
                pushRecent(container, labels[selectedIndex()]);
                requested = i;
                buttons[i].click();
            },
        };
    }

    // ------------------------------------------------------------------ small builders

    function el(tag, className, text) {
        const e = document.createElement(tag);
        if (className) e.className = className;
        if (text !== undefined) e.textContent = text;
        return e;
    }
    function coloured(e, hue) {
        e.style.setProperty("--lu-hue", hue);
        return e;
    }
    function optionButton(label, family, extraClass, onClick) {
        const b = coloured(el("button", "pybiscus-lu-chip " + (extraClass || ""), label), family.hue);
        b.type = "button";
        b.title = family.name;
        b.addEventListener("click", onClick);
        return b;
    }

    // ------------------------------------------------------------------ grouped list (keyboard)

    function openList(m, anchor, onClose) {
        const list = el("div", "pybiscus-lu-list");
        list.setAttribute("role", "dialog");
        const current = m.selectedLabel();
        const close = () => { list.remove(); document.removeEventListener("keydown", onKey); onClose && onClose(); };
        const onKey = e => { if (e.key === "Escape") { close(); anchor.focus(); } };
        m.families.forEach(f => {
            const group = coloured(el("div", "pybiscus-lu-group"), f.hue);
            group.append(el("div", "pybiscus-lu-group-title", f.name));
            f.members.forEach(l => group.append(
                optionButton(l, f, l === current ? "selected" : "", () => { m.select(l); close(); anchor.focus(); })));
            list.append(group);
        });
        anchor.after(list);
        document.addEventListener("keydown", onKey);
        (list.querySelector(".selected") || list.querySelector("button")).focus();
        return close;
    }

    // ------------------------------------------------------------------ radial menu

    const polar = (cx, cy, r, deg) => {
        const a = (deg - 90) * Math.PI / 180;
        return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
    };
    // extent of a w×h box along the radius / the tangent of a direction (degrees, clockwise from up)
    const radialHalf = (w, h, deg) => { const a = deg * Math.PI / 180; return Math.abs(Math.sin(a)) * w / 2 + Math.abs(Math.cos(a)) * h / 2; };
    const tangentExtent = (w, h, deg) => { const a = deg * Math.PI / 180; return Math.abs(Math.cos(a)) * w + Math.abs(Math.sin(a)) * h; };
    const place = (e, x, y) => { e.style.left = x + "px"; e.style.top = y + "px"; return e; };

    function spoke(overlay, x1, y1, x2, y2, hue) {
        const s = coloured(el("div", "pybiscus-lu-spoke"), hue);
        s.style.width = Math.hypot(x2 - x1, y2 - y1) + "px";
        s.style.transform = `rotate(${Math.atan2(y2 - y1, x2 - x1)}rad)`;
        overlay.append(place(s, x1, y1));
        return s;
    }
    function bubble(label, extraClass, hue) {
        const b = coloured(el("button", "pybiscus-lu-bubble " + extraClass, label), hue);
        b.type = "button";
        return b;
    }

    // members of one arc, spaced by their extents along the tangent, around angle `mid`
    function arc(bubbles, mid, radius) {
        const ext = bubbles.map(b => tangentExtent(b.offsetWidth, b.offsetHeight, mid));
        const steps = ext.slice(1).map((e, k) => ((ext[k] + e) / 2 + 12) / radius * 180 / Math.PI);
        const total = steps.reduce((a, s) => a + s, 0);
        let deg = mid - total / 2;
        return bubbles.map((b, k) => { if (k > 0) deg += steps[k - 1]; return deg; });
    }
    // radius giving a whole ring of bubbles room enough not to overlap
    function ringRadius(bubbles, minRadius) {
        const perimeter = bubbles.reduce((a, b) => a + Math.max(b.offsetWidth, b.offsetHeight) + 12, 0);
        return Math.max(minRadius, perimeter / (2 * Math.PI));
    }

    function openRadial(m, anchor, onClose) {
        const overlay = el("div", "pybiscus-lu-overlay");
        document.body.append(overlay);                    // in the DOM first: sizes are measured
        const current = m.selectedLabel();
        const close = () => { overlay.remove(); document.removeEventListener("keydown", onKey); onClose && onClose(); };
        const onKey = e => { if (e.key === "Escape") { close(); anchor.focus(); } };
        document.addEventListener("keydown", onKey);
        overlay.addEventListener("click", e => { if (e.target === overlay) close(); });
        const pick = l => { m.select(l); close(); anchor.focus(); };

        const center = el("div", "pybiscus-lu-center");
        center.append(el("span", "", "current"), el("b", "", current), el("span", "", "✕ close"));
        center.addEventListener("click", () => { close(); anchor.focus(); });

        const single = m.families.length === 1;
        const famBubbles = single ? [] : m.families.map(f => { const b = bubble(f.name, "family", f.hue); overlay.append(b); return b; });
        const famLayout = famBubbles.map((b, i) => {
            const angle = i * 360 / famBubbles.length;
            const half = radialHalf(b.offsetWidth, b.offsetHeight, angle);
            return { angle, dist: CENTER_R + GAP + half, outer: CENTER_R + GAP + 2 * half };
        });
        const memberBubbles = m.families.map(f => f.members.map(l => {
            const b = bubble(l, l === current ? "current" : "", f.hue);
            b.style.visibility = "hidden";
            b.addEventListener("click", () => pick(l));
            overlay.append(b);
            return b;
        }));
        const R2 = single
            ? ringRadius(memberBubbles[0], CENTER_R + 60)
            : Math.max(...famLayout.map(l => l.outer)) + 40;
        const maxHalf = Math.max(...memberBubbles.flat().map(b => Math.max(b.offsetWidth, b.offsetHeight) / 2));
        const reach = R2 + maxHalf + 16;

        // centred on the anchor, pushed inside the viewport when the menu would overflow it
        const rect = anchor.getBoundingClientRect();
        const cx = Math.min(Math.max(rect.left + rect.width / 2, reach), Math.max(reach, window.innerWidth - reach));
        const cy = Math.min(Math.max(rect.top + rect.height / 2, reach), Math.max(reach, window.innerHeight - reach));
        overlay.style.setProperty("--lu-cx", cx + "px");
        overlay.style.setProperty("--lu-cy", cy + "px");
        (single ? [R2] : [CENTER_R + GAP + 20, R2]).forEach(r => {
            const guide = el("div", "pybiscus-lu-guide");
            guide.style.width = guide.style.height = 2 * r + "px";
            overlay.prepend(place(guide, cx, cy));
        });

        if (single) {
            const bs = memberBubbles[0];
            bs.forEach((b, k) => {
                const [x, y] = polar(cx, cy, R2, k * 360 / bs.length);
                spoke(overlay, cx, cy, x, y, m.families[0].hue);
                place(b, x, y);
                b.style.visibility = "visible";
                b.style.animationDelay = (k * 25) + "ms";
            });
            overlay.append(...bs);
        } else {
            let spokes = [];
            const showFamily = fi => {
                spokes.forEach(s => s.remove());
                memberBubbles.flat().forEach(b => { b.style.visibility = "hidden"; });
                famBubbles.forEach((b, i) => b.classList.toggle("open", i === fi));
                const f = m.families[fi], { angle, dist } = famLayout[fi], bs = memberBubbles[fi];
                const [fx, fy] = polar(cx, cy, dist, angle);
                const angles = arc(bs, angle, R2);
                spokes = bs.map((b, k) => {
                    const [x, y] = polar(cx, cy, R2, angles[k]);
                    place(b, x, y);
                    b.style.visibility = "visible";
                    b.style.animation = "none"; void b.offsetWidth; b.style.animation = "";
                    b.style.animationDelay = (k * 35) + "ms";
                    return spoke(overlay, fx, fy, x, y, f.hue);
                });
                overlay.append(famBubbles[fi], ...bs);  // above the spokes
            };
            famBubbles.forEach((b, i) => {
                const [x, y] = polar(cx, cy, famLayout[i].dist, famLayout[i].angle);
                spoke(overlay, cx, cy, x, y, m.families[i].hue);
                b.style.animationDelay = (i * 40) + "ms";
                overlay.append(place(b, x, y));
                // mousemove, not mouseenter: a bubble appearing under a still pointer must not open
                b.addEventListener("mousemove", () => { if (!b.classList.contains("open")) showFamily(i); });
                b.addEventListener("click", () => showFamily(i));
            });
            showFamily(Math.max(0, m.families.findIndex(f => f.members.includes(current))));
        }
        overlay.append(place(center, cx, cy));
        (overlay.querySelector(".pybiscus-lu-bubble.current") || center).focus?.();
        return close;
    }

    // ------------------------------------------------------------------ representations

    function renderChips(container, m, ui) {
        ui.textContent = "";
        const current = m.selectedLabel();
        const family = m.familyOf(current);
        ui.append(optionButton(current, family, "selected", () => {}));

        const picked = [];
        const add = l => { if (l !== current && m.labels.includes(l) && !picked.includes(l)) picked.push(l); };
        readRecent(container).forEach(add);
        family.members.forEach(add);
        m.labels.forEach(add);
        picked.slice(0, MAX_ALTERNATIVES).forEach(l => ui.append(optionButton(l, m.familyOf(l), "", () => m.select(l))));

        const hidden = m.labels.length - 1 - Math.min(MAX_ALTERNATIVES, picked.length);
        const more = el("button", "pybiscus-lu-more", `+${hidden} others ▾`);
        more.type = "button";
        more.title = "All options, by family";
        // mouse: the radial menu; keyboard (click with detail 0): the grouped list
        more.addEventListener("click", e => (e.detail === 0 ? openList : openRadial)(m, more));
        ui.append(more);
    }

    function renderRadial(container, m, ui) {
        ui.textContent = "";
        const current = m.selectedLabel();
        const family = m.familyOf(current);
        const trigger = coloured(el("button", "pybiscus-lu-trigger"), family.hue);
        trigger.type = "button";
        trigger.append(el("span", "pybiscus-lu-dot"), document.createTextNode(current + " "),
                       el("small", "", (family.name === OTHER ? "" : "· " + family.name + " ") + "▾"));
        trigger.addEventListener("click", e => (e.detail === 0 && m.families.length > 1 ? openList : openRadial)(m, trigger));
        ui.append(trigger);
    }

    function mount(container, mode) {
        unmount(container);
        if (container.closest(".pybiscus-list-template")) {
            return;
        }
        if (mode === "column") {
            // the scrolling column would otherwise hide a selected option placed after the first ones
            const list = container.querySelector(":scope > .pybiscus-tab-buttons");
            const active = list.querySelector(":scope > .pybiscus-tab-button.active");
            if (active) {
                list.scrollTop = active.offsetTop - list.offsetTop - (list.clientHeight - active.offsetHeight) / 2;
            }
            return;
        }
        const m = model(container);
        const ui = el("div", "pybiscus-lu-ui");
        const render = () => (mode === "chips" ? renderChips : renderRadial)(container, m, ui);
        container.classList.add("pybiscus-lu-mounted");
        container.prepend(ui);
        render();
        // tabs also change through other scripts (presets, optional checkboxes): follow them
        const observer = new MutationObserver(() => {
            clearTimeout(ui._pending);
            ui._pending = setTimeout(render, 30);
        });
        m.buttons.forEach(b => observer.observe(b, { attributes: true, attributeFilter: ["class"] }));
        container._pybiscusLargeUnion = { ui, observer };
    }

    function unmount(container) {
        const mounted = container._pybiscusLargeUnion;
        if (mounted) {
            mounted.observer.disconnect();
            mounted.ui.remove();
            container._pybiscusLargeUnion = undefined;
        }
        container.classList.remove("pybiscus-lu-mounted");
    }

    // ------------------------------------------------------------------ setting

    function refresh() {
        const mode = storedMode();
        document.querySelectorAll(".pybiscus-tab-container.pybiscus-tab-large").forEach(c => mount(c, mode));
        MODES.forEach(mo => {
            const button = document.getElementById("largeUnionMode-" + mo);
            if (button) button.classList.toggle("active", mo === mode);
        });
    }

    function setMode(mode) {
        if (!MODES.includes(mode)) return;
        storeMode(mode);
        refresh();
    }

    function init() {
        refresh();
        // list items (pipeline decorators…) are cloned from a template after load
        new MutationObserver(records => {
            const mode = storedMode();
            records.forEach(r => r.addedNodes.forEach(n => {
                if (n.nodeType !== 1) return;
                const found = n.matches(".pybiscus-tab-large") ? [n] : [...n.querySelectorAll(".pybiscus-tab-large")];
                found.forEach(c => { if (!c._pybiscusLargeUnion) mount(c, mode); });
            }));
        }).observe(document.getElementById("top-div") || document.body, { childList: true, subtree: true });
    }

    return { init, setMode, MODES };
})();
