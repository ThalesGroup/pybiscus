
  function fixPybiscusTabs(item) {
      const tabContainers = item.querySelectorAll('.pybiscus-tab-container');

      tabContainers.forEach((container, containerIndex) => {
          const buttonGroups = container.querySelectorAll('.pybiscus-tab-buttons');
          const contentGroups = container.querySelectorAll('.pybiscus-tab-content');

          // Générer un identifiant de base unique pour ce container
          const baseId = `tab-${Date.now()}-${Math.floor(Math.random() * 10000)}-${containerIndex}`;
          console.log(`baseId: ${baseId}`);

          contentGroups.forEach((contentEl, i) => {
              // Génère un nouvel ID unique pour ce contenu
              const newId = `${baseId}-${i}`;
              console.log(`content id: ${contentEl.id} -> ${newId}`);
              contentEl.id = newId;

              // Trouve le bouton correspondant (même rang dans les .pybiscus-tab-buttons)
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

        // set click callback on new contents
        newContent.querySelectorAll('.pybiscus-tab-container').forEach(handlePybiscusTabContainer);

        // insert into .pybiscus-list-contents
        contents.appendChild(newContent);

        renum_list_config( container );
      });
    });
  