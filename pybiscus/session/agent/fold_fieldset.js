
    const legends = document.querySelectorAll('body > div > fieldset > div > fieldset ');

    legends.forEach((legend, index) => {
    legend.classList.add('foldable');
    if (index !== -1) {
        legend.classList.add('collapsed');
    }
    });

    // Fonction for folding all fieldsets except one
    function collapseOthers(except) {
    document.querySelectorAll('fieldset.foldable').forEach(fs => {
        if (fs !== except) {
        fs.classList.add('collapsed');
        }
    });
    }

    document.querySelectorAll('fieldset.foldable').forEach(fieldset => {

    const legend = fieldset.querySelector(':scope > legend');

    if (legend) {
        legend.addEventListener('click', () => {
        const isCollapsed = fieldset.classList.contains('collapsed');
        if (isCollapsed) {
            collapseOthers(fieldset);

            const divParent = fieldset.parentElement;
            const container = document.querySelector('#top-div > fieldset');
            container.appendChild(divParent);

            fieldset.classList.remove('collapsed');
        } else {
            fieldset.classList.add('collapsed');
        }
        });
    }
    });
