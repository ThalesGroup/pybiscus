
// access to buttons by id

const origin_button  = document.getElementById('origin-config-button');
const check_button   = document.getElementById('check-config-button');
const execute_button = document.getElementById('execute-button');
const pin_Button     = document.getElementById('pin-config-button');
const blank_Button   = document.getElementById('blank-config-button');

check_button.disabled   = false;
execute_button.disabled = true;

// Blank et Pin partagent le même emplacement (col 5) : un seul s'affiche selon l'origine
// de la config (updateOrigin). Masqués au départ tant que l'origine n'est pas connue.
blank_Button.style.display = 'none';
pin_Button.style.display   = 'none';

// ***********************************************************************************************
// ********** Origin config button ***************************************************************
// ***********************************************************************************************

function updateOrigin() {
  fetch('/server/config/pin', { method: 'HEAD' })
    .then(res => {
      if (res.ok) {

        // config lue depuis le cache -> proposer de la vider (Blank)
        origin_button.innerHTML = '<span class="emoji">🗂️</span> Config is read from cache';
        blank_Button.style.display = '';
        pin_Button.style.display   = 'none';

      } else if (res.status === 404) {

        // config générée dynamiquement -> proposer de l'épingler en cache (Pin)
        origin_button.innerHTML = '<span class="emoji">⚙️</span> Config is dynamically generated';
        blank_Button.style.display = 'none';
        pin_Button.style.display   = '';

      } else {
        origin_button.innerHTML = '<span class="emoji">❓</span> Config has unknown origin';
      }
    });
}

updateOrigin()

// ***********************************************************************************************
// ********** Check config button ****************************************************************
// ***********************************************************************************************

// add an button event listener
check_button.addEventListener('click', function() {

    const execute_indicatorDiv     = document.getElementById('execute-indicator');
    const execute_successResultDiv = document.getElementById('execute-success-result');
    const execute_failureResultDiv = document.getElementById('execute-failure-result');

    execute_indicatorDiv.style.display     = 'none';
    execute_successResultDiv.style.display = 'none';
    execute_failureResultDiv.style.display = 'none';

    const indicatorDiv     = document.getElementById('check-indicator');
    const successResultDiv = document.getElementById('check-success-result');
    const failureResultDiv = document.getElementById('check-failure-result');

    indicatorDiv.style.display     = 'block';
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

        indicatorDiv.style.display     = 'none';
        successResultDiv.style.display = 'block';
        failureResultDiv.style.display = 'none';

        execute_button.disabled = false;
      })
      .catch(error => {
        console.error("Error:", error);

        indicatorDiv.style.display     = 'none';
        successResultDiv.style.display = 'none';
        failureResultDiv.style.display = 'block';
      });
});

// ***********************************************************************************************
// ********** Execute config button **************************************************************
// ***********************************************************************************************

// add an button event listener
execute_button.addEventListener('click', function() {

    check_button.disabled   = true;
    execute_button.disabled = true;

    const check_indicatorDiv     = document.getElementById('check-indicator');
    const check_successResultDiv = document.getElementById('check-success-result');
    const check_failureResultDiv = document.getElementById('check-failure-result');

    check_indicatorDiv.style.display     = 'none';
    check_successResultDiv.style.display = 'none';
    check_failureResultDiv.style.display = 'none';

    const indicatorDiv     = document.getElementById('execute-indicator');
    const successResultDiv = document.getElementById('execute-success-result');
    const failureResultDiv = document.getElementById('execute-failure-result');

    indicatorDiv.style.display     = 'block';
    successResultDiv.style.display = 'none';
    failureResultDiv.style.display = 'none';
    
    // target URL for posting configuration
    const url_conf = "/{{action}}";

    // request options
    const options = {
      method: "GET",
    };

    // ask the backend to start the run, then leave the configuration page
    fetch(url_conf, options)
      .then(response => {
        if (!response.ok) {
          throw new Error("Get error " + response.status);
        }
        return response.json();
      })
      .then(data => {
        console.log("{{action}} response:", data);

        indicatorDiv.style.display     = 'none';
        successResultDiv.style.display = 'block';
        failureResultDiv.style.display = 'none';

        window.location.href = data.monitor || "/run";
      })
      .catch(error => {
        console.error("Error:", error);

        indicatorDiv.style.display = 'none';
        successResultDiv.style.display = 'none';
        failureResultDiv.style.display = 'block';

        check_button.disabled = false;
      });
});

// ***********************************************************************************************
// ********** Save config button *****************************************************************
// ***********************************************************************************************

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

// ***********************************************************************************************
// ********** Pin config button ******************************************************************
// ***********************************************************************************************

function savePageState() {

    fetch("/server/config/pin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state: pybiscusPinnedState.capture() })
    }).then(res => {
        if (res.ok) {
          alert("Configuration pinned !");
          updateOrigin()
        }
    });
}

pin_Button.addEventListener('click', savePageState);

// ***********************************************************************************************
// ********** Blank config button ****************************************************************
// ***********************************************************************************************

function deletePinnedConfig() {

  return fetch('/server/config/pin', {
    method: 'DELETE'
  })
  .then(response => {
    if (!response.ok) throw new Error("HTTP error " + response.status);
    return response.json();
  })
  .then(data => {
    alert("Pinned configuration deletion result: " + data.status + ", configuration is going to be blanked");
    return true;
  })
  .catch(error => {
    console.error("Pinned configuration deletion error :", error);
    alert("Error while deleting the pinned configuration.");
    return false;
  });
}

async function blankConfig() {
  // reloading before the answer let Firefox abort the DELETE: the pinned configuration came back
  if (!await deletePinnedConfig()) return;

  // base URL with existing _nocache parameter erased
  const url = new URL(window.location.href);
  url.searchParams.delete('_nocache');          // suppress existing
  url.searchParams.set('_nocache', Date.now()); // add a new one

  // force URL reload
  window.location.href = url.toString();
}


blank_Button.addEventListener('click', blankConfig);
