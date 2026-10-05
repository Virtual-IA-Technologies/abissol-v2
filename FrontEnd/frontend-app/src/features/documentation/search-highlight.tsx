import { Fragment } from "react";
import { searchRanges } from "./search-text";

export function SearchHighlight({text, query}: {text: string; query: string}) {
  const ranges = searchRanges(text,query);
  let end = 0;
  const parts = ranges.map((range,i) => {
    const before = text.slice(end,range.start); end = range.end;
    return <Fragment key={i}>{before}<mark data-search-hit className="rounded-sm bg-sky-200 text-slate-950">{text.slice(range.start,range.end)}</mark></Fragment>;
  });
  return <>{parts}{text.slice(end)}</>;
}
