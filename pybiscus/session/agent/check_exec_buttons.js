
const check_button = document.getElementById('check-config-button');

// add an button event listener
check_button.addEventListener('click', function() {

    const execute_indicatorDiv = document.getElementById('execute-indicator');
    const execute_successResultDiv = document.getElementById('execute-success-result');
    const execute_failureResultDiv = document.getElementById('execute-failure-result');

    execute_indicatorDiv.style.display = 'none';
    execute_successResultDiv.style.display = 'none';
    execute_failureResultDiv.style.display = 'none';

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
    const url_conf = "/config/{{modelName}}/json";

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

    const check_indicatorDiv = document.getElementById('check-indicator');
    const check_successResultDiv = document.getElementById('check-success-result');
    const check_failureResultDiv = document.getElementById('check-failure-result');

    check_indicatorDiv.style.display = 'none';
    check_successResultDiv.style.display = 'none';
    check_failureResultDiv.style.display = 'none';

    const indicatorDiv = document.getElementById('execute-indicator');
    const successResultDiv = document.getElementById('execute-success-result');
    const failureResultDiv = document.getElementById('execute-failure-result');

    indicatorDiv.style.display = 'block';
    successResultDiv.style.display = 'none';
    failureResultDiv.style.display = 'none';
    
    // target URL for posting configuration
    const url_conf = "/{{action}}";

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
        console.log("{{action}} response:", data);

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

const saveButton = document.getElementById('save-config-button');

saveButton.addEventListener('click', function() {

  // Select top-div element
  const topDiv = document.getElementById('top-div');

  data = traverseDOM(topDiv, []).reverse();

  // console.log( data );

  // target URL for posting configuration
  const url_conf = "/config/json/to_yaml";

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
      if ('success' in data) {

        // console.log('json to yaml Success:', data.success);

        async function saveFileWithPicker_only(text) {
          const options = {
            types: [{
              description: 'Yaml Files',
              accept: { 'text/yaml': ['.yml'] },
            }],
            suggestedName: 'config.yml',
          };
        
          try {
            const handle = await window.showSaveFilePicker(options);
            const writable = await handle.createWritable();
            await writable.write(text);
            await writable.close();
          } catch (err) {
            console.error("Save error :", err);
          }
        }

        async function saveFileWithPicker(text) {
          const options = {
            types: [{
              description: 'YAML Files',
              accept: { 'text/yaml': ['.yml'] },
            }],
            suggestedName: 'config.yml',
          };
        
          // convert the text to Blob
          const blob = new Blob([text], { type: 'text/yaml' });
        
          // try showSaveFilePicker
          if (window.showSaveFilePicker) {
            try {
              const handle = await window.showSaveFilePicker(options);
              const writable = await handle.createWritable();
              await writable.write(blob);
              await writable.close();
              console.log("✅ Saved file picker");
              return;
            } catch (err) {
              console.warn("⚠️ File picker error", err.message);
              // try fallback
            }
          }
        
          // Fallback : simulated download
          const a = document.createElement('a');
          const url = URL.createObjectURL(blob);
          a.href = url;
          a.download = options.suggestedName || 'download.yml';
          document.body.appendChild(a);
          a.click();
          a.remove();
          URL.revokeObjectURL(url);
          console.log("✅ Downloaded file using fallback");
        }
        
        saveFileWithPicker(data.success);

      } else if ('error' in data) {
        console.error('Error:', data.error);
      } else {
        console.warn('Unexpected response:', data);
      }      
    })
    .catch(error => {
      console.error("Error:", error);
    });
});

function showAlert() {
  alert("Not yet implemented");
}

const loadButton = document.getElementById('load-config-button');

loadButton.addEventListener('click', showAlert);
