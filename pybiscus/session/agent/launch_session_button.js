
const launch_session_button = document.getElementById('launch-session-button');

// add an button event listener
launch_session_button.addEventListener('click', function() {

    const indicatorDiv     = document.getElementById('check-indicator');
    const successResultDiv = document.getElementById('check-success-result');
    const failureResultDiv = document.getElementById('check-failure-result');

    indicatorDiv.style.display     = 'block';
    successResultDiv.style.display = 'none';
    failureResultDiv.style.display = 'none';

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
    const new_data = raw_data.filter(row => ! exclude.includes(row[0]));

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
    };    

    // console.log( server_data );

    // JSON parameter encoding
    // TODO: params may become to long for parameters
    const paramStr = encodeURIComponent(JSON.stringify(server_data));

    // allow back function
    //window.location.href = `/server/config?param=${paramStr}`

    window.location.replace(`/server/config?param=${paramStr}`)
});
