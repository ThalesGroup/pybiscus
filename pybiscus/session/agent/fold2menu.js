
    // 2 level menu for managing foldable fieldsets
    document.addEventListener('DOMContentLoaded', function() {
        
        // init function
        function initializeTwoLevelMenu() {
            const menuItems = document.querySelectorAll('.menu-item-level-1');
            const foldableFieldsets = document.querySelectorAll('fieldset.foldable');

            if (foldableFieldsets.length === 0) {
                console.log('No fieldset.foldable found');
                return;
            }

            // menu item click management
            menuItems.forEach(item => {
                item.addEventListener('click', function(event) {
                    event.preventDefault();
                    
                    // remove .active from all menu items
                    menuItems.forEach(mi => mi.classList.remove('active'));
                    
                    // add .active to clicked item
                    this.classList.add('active');

                    // fetch target fieldset id
                    const targetId = this.getAttribute('data-target');
                    const targetFieldset = document.getElementById(targetId);
                    
                    if (targetFieldset && targetFieldset.classList.contains('foldable')) {
                        // manage collapsed classes on all fieldsets
                        handleFieldsetVisibility(targetFieldset);

                        // trigger a personnalised event for comptibility purpose
                        const customEvent = new CustomEvent('pybiscusMenuChange', {
                            detail: {
                                activeItem: this,
                                targetFieldset: targetFieldset,
                                fieldsetId: targetId
                            }
                        });
                        document.dispatchEvent(customEvent);
                    }
                });
            });
        }

        // function that creates the menu from existing fieldset
        function createMenuFromFieldsets() {
            const foldableFieldsets = document.querySelectorAll('fieldset.foldable');
            
            if (foldableFieldsets.length === 0) {
                console.log('No fieldset.foldable found for menu creation');
                return;
            }

            console.log(`menu creation for ${foldableFieldsets.length} fieldsets`);

            // create the container menu if needed
            let menuContainer = document.querySelector('.level-1-menu');
            if (!menuContainer) {
                menuContainer = document.createElement('div');
                menuContainer.className = 'level-1-menu';
                
                // insert the menu before the first fieldset
                const firstFieldset = foldableFieldsets[0];
                firstFieldset.parentNode.insertBefore(menuContainer, firstFieldset);
            }

            let firstSection = true;

            // cvreate the menu item for each fieldset
            foldableFieldsets.forEach((fieldset, index) => {
                const legend = fieldset.querySelector('legend');
                if (!legend) return;

                // make sure that the fieldset has an ID
                if (!fieldset.id) {
                    fieldset.id = `fieldset-${index}`;
                }

                // create the level 1 menu item
                const menuItem = document.createElement('div');
                menuItem.className = `menu-item-level-1 ${firstSection ? 'active' : ''}`;
                menuItem.setAttribute('data-target', fieldset.id);
                menuItem.innerHTML = legend.innerHTML;

                menuContainer.appendChild(menuItem);

                // initi the fieldsets collapsed states - force the first to visible
                if (firstSection) {
                    fieldset.classList.remove('collapsed');
                    fieldset.style.display = 'block';
                    console.log(`First fieldset ${fieldset.id} set visible`);
                } else {
                    fieldset.classList.add('collapsed');
                    fieldset.style.display = 'none';
                }

                firstSection = false;
            });

            console.log('initial fieldsets state set');
        }

        // Fonction pour gérer la visibilité des fieldsets
        function handleFieldsetVisibility(activeFieldset) {
            const allFoldableFieldsets = document.querySelectorAll('fieldset.foldable');
            
            // Ajouter la classe collapsed à tous les fieldsets sauf celui actif
            allFoldableFieldsets.forEach(fieldset => {
                if (fieldset === activeFieldset) {
                    fieldset.classList.remove('collapsed');
                } else {
                    fieldset.classList.add('collapsed');
                }
            });

            // Mettre à jour la visibilité
            updateFieldsetVisibility();
        }

        // Fonction pour mettre à jour la visibilité des fieldsets
        function updateFieldsetVisibility() {
            const foldableFieldsets = document.querySelectorAll('fieldset.foldable');
            let visibleCount = 0;
            
            foldableFieldsets.forEach(fieldset => {
                if (fieldset.classList.contains('collapsed')) {
                    // Masquer le fieldset collapsed
                    fieldset.style.display = 'none';
                    console.log(`Fieldset ${fieldset.id} hidden`);
                } else {
                    // Afficher le fieldset non collapsed
                    fieldset.style.display = 'block';
                    visibleCount++;
                    console.log(`Fieldset ${fieldset.id} visible`);
                }
            });
            
            // insure that one fieldset is visible
            if (visibleCount === 0 && foldableFieldsets.length > 0) {
                console.warn('No visible fieldset detected, force first one visibility');
                const firstFieldset = foldableFieldsets[0];
                firstFieldset.classList.remove('collapsed');
                firstFieldset.style.display = 'block';
                
                // update the corresponding menu
                const firstMenuItem = document.querySelector('.menu-item-level-1');
                if (firstMenuItem) {
                    document.querySelectorAll('.menu-item-level-1').forEach(item => item.classList.remove('active'));
                    firstMenuItem.classList.add('active');
                }
            }
            
            console.log(`${visibleCount} fieldset(s) visible on ${foldableFieldsets.length}`);
        }

        // function to maintain the compatibility with foldable system
        function maintainBackwardCompatibility() {
            // emulate the event old system
            document.addEventListener('pybiscusMenuChange', function(event) {
                const { fieldsetId, activeItem, targetFieldset } = event.detail;
                
                // trigger the same events kind than before
                const oldStyleEvent = new CustomEvent('fieldsetToggle', {
                    detail: {
                        fieldsetId: fieldsetId,
                        isExpanded: true,
                        legend: activeItem.textContent,
                        activeFieldset: targetFieldset
                    }
                });
                document.dispatchEvent(oldStyleEvent);
            });

            // global function for compatibility
            window.pybiscusNavigation = {
                goToFieldset: function(fieldsetId) {
                    const menuItem = document.querySelector(`[data-target="${fieldsetId}"]`);
                    if (menuItem) {
                        menuItem.click();
                    }
                },
                
                getCurrentFieldset: function() {
                    const activeFieldset = document.querySelector('fieldset.foldable:not(.collapsed)');
                    return activeFieldset ? activeFieldset.id : null;
                },
                
                getAllFieldsets: function() {
                    return Array.from(document.querySelectorAll('fieldset.foldable')).map(fs => ({
                        id: fs.id,
                        legend: fs.querySelector('legend')?.textContent || 'Sans titre',
                        isCollapsed: fs.classList.contains('collapsed')
                    }));
                }
            };
        }

        function initialize() {
            // check if the menu exists otherwise create it
            const existingMenu = document.querySelector('.level-1-menu');
            const foldableFieldsets = document.querySelectorAll('fieldset.foldable');

            if (existingMenu && existingMenu.children.length > 0) {
                // the menu already exists
                console.log('existing menu found, navigation init');
                // init fieldsets states - insure that one is visible
                let hasVisibleFieldset = false;
                foldableFieldsets.forEach((fieldset, index) => {
                    if (index === 0) {
                        fieldset.classList.remove('collapsed');
                        fieldset.style.display = 'block';
                        hasVisibleFieldset = true;
                        console.log(`First fieldset ${fieldset.id} set visible`);
                    } else {
                        fieldset.classList.add('collapsed');
                        fieldset.style.display = 'none';
                    }
                });
                
                if (!hasVisibleFieldset && foldableFieldsets.length > 0) {
                    console.warn('Force first fieldset visibility');
                    foldableFieldsets[0].classList.remove('collapsed');
                    foldableFieldsets[0].style.display = 'block';
                }
                
                initializeTwoLevelMenu();
            } else if (foldableFieldsets.length > 0) {
                // create menu from fieldset
                createMenuFromFieldsets();
                initializeTwoLevelMenu();
            } else {
                // no structure detected
                console.warn('No fieldset.foldable detected');
            }

            maintainBackwardCompatibility();

            // reshape for responsive
            let resizeTimer;
            window.addEventListener('resize', function() {
                clearTimeout(resizeTimer);
                resizeTimer = setTimeout(function() {
                    // Réajuster la navigation si nécessaire
                    const menu = document.querySelector('.level-1-menu');
                    if (menu && menu.scrollWidth > menu.clientWidth) {
                        menu.classList.add('scrollable');
                    } else if (menu) {
                        menu.classList.remove('scrollable');
                    }
                }, 250);
            });
        }

        // perform init
        initialize();

        // expose functions for debugging
        if (window.console && window.console.log) {
            window.pybiscusDebug = {
                reinitialize: initialize,
                createMenu: createMenuFromFieldsets,
                navigation: window.pybiscusNavigation,
                showFieldset: function(fieldsetId) {
                    window.pybiscusNavigation.goToFieldset(fieldsetId);
                }
            };
        }
    });

    // additional CSS for 2 levels menu and fieldsets
    const menuStyles = `
        .level-1-menu {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-bottom: 20px;
            padding: 10px;
            background-color: #f5f5f5;
            border-radius: 8px;
        }
        
        .menu-item-level-1 {
            padding: 10px 15px;
            background-color: #fff;
            border: 1px solid #ddd;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s ease;
            user-select: none;
        }
        
        .menu-item-level-1:hover {
            background-color: #e9f4ff;
            border-color: #0066cc;
        }
        
        .menu-item-level-1.active {
            background-color: #0066cc;
            color: white;
            border-color: #0066cc;
        }
        
        .level-1-menu.scrollable {
            overflow-x: auto;
            box-shadow: inset -10px 0 10px -10px rgba(0,0,0,0.1);
        }
        
        .level-1-menu.scrollable::after {
            content: '→';
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--color-gray-400);
            pointer-events: none;
        }
        
        fieldset.foldable:not(.collapsed) {
            animation: fadeIn 0.3s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
    `;

    // styles injection
    const styleSheet = document.createElement('style');
    styleSheet.textContent = menuStyles;
    document.head.appendChild(styleSheet);

