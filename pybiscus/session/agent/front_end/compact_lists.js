// Compact view of lists (pipeline…): a linear graph of the items (rank, name, type) with the
// current item's values below it. Items are only hidden: they stay in the DOM, so traverseDOM
// still builds the whole list. The graph's ← → ➖ ➕ click the list's own controls (the item's
// movers and eraser, the list generator): both views share one code path and one numbering.
window.pybiscusCompactLists = (() => {

    const listPrefix = fs => {
        const probe = fs.querySelector(":scope > .pybiscus-list > .pybiscus-list-template :is([data-pybiscus-prefix], [data-pybiscus-name])");
        const path = probe ? (probe.getAttribute("data-pybiscus-prefix") || probe.getAttribute("data-pybiscus-name")) : "";
        return path.split(".#")[0] || fs.querySelector(":scope > legend .pybiscus-config")?.textContent.trim() || "list";
    };
    // a display setting saved by the agent (ui_settings.js); compact unless chosen otherwise
    const storedCompact = fs => pybiscusUiSettings.listView(listPrefix(fs)) !== "expanded";
    function storeCompact(fs, compact) {
        pybiscusUiSettings.save("agent", { list_views: { [listPrefix(fs)]: compact ? "compact" : "expanded" } });
    }

    const contentsOf = fs => fs.querySelector(":scope > .pybiscus-list > .pybiscus-list-contents");
    const itemsOf = fs => [...contentsOf(fs).querySelectorAll(":scope > .pybiscus-list-content")];
    // the item's own controls, not those of lists nested in it
    const ownControls = (item, selector) =>
        [...item.querySelectorAll(selector)].filter(c => c.closest(".pybiscus-list-content") === item);

    function describe(item, rank) {
        // union item: its selected option; otherwise a "name" field, then the first input
        const union = item.querySelector(".pybiscus-tab-container");
        const buttons = union ? [...union.querySelectorAll(":scope > .pybiscus-tab-buttons > .pybiscus-tab-button")] : [];
        const active = buttons.find(b => b.classList.contains("active"));
        if (active && active.textContent.trim()) {
            const type = active.dataset.pybiscusGroup || "";
            const hue = type && window.pybiscusLargeUnions ? pybiscusLargeUnions.familyHues(buttons).get(type) : undefined;
            return { name: active.textContent.trim(), type, hue };
        }
        const named = item.querySelector('input[data-pybiscus-name$=".name"]');
        const first = named || item.querySelector("input[data-pybiscus-name]:not([type=checkbox]):not([type=radio])");
        const name = first && first.value.trim();
        return { name: name || `item ${rank}`, type: "" };
    }

    // ---- rules of a list's options (data-pybiscus-after…), its anchor and implicit items
    // (data-pybiscus-chain): the same rules as the check's validators, shown before it runs

    const words = value => (value || "").split(" ").filter(Boolean);
    const scopeOf = fs => fs.closest("#top-div") || document;
    const parentPrefix = fs => listPrefix(fs).split(".").slice(0, -1).join(".");
    const siblingName = (fs, field) => (parentPrefix(fs) ? parentPrefix(fs) + "." : "") + field;
    const activeOption = container => container?.querySelector(".pybiscus-tab-buttons > .pybiscus-tab-button.active");

    function optionRules(fs) {
        const buttons = fs.querySelector(":scope > .pybiscus-list > .pybiscus-list-template .pybiscus-tab-buttons");
        const rules = new Map();
        buttons?.querySelectorAll(":scope > .pybiscus-tab-button[data-pybiscus-option]").forEach(b => rules.set(b.dataset.pybiscusOption, {
            after: words(b.dataset.pybiscusAfter),
            incompatible: words(b.dataset.pybiscusIncompatible),
            strategies: b.hasAttribute("data-pybiscus-strategies") ? words(b.dataset.pybiscusStrategies) : null,
            last: b.dataset.pybiscusLast === "true",
            label: b.textContent.trim(),
        }));
        return rules;
    }

    function anchorOf(fs, spec) {
        if (!spec?.anchor) return null;
        const container = scopeOf(fs).querySelector(`fieldset[data-pybiscus-prefix="${siblingName(fs, spec.anchor)}"]`);
        const active = activeOption(container);
        return container && active ? { container, label: active.textContent.trim(), option: active.dataset.pybiscusOption } : null;
    }

    function implicitSource(fs, field) {
        const name = siblingName(fs, field);
        const scope = scopeOf(fs);
        return scope.querySelector(`fieldset.pybiscus-option-fs[data-pybiscus-prefix="${name}"]`)
            || scope.querySelector(`input[data-pybiscus-name="${name}"]`)?.closest(".pybiscus-field");
    }

    function implicitActive(fs, { field, value }) {
        const name = siblingName(fs, field);
        const scope = scopeOf(fs);
        if (value === "set") {
            return !!scope.querySelector(`fieldset.pybiscus-option-fs[data-pybiscus-prefix="${name}"] > legend .pybiscus-option-cb`)?.checked;
        }
        const input = scope.querySelector(`input[data-pybiscus-name="${name}"]:checked, select[data-pybiscus-name="${name}"]`);
        return input?.value === value;
    }

    // the items in the order they run: the listed ones, with the implicit ones where the
    // validators insert them (last when the spec or the option says so, else right after the ones
    // it must follow, else first)
    function sequence(fs, items, rules, spec) {
        const entries = items.map(item => ({ item, name: activeOption(item)?.dataset.pybiscusOption }));
        (spec?.implicit || []).forEach(implicit => {
            if (!implicitActive(fs, implicit) || entries.some(e => e.name === implicit.name)) return;
            const rule = rules.get(implicit.name) || { after: [] };
            const entry = { implicit, name: implicit.name };
            if (implicit.place === "last" || rule.last) { entries.push(entry); return; }
            const after = entries.map((e, i) => rule.after.includes(e.name) ? i : -1).filter(i => i >= 0);
            entries.splice(after.length ? Math.max(...after) + 1 : 0, 0, entry);
        });
        return entries;
    }

    // check_compatible_decorators (config_server.py), message for message
    function issues(entries, rules, anchor) {
        const names = entries.map(e => e.name);
        const found = [];
        entries.forEach((entry, index) => {
            const rule = rules.get(entry.name);
            const flag = text => { found.push(text); (entry.issues ||= []).push(text); };
            if (!rule) {
                if (entry.implicit) flag(`${entry.name} needs its plugin, which is not loaded`);
                return;
            }
            rule.incompatible.forEach(other => {
                const others = names.filter(n => n === other).length - (other === entry.name ? 1 : 0);
                if (others > 0) flag(`${entry.name} cannot be combined with ${other}`);
            });
            rule.after.forEach(other => {
                if (names.includes(other) && names.indexOf(other) > index) flag(`${entry.name} must come after ${other}`);
            });
            if (rule.last && index !== names.length - 1) flag(`${entry.name} must come last`);
            if (rule.strategies && anchor?.option && !rule.strategies.includes(anchor.option)) {
                flag(`${entry.name} works over the strategies ${rule.strategies.join(", ")}, not ${anchor.option}`);
            }
        });
        return [...new Set(found)];
    }

    function renderIssues(fs) {
        const state = fs._pybiscusCompact;
        const items = itemsOf(fs);
        const entries = sequence(fs, items, state.rules, state.spec);
        const anchor = anchorOf(fs, state.spec);
        const found = issues(entries, state.rules, anchor);
        state.issues.textContent = "";
        state.issues.hidden = !found.length;
        found.forEach(text => state.issues.append(Object.assign(document.createElement("div"), { textContent: "⚠ " + text })));
        return { entries, anchor };
    }

    function button(className, text, title, onClick) {
        const b = document.createElement("button");
        b.type = "button";
        b.className = className;
        b.textContent = text;
        b.title = title;
        b.addEventListener("click", onClick);
        return b;
    }

    function render(fs) {
        const { entries, anchor } = renderIssues(fs);
        // the expanded view shows every item: never hide items nor draw outside the compact view
        if (!fs.classList.contains("pybiscus-cl-compact")) return;
        const state = fs._pybiscusCompact;
        const items = itemsOf(fs);
        if (!items.includes(state.current)) {
            state.current = items[Math.min(state.lastIndex, items.length - 1)] || null;
        }
        const index = items.indexOf(state.current);
        state.lastIndex = Math.max(0, index);

        items.forEach(item => {
            item.classList.toggle("pybiscus-cl-hidden", item !== state.current);
            // classList.add of a present class still records a mutation: guard it (render loop)
            ownControls(item, ".pybiscus-list-mover, .pybiscus-list-eraser")
                .forEach(c => { if (!c.classList.contains("pybiscus-cl-own-control")) c.classList.add("pybiscus-cl-own-control"); });
        });

        const graph = state.graph;
        graph.textContent = "";
        const chain = document.createElement("div");
        chain.className = "pybiscus-cl-chain";
        if (!items.length) {
            chain.append(Object.assign(document.createElement("span"), { className: "pybiscus-cl-empty", textContent: "empty list: ➕📝 adds an item" }));
        }
        const link = () => chain.append(Object.assign(document.createElement("span"), { className: "pybiscus-cl-link", textContent: "→" }));
        if (anchor) {
            const node = button("pybiscus-cl-anchor", "", `${anchor.label}: the strategy, wrapped by the items in this order`,
                                () => anchor.container.scrollIntoView({ block: "start", behavior: "smooth" }));
            node.append(Object.assign(document.createElement("span"), { className: "pybiscus-cl-name", textContent: anchor.label }));
            chain.append(node);
            if (entries.length) link();
        }
        entries.forEach((entry, position) => {
            if (position > 0) link();
            const marked = entry.issues ? " pybiscus-cl-issue" : "";
            const why = entry.issues ? "\n⚠ " + entry.issues.join("\n⚠ ") : "";
            if (entry.implicit) {
                const source = implicitSource(fs, entry.implicit.field);
                const label = state.rules.get(entry.name)?.label || entry.name;
                const node = button("pybiscus-cl-node pybiscus-cl-implicit" + marked, "",
                                    `${label}: added by ${entry.implicit.field}` + why,
                                    () => source?.scrollIntoView({ block: "center", behavior: "smooth" }));
                node.append(Object.assign(document.createElement("span"), { className: "pybiscus-cl-rank", textContent: "auto" }),
                            Object.assign(document.createElement("span"), { className: "pybiscus-cl-name", textContent: label }),
                            Object.assign(document.createElement("span"), { className: "pybiscus-cl-type", textContent: entry.implicit.field }));
                chain.append(node);
                return;
            }
            const item = entry.item;
            const rank = items.indexOf(item);
            const { name, type, hue } = describe(item, rank);
            const node = button("pybiscus-cl-node" + (item === state.current ? " current" : "") + (hue !== undefined ? " pybiscus-cl-family" : "") + marked,
                                "", `${rank} · ${name}` + (type ? ` (${type})` : "") + why, () => { state.current = item; render(fs); });
            if (hue !== undefined) node.style.setProperty("--lu-hue", hue);
            node.append(Object.assign(document.createElement("span"), { className: "pybiscus-cl-rank", textContent: rank }),
                        Object.assign(document.createElement("span"), { className: "pybiscus-cl-name", textContent: name }));
            if (type) node.append(Object.assign(document.createElement("span"), { className: "pybiscus-cl-type", textContent: type }));
            if (item !== state.current) { chain.append(node); return; }
            // the current item's controls under it: at the end of a long chain they went out of view
            const slot = Object.assign(document.createElement("span"), { className: "pybiscus-cl-current" });
            slot.append(node, currentActions(fs, items, index));
            chain.append(slot);
        });

        graph.append(chain);
        // horizontal only: scrollIntoView could also move the page while a value is typed
        const shown = chain.querySelector(".pybiscus-cl-current");
        if (shown) chain.scrollLeft = shown.offsetLeft - (chain.clientWidth - shown.offsetWidth) / 2;
    }

    // adding is the legend's ➕📝: it appends at the end, whatever the current item
    function currentActions(fs, items, index) {
        const current = items[index];
        const actions = document.createElement("span");
        actions.className = "pybiscus-cl-actions";
        // the original controls act synchronously (move / remove / add, then renumbering): redraw
        // right after them instead of relying on the mutation observer alone, which reported
        // graphs left unchanged after ← → in a user's browser
        const act = control => () => { control(); render(fs); };
        const left = button("pybiscus-cl-action", "←", "Move the current item earlier", act(() => current._moveUp && current._moveUp.click()));
        const right = button("pybiscus-cl-action", "→", "Move the current item later", act(() => current._moveDown && current._moveDown.click()));
        // the item fades out before it goes: among identical items, removing one in the middle
        // looked like removing the last one (the ranks are renumbered)
        const erase = act(() => ownControls(current, ".pybiscus-list-eraser")[0]?.click());
        const remove = button("pybiscus-cl-action remove", "➖", "Remove the current item", () => {
            if (remove.disabled) return;
            remove.disabled = true;
            remove.closest(".pybiscus-cl-current")?.classList.add("pybiscus-cl-leaving");
            setTimeout(erase, matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 220);
        });
        // hidden, not removed: ➖ stays centred under the item
        left.style.visibility = index === 0 ? "hidden" : "";
        right.style.visibility = index === items.length - 1 ? "hidden" : "";
        actions.append(left, remove, right);
        return actions;
    }

    function setCompact(fs, compact) {
        const state = fs._pybiscusCompact;
        state.toggle.textContent = compact ? "⊞" : "⊟";
        state.toggle.title = compact ? "Show all items" : "Compact view: items as a graph, one item shown";
        fs.classList.toggle("pybiscus-cl-compact", compact);
        state.graph.hidden = !compact;
        if (compact) {
            render(fs);
        } else {
            itemsOf(fs).forEach(item => item.classList.remove("pybiscus-cl-hidden"));
        }
    }

    function mount(fs) {
        if (fs._pybiscusCompact || fs.closest(".pybiscus-list-template") || !contentsOf(fs)) {
            return;
        }
        const legend = fs.querySelector(":scope > legend");
        const generator = legend && legend.querySelector(".pybiscus-list-generator");
        if (!generator) return;

        const state = { current: null, lastIndex: 0 };
        fs._pybiscusCompact = state;
        // only a click on the toggle records a choice: the default stays compact otherwise
        state.toggle = button("pybiscus-cl-toggle", "⊟", "", () => {
            const compact = !fs.classList.contains("pybiscus-cl-compact");
            storeCompact(fs, compact);
            setCompact(fs, compact);
        });
        generator.after(state.toggle);
        state.graph = document.createElement("div");
        state.graph.className = "pybiscus-cl-graph";
        contentsOf(fs).before(state.graph);
        state.rules = optionRules(fs);
        state.spec = fs.dataset.pybiscusChain ? JSON.parse(fs.dataset.pybiscusChain) : null;
        state.issues = Object.assign(document.createElement("div"), { className: "pybiscus-cl-issues", hidden: true });
        state.issues.setAttribute("role", "status");
        state.graph.after(state.issues);

        // follow additions (the new item becomes current), removals, moves, option and value changes
        const contents = contentsOf(fs);
        let before = itemsOf(fs);
        // one pending render at a time, never postponed: restarting the delay on every mutation
        // starved the rendering while tab classes kept changing
        const rerender = () => {
            if (state.pending) return;
            state.pending = setTimeout(() => { state.pending = null; render(fs); }, 20);
        };
        new MutationObserver(records => {
            // ignore this script's own class changes (hidden items, own controls): only item
            // additions, removals, moves and tab (option) changes alter the graph
            const relevant = records.some(r => r.type === "childList" || r.target.classList.contains("pybiscus-tab-button"));
            if (!relevant) return;
            const now = itemsOf(fs);
            const added = now.filter(i => !before.includes(i));
            if (added.length && records.some(r => r.type === "childList" && r.target === contents)) {
                state.current = added[added.length - 1];
            }
            before = now;
            rerender();
        }).observe(contents, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
        contents.addEventListener("input", rerender);
        // the anchor and the fields adding implicit items live outside the list
        if (state.spec) {
            const anchor = anchorOf(fs, state.spec);
            if (anchor) new MutationObserver(records => {
                if (records.some(r => r.target.classList.contains("pybiscus-tab-button"))) rerender();
            }).observe(anchor.container, { subtree: true, attributes: true, attributeFilter: ["class"] });
            (state.spec.implicit || []).forEach(({ field }) => {
                const source = implicitSource(fs, field);
                source?.addEventListener("change", rerender);
                source?.addEventListener("click", rerender);
            });
        }

        setCompact(fs, storedCompact(fs));
    }

    function init() {
        document.querySelectorAll(".pybiscus-list-fs").forEach(mount);
        // views reset from the settings panel
        pybiscusUiSettings.onChange(() => document.querySelectorAll(".pybiscus-list-fs").forEach(fs => {
            if (fs._pybiscusCompact && storedCompact(fs) !== fs.classList.contains("pybiscus-cl-compact")) setCompact(fs, storedCompact(fs));
        }));
        // lists nested in items appear with their item
        new MutationObserver(records => records.forEach(r => r.addedNodes.forEach(n => {
            if (n.nodeType !== 1) return;
            (n.matches(".pybiscus-list-fs") ? [n] : [...n.querySelectorAll(".pybiscus-list-fs")]).forEach(mount);
        }))).observe(document.getElementById("top-div") || document.body, { childList: true, subtree: true });
    }

    return { init };
})();
