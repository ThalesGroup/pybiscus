
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
    data = traverseDOM(topDiv, []).reverse();

    console.log( data );

    // Encodage du paramètre JSON pour l'URL
    const paramStr = encodeURIComponent(JSON.stringify(data));

    // allow back function
    //window.location.href = `http://localhost:5000/server/config?param=${paramStr}`

    window.location.replace(`http://localhost:5000/server/config?param=${paramStr}`)
});
