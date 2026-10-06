// one hue per bouquet name, the same in every page (the manager's, 3frames.html) and on every
// machine. FNV-1a then a final mix: with a plain polynomial hash, names differing by their last
// character (edge1, edge2) got neighbouring hues
function bouquetColor(name) {
    let h = 0x811c9dc5;
    for (const byte of new TextEncoder().encode(name)) {
        h = Math.imul(h ^ byte, 0x01000193);
    }
    h ^= h >>> 16; h = Math.imul(h, 0x85ebca6b);
    h ^= h >>> 13; h = Math.imul(h, 0xc2b2ae35);
    h ^= h >>> 16;
    return `hsl(${(h >>> 0) % 360} 70% 60%)`;
}
