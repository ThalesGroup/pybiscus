
  function fixPybiscusTabs(item) {
      const tabContainers = item.querySelectorAll('.pybiscus-tab-container');

      tabContainers.forEach((container, containerIndex) => {
          // :scope > is mandatory here: a tab-content may itself hold a nested
          // tab-container (an included-model field, e.g. personalize's result_modifier).
          // A non-scoped query would flatten those nested buttons/contents into this
          // container's list, breaking the button[i] <-> content[i] pairing and leaving
          // the tabs placed after the nested one unreachable.
          const buttonGroups = container.querySelectorAll(':scope > .pybiscus-tab-buttons');
          const contentGroups = container.querySelectorAll(':scope > .pybiscus-tab-content');

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
                  const buttons = buttonGroup.querySelectorAll(':scope > .pybiscus-tab-button');
                  if (buttons[i]) {
                      console.log(`button tab-id: ${buttons[i].dataset.tab} -> ${newId}`);
                      buttons[i].setAttribute('data-tab', newId);
                  }
              });
          });
      });
  }

  function escapeRegExp(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function renum_list_config(container) {
    const contents = container.querySelector('.pybiscus-list-contents');
    if (!contents) return;

    // Base du chemin de CETTE liste = segment précédant le '#' du template. Permet de
    // ne ré-indexer que l'indice de cette liste (qu'il soit encore '#' ou déjà un nombre)
    // sans toucher aux indices des listes imbriquées, qui viennent plus loin dans le chemin.
    // NB: l'ancienne version faisait replace('#', index), qui ne trouvait plus rien une fois
    // l'item numéroté -> suppression au milieu / réordonnancement laissaient des indices
    // périmés (trous dans le YAML).
    const template = container.querySelector('.pybiscus-list-template');
    const probe = template && template.querySelector('[data-pybiscus-name*="#"], [data-pybiscus-prefix*="#"]');
    let re = null;
    if (probe) {
        const name = probe.getAttribute('data-pybiscus-name') || '';
        const path = name.indexOf('#') >= 0 ? name : (probe.getAttribute('data-pybiscus-prefix') || '');
        const hash = path.indexOf('#');
        if (hash >= 0) {
            re = new RegExp('^(' + escapeRegExp(path.slice(0, hash)) + ')(?:#|\\d+)');
        }
    }

    // items DIRECTS de cette liste (:scope > pour ignorer d'éventuelles listes imbriquées)
    const listItems = contents.querySelectorAll(':scope > .pybiscus-list-content');
    const n = listItems.length;

    listItems.forEach((item, index) => {

        // numéro affiché (toujours mis à jour)
        const config = item.querySelector('.pybiscus-config');
        if (config) {
            config.innerHTML = index;
        }

        // flèches masquées aux extrémités : pas de ↑ pour le premier, pas de ↓ pour le dernier
        if (item._moveUp)   item._moveUp.style.visibility   = (index === 0)     ? 'hidden' : '';
        if (item._moveDown) item._moveDown.style.visibility = (index === n - 1) ? 'hidden' : '';

        if (!re) return;

        // ré-indexation du segment de liste dans les chemins ; remplacement par fonction
        // (et non '$1'+index, qui produirait $10, $11... interprétés comme groupes)
        const reindex = (value) => value.replace(re, (m, g1) => g1 + index);

        item.querySelectorAll('[data-pybiscus-prefix]').forEach(el => {
            el.setAttribute('data-pybiscus-prefix', reindex(el.getAttribute('data-pybiscus-prefix')));
        });
        item.querySelectorAll('[data-pybiscus-name]').forEach(el => {
            el.setAttribute('data-pybiscus-name', reindex(el.getAttribute('data-pybiscus-name')));
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

        // move up / down buttons (réordonnancement) : déplacent le noeud puis renumérotent,
        // indispensable car la position dans le YAML vient de l'indice, pas de l'ordre DOM
        const moveUp = document.createElement('label');
        moveUp.classList.add('pybiscus-list-mover');
        moveUp.textContent = '⬆️';
        moveUp.addEventListener('click', () => {
          const prev = newContent.previousElementSibling;
          if (prev) {
            contents.insertBefore(newContent, prev);
            renum_list_config( container );
          }
        });

        const moveDown = document.createElement('label');
        moveDown.classList.add('pybiscus-list-mover');
        moveDown.textContent = '⬇️';
        moveDown.addEventListener('click', () => {
          const next = newContent.nextElementSibling;
          if (next) {
            contents.insertBefore(next, newContent);
            renum_list_config( container );
          }
        });

        // références sur l'item : renum_list_config masque ↑ au premier / ↓ au dernier
        // (sans confondre avec les flèches d'éventuelles listes imbriquées)
        newContent._moveUp = moveUp;
        newContent._moveDown = moveDown;
    
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
          // insert move/erase controls after .pybiscus-config (ordre : ⬆️ ⬇️ ➖)
          const ref = configField.nextSibling;
          configField.parentNode.insertBefore(moveUp, ref);
          configField.parentNode.insertBefore(moveDown, ref);
          configField.parentNode.insertBefore(eraser, ref);
        } else {
          // Fallback : if not found, prepend them
          newContent.prepend(eraser);
          newContent.prepend(moveDown);
          newContent.prepend(moveUp);
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

  // =========================================================================
  // Pré-allocation d'éléments par défaut dans certaines listes.
  // clé = data-pybiscus-prefix de la liste (sans le .#) ; valeur = noms d'onglets
  // (options) à pré-créer. Robuste aux plugins : liste absente -> ignorée ;
  // option indisponible (plugin non chargé) -> ignorée (aucun item bancal ajouté).
  // Ne pré-alloue que si la liste est vide (évite les doublons quand la config
  // vient du cache ou après un rechargement).
  // =========================================================================
  const PYBISCUS_LIST_DEFAULTS = {
    'server_run.loggers': ['WebHook'],
    'server_compute_context.metrics_loggers': ['WebHook'],
    'server_strategy.pipeline': ['MetricDiffCompute', 'TimeDiffCompute', 'VisualizeModelLayers'],
  };

  function listOptionAvailable(container, name){
    // le template contient l'union avec tous les onglets d'options disponibles
    return Array.from(container.querySelectorAll('.pybiscus-list-template .pybiscus-tab-button'))
      .some(b => b.textContent.trim() === name);
  }

  function preallocateListDefaults(){
    Object.entries(PYBISCUS_LIST_DEFAULTS).forEach(([prefix, options]) => {
      const probe = document.querySelector(
        `.pybiscus-list-template [data-pybiscus-prefix^="${prefix}.#"], .pybiscus-list-template [data-pybiscus-name^="${prefix}.#"]`);
      const container = probe && probe.closest('.pybiscus-list-fs');
      if (!container) return;                                        // liste absente (config/plugins)
      const contents   = container.querySelector('.pybiscus-list-contents');
      const generator  = container.querySelector('.pybiscus-list-generator');
      if (!contents || !generator || contents.children.length) return;   // absente ou déjà peuplée

      options.forEach(name => {
        if (!listOptionAvailable(container, name)) {
          console.warn(`[list-defaults] option '${name}' indisponible pour '${prefix}' (plugin absent ?) — ignorée`);
          return;                                                   // option absente -> rien ajouté
        }
        generator.click();                                          // ajoute via le mécanisme existant
        const idx = contents.children.length - 1;
        if (typeof set_option === 'function') set_option(`${prefix}.${idx}`, name);
      });
    });
  }

  preallocateListDefaults();
  