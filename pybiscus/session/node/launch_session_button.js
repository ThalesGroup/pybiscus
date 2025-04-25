
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

    const options_set = {};
    const options_lock = [];

    raw_data.forEach(([key, _, value]) => {
        options_set[key] = value;
        options_lock.push(key);
    });

    data = {
        options_set,
        options_lock
    };    

    console.log( data );

    // JSON parameter encoding
    const paramStr = encodeURIComponent(JSON.stringify(data));

    // allow back function
    //window.location.href = `/server/config?param=${paramStr}`

    window.location.replace(`/server/config?param=${paramStr}`)
});
