export const AVATAR_PALETTE = [
  '#A47CE8', '#E87C9E', '#E8A47C', '#C8E87C', '#7CE8B4', '#7CC8E8',
  '#7C8EE8', '#B47CE8', '#E87CC8', '#D89472', '#9DB472', '#72B49D',
  '#729DB4', '#7C94D8', '#A47CD8', '#D87CA4', '#C49472', '#94C472',
  '#72C494', '#7294C4', '#9472C4', '#C47294', '#B8B272', '#72B8B2',
];

export function hashName(name) {
  const s = String(name || '');
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

export function colorForName(name) {
  return AVATAR_PALETTE[hashName(name) % AVATAR_PALETTE.length];
}

export function initialsFromName(name) {
  const s = String(name || '').trim();
  if (!s) return '?';
  return s.split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase();
}
