export function searchRanges(text: string, query: string) {
  const normalize = (value: string) => value.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase("es-PE");
  const words = [...new Set(query.trim().split(/\s+/).slice(0,8).map(normalize).filter(Boolean))];
  if (!words.length) return [];
  let normalized = ""; const offsets: {start: number; end: number}[] = [];
  let index = 0;
  for (const char of text) {
    const value = normalize(char);
    for (let i = 0; i < value.length; i++) offsets.push({start: index, end: index + char.length});
    normalized += value; index += char.length;
  }
  const ranges: {start: number; end: number}[] = [];
  for (const word of words) {
    let from = 0; let found: number;
    while ((found = normalized.indexOf(word, from)) !== -1) {
      ranges.push({start: offsets[found].start, end: offsets[found + word.length - 1].end});
      from = found + word.length;
    }
  }
  return ranges.sort((a,b) => a.start - b.start).reduce<typeof ranges>((result, range) => {
    const last = result[result.length - 1];
    if (last && range.start <= last.end) last.end = Math.max(last.end, range.end);
    else result.push({...range});
    return result;
  }, []);
}
