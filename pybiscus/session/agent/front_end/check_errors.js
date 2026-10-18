// Shows each Pydantic error of a failed check under the field of the form it is about.
//
// A Pydantic location holds segments the form names do not: the tag of the chosen variant of a
// union ('model', 'mnist_cnn', 'config', 'hidden' for the input named 'model.config.hidden').
// A name therefore matches a location when its segments appear in it in order, the others skipped.

const pybiscusCheckErrors = (function () {

  const IGNORED = '[data-pybiscus-status="ignored"]';

  // the inputs traverseDOM reads: the inactive tabs and the list templates are left out
  function effectiveInputs(root) {
    return Array.from(root.querySelectorAll('[data-pybiscus-name]')).filter(input =>
      !input.closest(IGNORED) && !input.closest('.pybiscus-dict-key'));
  }

  // position of each list item holding the input, outermost first: the '#' of its name, in order
  function listIndices(input) {
    const indices = [];
    let item = input.closest('.pybiscus-list-content');
    while (item) {
      const siblings = Array.from(item.parentElement.querySelectorAll(':scope > .pybiscus-list-content'));
      indices.unshift(siblings.indexOf(item));
      item = item.parentElement.closest('.pybiscus-list-content');
    }
    return indices;
  }

  function segmentMatches(segment, locPart) {
    const isIndex = typeof locPart === 'number';
    if (segment === '#') return isIndex;
    if (segment === '@') return !isIndex;   // key of a dict
    return !isIndex && segment === locPart;
  }

  // depth: name segments found in the location, in order; rest: location segments after the last one
  function match(input, loc) {
    const segments = input.getAttribute('data-pybiscus-name').split('.');
    const indices = listIndices(input);
    let j = 0, depth = 0, listLevel = 0;
    for (const segment of segments) {
      let found = -1;
      for (let k = j; k < loc.length; k++) {
        if (segmentMatches(segment, loc[k])) { found = k; break; }
      }
      if (found === -1) break;
      if (segment === '#' && loc[found] !== indices[listLevel++]) break;   // another item of the list
      j = found + 1;
      depth++;
    }
    return { depth, rest: loc.slice(j), leaf: depth === segments.length && j === loc.length };
  }

  function commonAncestor(elements) {
    let ancestor = elements[0];
    while (ancestor && !elements.every(e => ancestor.contains(e))) ancestor = ancestor.parentElement;
    return ancestor;
  }

  // the input, or the fieldset of the deepest part of the location the form has
  function locate(root, loc) {
    const matches = effectiveInputs(root).map(input => ({ input, ...match(input, loc) }));
    const leaf = matches.find(m => m.leaf);
    if (leaf) return { input: leaf.input };
    const depth = Math.max(0, ...matches.map(m => m.depth));
    if (depth === 0) return null;
    const deepest = matches.filter(m => m.depth === depth);
    const ancestor = commonAncestor(deepest.map(m => m.input));
    const fieldset = ancestor && ancestor.closest('fieldset');
    return fieldset ? { fieldset, rest: deepest[0].rest } : null;
  }

  function message(text) {
    const div = document.createElement('div');
    div.className = 'pybiscus-field-error';
    div.textContent = text;
    return div;
  }

  function clear(root) {
    root.querySelectorAll('.pybiscus-field-error').forEach(e => e.remove());
    root.querySelectorAll('.pybiscus-field-invalid').forEach(e => e.classList.remove('pybiscus-field-invalid'));
    root.querySelectorAll('.pybiscus-fieldset-invalid').forEach(e => e.classList.remove('pybiscus-fieldset-invalid'));
  }

  // the first error is in a section the level-1 menu may hide
  function reveal(element) {
    const section = element.closest('fieldset.foldable');
    if (section && section.id) {
      const item = document.querySelector(`.menu-item-level-1[data-target="${section.id}"]`);
      if (item && !item.classList.contains('active')) item.click();
    }
    element.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }

  // returns the errors no field of the form matches, for the caller to show elsewhere
  function show(root, errors) {
    clear(root);
    const unplaced = [];
    let first = null;
    for (const error of errors) {
      const place = locate(root, error.loc);
      if (!place) { unplaced.push(`${error.loc.join('.')}: ${error.msg}`); continue; }
      if (place.input) {
        const field = place.input.closest('.pybiscus-field') || place.input.parentElement;
        field.classList.add('pybiscus-field-invalid');
        place.input.insertAdjacentElement('afterend', message(error.msg));
        first = first || place.input;
      } else {
        const legend = place.fieldset.querySelector(':scope > legend');
        const text = place.rest.length ? `${place.rest.join('.')}: ${error.msg}` : error.msg;
        place.fieldset.classList.add('pybiscus-fieldset-invalid');
        (legend || place.fieldset.firstChild).insertAdjacentElement(legend ? 'afterend' : 'beforebegin', message(text));
        first = first || place.fieldset;
      }
    }
    if (first) reveal(first);
    return unplaced;
  }

  // a corrected value no longer carries the message of the previous check
  document.addEventListener('input', event => {
    const field = event.target.closest && event.target.closest('.pybiscus-field-invalid');
    if (!field) return;
    field.classList.remove('pybiscus-field-invalid');
    field.querySelectorAll(':scope > .pybiscus-field-error').forEach(e => e.remove());
  });

  return { show, clear, locate };
})();
