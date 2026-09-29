// Display settings (layout thresholds, column sizes, weight of the selected option, long-list
// representation, list views), saved by the agent on two levels (ui_settings.py): the machine's
// defaults and this agent's own values. Applied live: reloading the page would lose a form
// being edited.
window.pybiscusUiSettings = (() => {

    let state = null;          // spec, agent_port, machine, agent, effective: from the agent
    let preview = null;        // values shown by the open panel, not saved yet
    const listeners = [];      // redraw what depends on the settings (large unions, list views)

    const WEIGHTS = { bold: 700, semibold: 600 };
    const LIST_VIEW_KEY = "pybiscus-list-view-";
    const LARGE_UNION_KEY = "pybiscus-large-union-mode";

    const effective = () => (preview ? { ...state.effective, ...preview } : state.effective);
    const get = name => effective()[name];
    const listView = prefix => (get("list_views") || {})[prefix] || "compact";

    // ------------------------------------------------------------------ layout

    // classList.toggle of an unchanged class still records a mutation, which observers react to
    const toggle = (el, cls, on) => { if (el.classList.contains(cls) !== on) el.classList.toggle(cls, on); };

    function classify(container) {
        const options = container.querySelectorAll(":scope > .pybiscus-tab-buttons > .pybiscus-tab-button").length;
        // Optional[T] (Some / None) keeps its inline rendering
        const optional = container.parentElement?.classList.contains("pybiscus-option-fs");
        const vertical = !optional && options >= get("vertical_tabs_min_options");
        toggle(container, "pybiscus-tab-vertical", vertical);
        toggle(container, "pybiscus-tab-large", vertical && options >= get("large_union_min_options"));
    }

    function apply() {
        const root = document.documentElement.style;
        root.setProperty("--pybiscus-options-col-max", get("options_column_max_width_rem") + "rem");
        root.setProperty("--pybiscus-options-col-max-height", get("options_column_max_height_rem") + "rem");
        root.setProperty("--pybiscus-field-name-col", get("field_name_column_width_rem") + "rem");
        root.setProperty("--pybiscus-active-weight", WEIGHTS[get("active_option_weight")] || WEIGHTS.bold);
        // list templates included: the items cloned from them later inherit the classes
        document.querySelectorAll(".pybiscus-tab-container").forEach(classify);
        listeners.forEach(listener => listener());
    }

    // ------------------------------------------------------------------ agent

    async function request(method, url, body) {
        const res = await fetch(url, body === undefined ? { method } :
            { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        const answer = await res.json();
        if (!res.ok) throw new Error(answer.error || `HTTP ${res.status}`);
        return answer;
    }

    // shown at once (a representation switch reads the new value right away); the agent's answer,
    // which knows the levels below, then replaces the whole state
    async function save(scope, values) {
        const shown = { ...state.effective };
        Object.entries(values).forEach(([name, value]) => {
            if (value === null) return;
            shown[name] = name === "list_views" ? { ...shown[name], ...value } : value;
        });
        state.effective = shown;
        let saved = true;
        try {
            state = await request("PATCH", "/ui/settings", { scope, values });
        } catch (e) {
            saved = false;
            console.warn("[ui settings] not saved:", e.message);
        }
        apply();
        return saved;
    }

    async function reset(scope) {
        try {
            state = await request("DELETE", `/ui/settings?scope=${scope}`);
        } catch (e) {
            console.warn("[ui settings] not reset:", e.message);
        }
        apply();
    }

    // these settings used to live in the browser: moved once into the agent's file
    function migrateBrowserSettings() {
        const values = {}, views = {}, keys = [];
        try {
            const mode = localStorage.getItem(LARGE_UNION_KEY);
            if (mode !== null) {
                keys.push(LARGE_UNION_KEY);
                if (state.spec.large_union_mode.choices.includes(mode)) values.large_union_mode = mode;
            }
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (!key.startsWith(LIST_VIEW_KEY)) continue;
                keys.push(key);
                // v1 keys had recorded the former default for every list: dropped, never moved
                const v2 = LIST_VIEW_KEY + "v2-";
                const view = localStorage.getItem(key);
                if (key.startsWith(v2) && ["compact", "expanded"].includes(view)) views[key.slice(v2.length)] = view;
            }
        } catch (e) {
            return;
        }
        if (Object.keys(views).length) values.list_views = views;
        if (!keys.length) return;
        const forget = () => keys.forEach(key => { try { localStorage.removeItem(key); } catch (e) { /* retried next time */ } });
        if (!Object.keys(values).length) { forget(); return; }
        save("agent", values).then(saved => { if (saved) forget(); });
    }

    // ------------------------------------------------------------------ panel

    const FIELDS = [
        ["vertical_tabs_min_options", "Two-column option lists from", "options"],
        ["large_union_min_options", "Long option lists (chips…) from", "options"],
        ["options_column_max_width_rem", "Options column, max width", "rem"],
        ["options_column_max_height_rem", "Options column, max height", "rem"],
        ["field_name_column_width_rem", "Field names column, width", "rem"],
        ["active_option_weight", "Selected option", ""],
        ["large_union_mode", "Long option lists shown as", ""],
    ];

    let panel = null;
    let scope = "agent";
    let resetViews = false;

    function el(tag, className, text) {
        const e = document.createElement(tag);
        if (className) e.className = className;
        if (text !== undefined) e.textContent = text;
        return e;
    }

    function sourceOf(name) {
        if (name in state.agent) return `agent :${state.agent_port}`;
        if (name in state.machine) return "machine";
        return "default";
    }

    function input(name) {
        const spec = state.spec[name];
        const value = get(name);
        let field;
        if (spec.kind === "choice") {
            field = el("select");
            spec.choices.forEach(choice => field.append(Object.assign(el("option", "", choice), { value: choice, selected: choice === value })));
        } else {
            field = Object.assign(el("input"), { type: "number", min: spec.min, max: spec.max, step: spec.kind === "int" ? 1 : 0.5, value });
        }
        field.addEventListener("input", () => {
            const parsed = spec.kind === "choice" ? field.value : Number(field.value);
            const valid = spec.kind === "choice" ||
                (field.value !== "" && parsed >= spec.min && parsed <= spec.max && (spec.kind !== "int" || Number.isInteger(parsed)));
            field.classList.toggle("invalid", !valid);
            if (!valid) return;
            preview = { ...(preview || {}), [name]: parsed };
            apply();
        });
        return field;
    }

    function render() {
        panel.textContent = "";
        const head = el("div", "pybiscus-ui-head");
        head.append(el("b", "", "Display settings"), Object.assign(el("button", "pybiscus-ui-close", "✕"), { type: "button", title: "Close without saving", onclick: closePanel }));

        const scopes = el("div", "pybiscus-ui-scopes");
        [["agent", `This agent (port ${state.agent_port})`], ["machine", "All agents of this machine"]].forEach(([value, label]) => {
            const radio = Object.assign(el("input"), { type: "radio", name: "pybiscus-ui-scope", value, checked: scope === value });
            radio.addEventListener("change", () => { scope = value; });
            const option = el("label");
            option.append(radio, document.createTextNode(" " + label));
            scopes.append(option);
        });

        const grid = el("div", "pybiscus-ui-grid");
        FIELDS.forEach(([name, label, unit]) => {
            grid.append(el("label", "", label), input(name), el("span", "pybiscus-ui-unit", unit),
                        el("span", "pybiscus-ui-source", sourceOf(name) === "default" ? "default" : `${sourceOf(name)} (default ${state.spec[name].default})`));
        });
        const expanded = Object.values(get("list_views") || {}).filter(view => view === "expanded").length;
        const views = Object.assign(el("button", "", resetViews ? "all compact on save ✓" : "show all compact"), { type: "button" });
        views.addEventListener("click", () => { resetViews = !resetViews; render(); });
        grid.append(el("label", "", "Lists shown expanded"), el("span", "", String(expanded)), el("span"), views);

        const note = el("div", "pybiscus-ui-note");
        if (scope === "machine") note.textContent = "Agents with their own value for a setting keep it.";

        const actions = el("div", "pybiscus-ui-actions");
        const saveButton = Object.assign(el("button", "pybiscus-ui-save", "Save"), { type: "button" });
        saveButton.addEventListener("click", async () => {
            const values = { ...(preview || {}) };
            if (resetViews) values.list_views = null;
            preview = null;
            resetViews = false;
            const saved = await save(scope, values);
            render();
            panel.querySelector(".pybiscus-ui-note").textContent = saved
                ? `Saved for ${scope === "agent" ? "this agent" : "all agents of this machine"}.`
                : "Not saved: the agent did not answer.";
        });
        const resetButton = Object.assign(el("button", "", "Back to defaults"), { type: "button", title: "Forget the values saved at the chosen level" });
        resetButton.addEventListener("click", async () => { preview = null; resetViews = false; await reset(scope); render(); });
        actions.append(saveButton, resetButton);

        panel.append(head, scopes, grid, actions, note);
    }

    function openPanel() {
        if (panel) return closePanel();
        panel = el("div", "pybiscus-ui-panel");
        panel.setAttribute("role", "dialog");
        render();
        document.body.append(panel);
        document.addEventListener("keydown", onKey);
    }

    function closePanel() {
        if (!panel) return;
        panel.remove();
        panel = null;
        preview = null;
        resetViews = false;
        document.removeEventListener("keydown", onKey);
        apply();
    }

    const onKey = e => { if (e.key === "Escape") closePanel(); };

    // ------------------------------------------------------------------ entry points

    function init(initialState) {
        state = initialState;
        apply();
        migrateBrowserSettings();
    }

    return {
        init, get, listView, save, openPanel,
        onChange: listener => listeners.push(listener),
    };
})();
