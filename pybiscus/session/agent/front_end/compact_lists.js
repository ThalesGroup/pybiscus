// Compact view of lists (pipeline…): a linear graph of the items (rank, name, type) with the
// current item's values below it. Items are only hidden: they stay in the DOM, so traverseDOM
// still builds the whole list. The graph's ← → ➖ ➕ click the list's own controls (the item's
// movers and eraser, the list generator): both views share one code path and one numbering.
window.pybiscusCompactLists = (() => {

    // v2: the first version stored the view at every page load, so its default ("expanded") was
    // recorded for every list and would now hide the compact default; those values are ignored
    const VIEW_KEY_PREFIX = "pybiscus-list-view-v2-";

    const listPrefix = fs => {
        const probe = fs.querySelector(".pybiscus-list-template [data-pybiscus-prefix], .pybiscus-list-template [data-pybiscus-name]");
        const path = probe ? (probe.getAttribute("data-pybiscus-prefix") || probe.getAttribute("data-pybiscus-name")) : "";
        return path.split(".#")[0] || fs.querySelector(":scope > legend .pybiscus-config")?.textContent.trim() || "list";
    };
    // compact by default: only an explicit "show all" choice is remembered as expanded
    function storedCompact(fs) {
        try { return localStorage.getItem(VIEW_KEY_PREFIX + listPrefix(fs)) !== "expanded"; } catch (e) { return true; }
    }
    function storeCompact(fs, compact) {
        try { localStorage.setItem(VIEW_KEY_PREFIX + listPrefix(fs), compact ? "compact" : "expanded"); } catch (e) { /* not remembered */ }
    }

    const contentsOf = fs => fs.querySelector(":scope > .pybiscus-list > .pybiscus-list-contents");
    const itemsOf = fs => [...contentsOf(fs).querySelectorAll(":scope > .pybiscus-list-content")];
    // the item's own controls, not those of lists nested in it
    const ownControls = (item, selector) =>
        [...item.querySelectorAll(selector)].filter(c => c.closest(".pybiscus-list-content") === item);

    function describe(item, rank) {
        // union item: its selected option; otherwise a "name" field, then the first input
        const union = item.querySelector(".pybiscus-tab-container");
        const active = union && union.querySelector(":scope > .pybiscus-tab-buttons > .pybiscus-tab-button.active");
        if (active && active.textContent.trim()) {
            return { name: active.textContent.trim(), type: active.dataset.pybiscusGroup || "" };
        }
        const named = item.querySelector('input[data-pybiscus-name$=".name"]');
        const first = named || item.querySelector("input[data-pybiscus-name]:not([type=checkbox]):not([type=radio])");
        const name = first && first.value.trim();
        return { name: name || `item ${rank}`, type: "" };
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
            chain.append(Object.assign(document.createElement("span"), { className: "pybiscus-cl-empty", textContent: "empty list: ➕ adds an item" }));
        }
        items.forEach((item, rank) => {
            if (rank > 0) chain.append(Object.assign(document.createElement("span"), { className: "pybiscus-cl-link", textContent: "→" }));
            const { name, type } = describe(item, rank);
            const node = button("pybiscus-cl-node" + (item === state.current ? " current" : ""), "", `${rank} · ${name}`,
                                () => { state.current = item; render(fs); });
            node.append(Object.assign(document.createElement("span"), { className: "pybiscus-cl-rank", textContent: rank }),
                        Object.assign(document.createElement("span"), { className: "pybiscus-cl-name", textContent: name }));
            if (type) node.append(Object.assign(document.createElement("span"), { className: "pybiscus-cl-type", textContent: type }));
            chain.append(node);
        });

        const current = state.current;
        const actions = document.createElement("div");
        actions.className = "pybiscus-cl-actions";
        // the original controls act synchronously (move / remove / add, then renumbering): redraw
        // right after them instead of relying on the mutation observer alone, which reported
        // graphs left unchanged after ← → in a user's browser
        const act = control => () => { control(); render(fs); };
        const left = button("pybiscus-cl-action", "←", "Move the current item earlier", act(() => current._moveUp && current._moveUp.click()));
        const right = button("pybiscus-cl-action", "→", "Move the current item later", act(() => current._moveDown && current._moveDown.click()));
        const remove = button("pybiscus-cl-action remove", "➖", "Remove the current item",
                              act(() => ownControls(current, ".pybiscus-list-eraser")[0]?.click()));
        const add = button("pybiscus-cl-action add", "➕", "Add an item", act(() => {
            fs.querySelector(":scope > legend .pybiscus-list-generator").click();
            state.current = itemsOf(fs).pop() || null;
        }));
        left.disabled = !current || index === 0;
        right.disabled = !current || index === items.length - 1;
        remove.disabled = !current;
        actions.append(left, right, remove, add);

        graph.append(chain, actions);
        // horizontal only: scrollIntoView could also move the page while a value is typed
        const shown = chain.querySelector(".current");
        if (shown) chain.scrollLeft = shown.offsetLeft - (chain.clientWidth - shown.offsetWidth) / 2;
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

        // follow additions (the new item becomes current), removals, moves, option and value changes
        const contents = contentsOf(fs);
        let before = itemsOf(fs);
        // one pending render at a time, never postponed: restarting the delay on every mutation
        // starved the rendering while tab classes kept changing
        const rerender = () => {
            if (!fs.classList.contains("pybiscus-cl-compact") || state.pending) return;
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

        setCompact(fs, storedCompact(fs));
    }

    function init() {
        document.querySelectorAll(".pybiscus-list-fs").forEach(mount);
        // lists nested in items appear with their item
        new MutationObserver(records => records.forEach(r => r.addedNodes.forEach(n => {
            if (n.nodeType !== 1) return;
            (n.matches(".pybiscus-list-fs") ? [n] : [...n.querySelectorAll(".pybiscus-list-fs")]).forEach(mount);
        }))).observe(document.getElementById("top-div") || document.body, { childList: true, subtree: true });
    }

    return { init };
})();
