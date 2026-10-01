
const launch_session_button = document.getElementById('launch-session-button');

// add an button event listener
launch_session_button.addEventListener('click', function() {

    // Select top-div ided element
    const topDiv = document.getElementById('top-div');

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
    // a manager setting too, not an option to select
    const share_row = raw_data.find(row => row[0] === 'share_cpu_threads');
    const share_cpu_threads = share_row ? share_row[1] === true || share_row[1] === 'true' : false;
    const min_clients_row = raw_data.find(row => row[0] === 'min_clients');
    const min_clients = min_clients_row ? Number(min_clients_row[1]) : null;
    const new_data = raw_data.filter(row => ! exclude.includes(row[0]) && ! is_partition(row) && ! is_holdout(row) && row !== share_row && row !== min_clients_row);
    const partition_rows = raw_data.filter(is_partition);
    const data_partition = partition_rows.length
        ? Object.fromEntries(partition_rows.map(([key, value]) => [key.slice('data_partition.'.length), value]))
        : null;
    const holdout_rows = raw_data.filter(is_holdout);
    const data_holdout = holdout_rows.length
        ? Object.fromEntries(holdout_rows.map(([key, value]) => [key.slice('data_holdout.'.length), value]))
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
    };    

    // console.log( server_data );

    window.parent.postMessage({ type: "session_config", value: server_data }, "*");
});
