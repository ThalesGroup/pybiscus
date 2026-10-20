
const launch_session_button = document.getElementById('launch-session-button');

// add an button event listener
launch_session_button.addEventListener('click', function() {

    // Select top-div ided element
    const topDiv = document.getElementById('top-div');
    clearRefusal(topDiv);

    // generate configuration data (returns a list of 3-tuples)
    raw_data = traverseDOM(topDiv, []).reverse();

    // console.log( raw_data );

    // transform configuration from format to session config
    // to either server or client HMI configuration actions

    const server_host      = raw_data.find(row => row[0] === 'flower_server.server_host');
    const server_port      = raw_data.find(row => row[0] === 'flower_server.server_port');
    const server_listen_to = raw_data.find(row => row[0] === 'flower_server.server_listen_to');
    const server_protocol  = raw_data.find(row => row[0] === 'flower_server.server_protocol');

    // console.log( server_protocol );

    const exclude = ['flower_server.server_host', 'flower_server.server_port', 'flower_server.server_protocol', 'flower_server.server_listen_to'];
    // the data partition and holdout are not options to select: the manager turns them into each
    // client's train.partition and val section
    const is_partition = row => row[0].startsWith('data_partition.');
    const is_holdout = row => row[0].startsWith('data_holdout.');
    // the manager's schedule of the session's repetition, not an option of the participants' forms
    const is_repeat = row => row[0].startsWith('repeat.');
    // a manager setting too, not an option to select
    const share_row = raw_data.find(row => row[0] === 'share_cpu_threads');
    const share_cpu_threads = share_row ? share_row[1] === true || share_row[1] === 'true' : false;
    const min_clients_row = raw_data.find(row => row[0] === 'min_clients');
    const min_clients = min_clients_row ? Number(min_clients_row[1]) : null;
    const num_rounds_row = raw_data.find(row => row[0] === 'num_rounds');
    const num_rounds = num_rounds_row ? Number(num_rounds_row[1]) : null;
    // a value of the server's form, not an option to select in every form
    const robustness_row = raw_data.find(row => row[0] === 'robustness');
    const robustness = robustness_row ? robustness_row[1] : null;
    // the model: its plugin and its direct scalar fields, set and locked in every form (a dict's
    // entries cannot be recreated in another form)
    const is_model = row => row[0] === 'model.name' || row[0].startsWith('model.config.');
    const model_values = raw_data.filter(row => /^model\.config\.[^.]+$/.test(row[0]) && ! Array.isArray(row[1]));
    const new_data = raw_data.filter(row => ! exclude.includes(row[0]) && ! is_model(row) && ! is_partition(row) && ! is_holdout(row) && ! is_repeat(row) && row !== share_row && row !== min_clients_row && row !== num_rounds_row && row !== robustness_row);
    const partition_rows = raw_data.filter(is_partition);
    const data_partition = partition_rows.length
        ? Object.fromEntries(partition_rows.map(([key, value]) => [key.slice('data_partition.'.length), value]))
        : null;
    const holdout_rows = raw_data.filter(is_holdout);
    const data_holdout = holdout_rows.length
        ? Object.fromEntries(holdout_rows.map(([key, value]) => [key.slice('data_holdout.'.length), value]))
        : null;

    // an unset Optional field (every or cron) is left out: the schedule takes one of them
    const repeat_rows = raw_data.filter(row => is_repeat(row) && row[1] !== null && row[1] !== '');
    const repeat = repeat_rows.length
        ? Object.fromEntries(repeat_rows.map(([key, value]) => [key.slice('repeat.'.length), value]))
        : null;

    // console.log( new_data );

    const listen_address = server_listen_to[1] === "the whole internet" ? "[::]" : "[::1]";

    // special names of tab components for unions corresponding to an optional config field
    const optional_options_by_visibility = { true: ' ', false: '  ' };

    const ssl_option_is_visible = optional_options_by_visibility[server_protocol[1] === 'https'];

    const values_set = { 
        'flower_server.listen_address' : `${listen_address}:${server_port[1]}`,
        'flower_client.server_address' : `${server_host[1]}:${server_port[1]}`,
    };
    const values_lock  = [
        'root_dir', 
        'flower_server.listen_address', 
        'flower_client.server_address',
    ];

    const options_set  = {
        'flower_server.ssl'            : `${ssl_option_is_visible}`,
        'flower_client.ssl'            : `${ssl_option_is_visible}`,
    }
    
    const options_lock = ['flower_server.ssl', 'flower_client.ssl', ];

    new_data.forEach(([key, value]) => {
        
        options_set[key] = value;
        options_lock.push(key);
    });

    options_set['model'] = selected_option('model');
    options_lock.push('model');
    model_values.forEach(([key, value]) => {
        values_set[key] = value;
        values_lock.push(key);
    });

    // TODO: for the time being this data is common to server and client
    // so may cause errors in the console for values specific to the other mode
    const server_data = {
        options_set,
        options_lock,
        values_set,
        values_lock,
        data_partition,
        data_holdout,
        share_cpu_threads,
        min_clients,
        num_rounds,
        robustness,
        repeat,
    };    

    // console.log( server_data );

    window.parent.postMessage({ type: "session_config", value: server_data }, "*");
});

function clearRefusal(topDiv) {
    pybiscusCheckErrors.clear(topDiv);
    document.getElementById('check-failure-result').style.display = 'none';
    document.getElementById('check-errors-unplaced').replaceChildren();
}

// the manager refused the session: its problems as the check's errors, shown under their fields
window.addEventListener('message', event => {
    if (event.source !== window.parent || event.data?.type !== 'session_refused') return;
    const topDiv = document.getElementById('top-div');
    const fields = Array.isArray(event.data.fields) ? event.data.fields : [];
    const unplaced = pybiscusCheckErrors.show(topDiv, fields);
    const failure = document.getElementById('check-failure-result');
    failure.textContent = fields.length > unplaced.length
        ? `Session refused: ${fields.length} problem${fields.length > 1 ? 's' : ''}, shown in red in the form.`
        : 'Session refused.';
    failure.style.display = 'block';
    // a refusal about no field (a relay to designate, the upper level not configured) has only its message
    const lines = fields.length > 0 ? unplaced : [event.data.message || 'unknown reason'];
    const unplacedDiv = document.getElementById('check-errors-unplaced');
    for (const line of lines) {
        const pre = document.createElement('pre');
        pre.textContent = line;
        unplacedDiv.appendChild(pre);
    }
});
