const KEY = "kc-saved-offerings";

function read() {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(parsed) ? parsed.filter((id) => typeof id === "string") : [];
  } catch {
    return [];
  }
}

export function savedIds() {
  return read();
}

export function isSaved(id) {
  return read().includes(id);
}

export function toggleSaved(id) {
  const ids = read().filter((item) => item !== id);
  if (!isSaved(id)) ids.push(id);
  try {
    localStorage.setItem(KEY, JSON.stringify(ids));
  } catch {
    /* the button still reflects the in-memory attempt */
  }
  return ids.includes(id);
}
