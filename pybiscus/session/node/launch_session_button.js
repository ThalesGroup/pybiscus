
const launch_session_button = document.getElementById('launch-session-button');

// add an button event listener
launch_session_button.addEventListener('click', function() {

    const indicatorDiv = document.getElementById('check-indicator');
    const successResultDiv = document.getElementById('check-success-result');
    const failureResultDiv = document.getElementById('check-failure-result');

    indicatorDiv.style.display = 'block';
    successResultDiv.style.display = 'none';
    failureResultDiv.style.display = 'none';

    // Select top-div ided element
    const topDiv = document.getElementById('top-div');

    // generate configuration data
    raw_data = traverseDOM(topDiv, []).reverse();

    console.log( raw_data );

    /*
    
    ssl
    */

    const server_host = raw_data.find(row => row[0] === 'network.server_host');
    const server_port = raw_data.find(row => row[0] === 'network.server_port');
    const server_listen_to = raw_data.find(row => row[0] === 'network.server_listen_to');
    const protocol    = raw_data.find(row => row[0] === 'network.protocol');

    const exclude = ['network.server_host', 'network.server_port', 'network.protocol', 'network.server_listen_to'];

    const new_data = raw_data.filter(row => !exclude.includes(row[0]));

    const listen_address = server_listen_to[2] === "the whole internet" ? "[::]" : "127.0.0.1";

    const values_set = { 
        'server_listen_address' : `${listen_address}:${server_port[2]}`,
        'server_address'        : `${server_host[2]}:${server_port[2]}`,
    };
    const values_lock = ['root_dir', 'server_listen_address', 'server_address'];
    const options_set = { };
    const options_lock = [];

    new_data.forEach(([key, _, value]) => {
        options_set[key] = value;
        options_lock.push(key);
    });

    const server_data = {
        options_set,
        options_lock,
        values_set,
        values_lock,
    };    

    console.log( server_data );

    // JSON parameter encoding
    const paramStr = encodeURIComponent(JSON.stringify(server_data));

    // allow back function
    //window.location.href = `/server/config?param=${paramStr}`

    window.location.replace(`/server/config?param=${paramStr}`)
});
