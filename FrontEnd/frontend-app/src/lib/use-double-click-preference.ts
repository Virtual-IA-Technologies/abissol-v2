import { useEffect,useState } from "react";

export function useDoubleClickPreference<T extends string>(
  scope: string,
  allowed: readonly T[],
  fallback: T,
) {
  const storageKey = `abissol:double-click:${scope}`;
  const valid=allowed.filter(value=>value!=='none');
  const normalize=(value:T|null)=>value&&valid.includes(value)?value:valid.includes(fallback)?fallback:valid[0]??fallback;
  const read=()=>{try{return normalize(window.localStorage.getItem(storageKey) as T|null);}catch{return normalize(null);}};
  const [saved, setValueState] = useState<{key:string;value:T}>(() => ({key:storageKey,value:read()}));
  const value=saved.key===storageKey?normalize(saved.value):read();
  useEffect(()=>{const reload=()=>{try{const value=window.localStorage.getItem(storageKey) as T|null;if(value)setValueState({key:storageKey,value});}catch{/* Storage may be disabled by the browser. */}};window.addEventListener('storage',reload);return()=>window.removeEventListener('storage',reload);},[storageKey]);

  const setValue = (next: T) => {
    const value=normalize(next);setValueState({key:storageKey,value});
    try{window.localStorage.setItem(storageKey,value);}catch{/* Keep the in-memory preference. */}
  };

  return [value, setValue] as const;
}
