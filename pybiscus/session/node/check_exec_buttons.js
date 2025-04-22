
const check_button = document.getElementById('check-config-button');

// add an button event listener
check_button.addEventListener('click', function() {

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

    //console.log( data );

    // target URL for posting configuration
    const url_conf = "/config/MODEL_NAME/json";

    // request options
    const options = {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(data)
    };

    // post the configuration in json format
    fetch(url_conf, options)
      .then(response => {
        if (!response.ok) {
          throw new Error("Post error " + response.status);
        }
        return response.json();
      })
      .then(data => {
        console.log("Server response:", data);

        indicatorDiv.style.display = 'none';
        successResultDiv.style.display = 'block';
        failureResultDiv.style.display = 'none';
      })
      .catch(error => {
        console.error("Error:", error);

        indicatorDiv.style.display = 'none';
        successResultDiv.style.display = 'none';
        failureResultDiv.style.display = 'block';
      });
});

const execute_button = document.getElementById('execute-button');

// add an button event listener
execute_button.addEventListener('click', function() {

    const indicatorDiv = document.getElementById('execute-indicator');
    const successResultDiv = document.getElementById('execute-success-result');
    const failureResultDiv = document.getElementById('execute-failure-result');

    indicatorDiv.style.display = 'block';
    successResultDiv.style.display = 'none';
    failureResultDiv.style.display = 'none';
    
    // target URL for posting configuration
    const url_conf = "/ACTION";

    // request options
    const options = {
      method: "GET",
    };

    // post the configuration in json format
    fetch(url_conf, options)
      .then(response => {
        if (!response.ok) {
          throw new Error("Get error " + response.status);
        }
        return response.json();
      })
      .then(data => {
        console.log("ACTION response:", data);

        indicatorDiv.style.display = 'none';
        successResultDiv.style.display = 'block';
        failureResultDiv.style.display = 'none';
      })
      .catch(error => {
        console.error("Error:", error);
        
        indicatorDiv.style.display = 'none';
        successResultDiv.style.display = 'none';
        failureResultDiv.style.display = 'block';
      });
});
