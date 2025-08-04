
  function fixPybiscusTabs(item) {
      const tabContainers = item.querySelectorAll('.pybiscus-tab-container');

      tabContainers.forEach((container, containerIndex) => {
          const buttonGroups = container.querySelectorAll('.pybiscus-tab-buttons');
          const contentGroups = container.querySelectorAll('.pybiscus-tab-content');

          // generate an uniq base id for this container
          const baseId = `tab-${Date.now()}-${Math.floor(Math.random() * 10000)}-${containerIndex}`;
          console.log(`baseId: ${baseId}`);

          contentGroups.forEach((contentEl, i) => {
              // generate a new unique id for this content
              const newId = `${baseId}-${i}`;
              console.log(`content id: ${contentEl.id} -> ${newId}`);
              contentEl.id = newId;

              // find the associated button (same rank in ).pybiscus-tab-buttons)
              buttonGroups.forEach(buttonGroup => {
                  const buttons = buttonGroup.querySelectorAll('.pybiscus-tab-button');
                  if (buttons[i]) {
                      console.log(`button tab-id: ${buttons[i].dataset.tab} -> ${newId}`);
                      buttons[i].setAttribute('data-tab', newId);
                  }
              });
          });
      });
  }

  function renum_list_config(container) {
    const contents = container.querySelector('.pybiscus-list-contents');
    if (!contents) return;

    const listItems = contents.querySelectorAll('.pybiscus-list-content');

    listItems.forEach((item, index) => {

        console.log(`renum ${index}`)

        const config = item.querySelector('.pybiscus-config');
        if (config) {
            config.innerHTML = index;
        }

        // update data-pybiscus-prefix attributes
        const elementsWithPrefix = item.querySelectorAll('[data-pybiscus-prefix]');
        elementsWithPrefix.forEach(el => {
            const rawPrefix = el.getAttribute('data-pybiscus-prefix');
            if (rawPrefix) {
                const newPrefix = rawPrefix.replace('#', index);
                el.setAttribute('data-pybiscus-prefix', newPrefix);
                console.log(`prefix update: ${rawPrefix} -> ${newPrefix}`)
            }
        });

        // update data-pybiscus-prefix attributes
        const elementsWithPrefix2 = item.querySelectorAll('[data-pybiscus-name]');
        elementsWithPrefix2.forEach(el => {
            const rawPrefix = el.getAttribute('data-pybiscus-name');
            if (rawPrefix) {
                const newPrefix = rawPrefix.replace('#', index);
                el.setAttribute('data-pybiscus-name', newPrefix);
                console.log(`name update: ${rawPrefix} -> ${newPrefix}`)
            }
        });
      });
  }

  function renameRadioButtons(container) {

    // console.log(`rename buttons of ${container.outerHTML}`)
    let nameMap = {}

    // select all container inputs with class pybiscus-radiobutton set
    const inputs = container.querySelectorAll('input.pybiscus_radiobutton');

    inputs.forEach(input => {
        const originalName = input.name;

        // console.log(`* button of ${originalName}`)

        // get the associated name if it already exists
        if (!nameMap[originalName]) {

            // otherwise generate a uniq one
            const uniqueName = `option-${Date.now()}-${Math.floor(Math.random() * 10000)}-${originalName}`;

            nameMap[originalName] = uniqueName;
        }

        // rename the radio button input
        input.name = nameMap[originalName];

        console.log( `button name ${originalName} -> ${input.name}`);

        // init : set callback and parent's div status
        newRadioButtonInit( input );
    });
}

  document.querySelectorAll('.pybiscus-list-generator').forEach(generator => {

      generator.addEventListener('click', () => {

        // go up to parent fieldset
        const container = generator.closest('.pybiscus-list-fs');
        if (!container) return;

        // access internal elements
        const contents = container.querySelector('.pybiscus-list-contents');
        const template = container.querySelector('.pybiscus-list-template');
        if (!contents || !template) return;
   
        // create .pybiscus-list-content container
        const newContent = document.createElement('div');
        newContent.classList.add('pybiscus-list-content');
    
        // create suppress button
        const eraser = document.createElement('label');
        eraser.classList.add('pybiscus-list-eraser');
        eraser.textContent = '➖📝';
    
        // 🔁 add suppress callback
        eraser.addEventListener('click', () => {
          newContent.remove();

          renum_list_config( container );
        });
    
        // clone .pybiscus-list-template children
        // console.log(`list mngt ${template.classList}`)
        const templateChildren = Array.from(template.children).map(child => child.cloneNode(true));
    
        // gather elements
        templateChildren.forEach(clone => newContent.appendChild(clone));

        // find newContent first chid
        const firstChild = newContent.firstElementChild;

        // access first child .pybiscus-config element
        const configField = firstChild?.querySelector('.pybiscus-config');

        if (configField && configField.parentNode) {
          // insert eraser after .pybiscus-config
          configField.parentNode.insertBefore(eraser, configField.nextSibling);
        } else {
          // Fallback : if not found, prepend it
          newContent.prepend(eraser);
        }
          
        // renum tab and tab contents
        fixPybiscusTabs(newContent);

        // rename radio buttons
        renameRadioButtons(newContent);
      
        // set click callback on new contents
        newContent.querySelectorAll('.pybiscus-tab-container').forEach(handlePybiscusTabContainer);

        // insert into .pybiscus-list-contents
        contents.appendChild(newContent);

        renum_list_config( container );
      });
    });
  