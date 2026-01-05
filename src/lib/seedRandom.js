const stringHash = (str) => {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i += 1) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
};

export const mulberry32 = (seed) => {
  return function random() {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
};

export const createSeededRandom = (seedString) => {
  const seed = stringHash(seedString);
  const base = mulberry32(seed);
  return {
    next: () => base(),
    nextInt: (min, max) => Math.floor(base() * (max - min + 1)) + min,
    pick: (list) => list[Math.floor(base() * list.length)],
  };
};
