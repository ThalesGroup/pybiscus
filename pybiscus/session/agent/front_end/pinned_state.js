// Pinned configuration: the form's state (options, list items, values), not its HTML. Pinning
// the whole page froze the interface injected by the scripts (list graphs, chips…), which the
// scripts then added a second time, and kept the CSS/JS of the pinning day.
// The state is keyed by structure, never by a global data-pybiscus-name lookup: the options of
// a union share their fields' names (every strategy has "server_strategy.name"), so a lookup by
// name alone could hit a field of another option. Values of non-selected options are kept too.
window.pybiscusPinnedState = (() => {

    // a scope owns the fields below it up to the next nested scope
    const SCOPE = ".pybiscus-tab-content, .pybiscus-list-content";

    const optionButtons = fs => [...fs.querySelectorAll(":scope > .pybiscus-tab-container > .pybiscus-tab-buttons > .pybiscus-tab-button")];
    const optionContent = (fs, button) => fs.querySelector(`:scope > .pybiscus-tab-container > #${CSS.escape(button.dataset.tab)}`);
    const listItems = fs => [...fs.querySelectorAll(":scope > .pybiscus-list > .pybiscus-list-contents > .pybiscus-list-content")];

    function listKey(fs, rank) {
        const probe = fs.querySelector(":scope > .pybiscus-list > .pybiscus-list-template [data-pybiscus-name], :scope > .pybiscus-list > .pybiscus-list-template [data-pybiscus-prefix]");
        const path = probe && (probe.getAttribute("data-pybiscus-prefix") || probe.getAttribute("data-pybiscus-name"));
        return path ? path.split(".#")[0] : `list ${rank}`;
    }

    // unions, lists and named fields of a scope, in document order, without entering nested scopes
    function parts(scope) {
        const found = { unions: [], lists: [], fields: [] };
        const visit = el => {
            for (const child of el.children) {
                if (child.matches(".pybiscus-list-template")) continue;
                if (child.matches("fieldset.pybiscus-list-fs")) { found.lists.push(child); continue; }
                if (child.matches(".pybiscus-fieldset-container[data-pybiscus-prefix]")) { found.unions.push(child); continue; }
                if (child.hasAttribute("data-pybiscus-name") && child.tagName === "INPUT") found.fields.push(child);
                if (!child.matches(SCOPE)) visit(child);
            }
        };
        visit(scope);
        return found;
    }

    // ------------------------------------------------------------------ capture

    function capture(scope) {
        const { unions, lists, fields } = parts(scope);
        const state = { values: {}, unions: {}, lists: {} };
        fields.forEach(input => {
            const name = input.getAttribute("data-pybiscus-name");
            if (input.type === "radio") {
                if (input.checked) state.values[name] = input.value;
            } else if (input.type === "checkbox") {
                state.values[name] = input.checked;
            } else {
                state.values[name] = input.value;
            }
        });
        unions.forEach(fs => {
            const buttons = optionButtons(fs);
            const active = buttons.find(b => b.classList.contains("active"));
            const options = {};
            buttons.forEach(b => { const content = optionContent(fs, b); if (content) options[b.textContent] = capture(content); });
            state.unions[fs.getAttribute("data-pybiscus-prefix")] = { selected: active ? active.textContent : null, options };
        });
        lists.forEach((fs, rank) => { state.lists[listKey(fs, rank)] = listItems(fs).map(capture); });
        return state;
    }

    // ------------------------------------------------------------------ restore

    const warn = (...args) => console.warn("[pinned config]", ...args);

    // synchronous: the tab click handler switches after 600 ms, too late for the values below
    function select(fs, label) {
        const buttons = optionButtons(fs);
        const chosen = buttons.find(b => b.textContent === label);
        if (!chosen) {
            warn(`option "${label.trim() || "(optional)"}" no longer exists in`, fs.getAttribute("data-pybiscus-prefix"));
            return;
        }
        buttons.forEach(b => {
            const on = b === chosen;
            b.classList.toggle("active", on);
            b.setAttribute("data-pybiscus-status", on ? "valid" : "ignored");
            const content = optionContent(fs, b);
            if (!content) return;
            content.classList.toggle("active", on);
            content.classList.remove("hidden");
            content.setAttribute("data-pybiscus-status", on ? "valid" : "ignored");
        });
        // Optional[T]: the first option is Some, shown by the legend's checkbox
        const checkbox = fs.querySelector(":scope > legend input.pybiscus-option-cb");
        if (checkbox) {
            checkbox.checked = chosen === buttons[0];
            fs.classList.toggle("pybiscus-camouflaged-fieldset", !checkbox.checked);
        }
    }

    function setLength(fs, count) {
        listItems(fs).forEach(item => item.remove());
        const generator = fs.querySelector(":scope > legend .pybiscus-list-generator");
        for (let i = 0; i < count; i++) generator.click();
    }

    function setValue(inputs, value) {
        const first = inputs[0];
        if (first.type === "radio") {
            inputs.forEach(r => {
                r.checked = r.value === value;
                r.parentElement.setAttribute("data-pybiscus-status", r.checked ? "valid" : "ignored");
            });
        } else if (first.type === "checkbox") {
            first.checked = value === true;
        } else {
            first.value = value;
        }
    }

    function restore(scope, state) {
        const { unions, lists, fields } = parts(scope);

        const byName = {};
        fields.forEach(input => (byName[input.getAttribute("data-pybiscus-name")] ||= []).push(input));
        Object.entries(state.values || {}).forEach(([name, value]) => {
            if (byName[name]) setValue(byName[name], value);
            else warn("field no longer exists:", name);
        });

        const unionsByPrefix = Object.fromEntries(unions.map(fs => [fs.getAttribute("data-pybiscus-prefix"), fs]));
        Object.entries(state.unions || {}).forEach(([prefix, union]) => {
            const fs = unionsByPrefix[prefix];
            if (!fs) { warn("option group no longer exists:", prefix); return; }
            optionButtons(fs).forEach(b => {
                const content = optionContent(fs, b);
                if (content && union.options[b.textContent]) restore(content, union.options[b.textContent]);
            });
            if (union.selected !== null) select(fs, union.selected);
        });

        const listsByKey = Object.fromEntries(lists.map((fs, rank) => [listKey(fs, rank), fs]));
        Object.entries(state.lists || {}).forEach(([key, items]) => {
            const fs = listsByKey[key];
            if (!fs) { warn("list no longer exists:", key); return; }
            setLength(fs, items.length);
            listItems(fs).forEach((item, i) => restore(item, items[i]));
        });
    }

    const root = () => document.getElementById("top-div");

    return {
        capture: () => capture(root()),
        restore: state => restore(root(), state),
    };
})();
