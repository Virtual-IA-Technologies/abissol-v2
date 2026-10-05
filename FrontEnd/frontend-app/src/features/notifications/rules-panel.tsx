import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { ActionButton } from '@/components/action-button';
import { SearchableSelect, SearchableMultiSelect } from '@/components/searchable-select';
import { notificationsAPI, type RuleConfiguration, type RecipientRule } from './api';
import type { NotificationType } from './types';

export function NotificationRulesPanel({ types }: { types: NotificationType[] }) {
  const [config, setConfig] = useState<RuleConfiguration|null>(null), [saving, setSaving] = useState(false);
  useEffect(() => { let active=true; void notificationsAPI.rules().then(result=>{if(active)setConfig(result);}).catch(()=>{if(active)toast.error('No se pudieron cargar las reglas');}); return()=>{active=false;}; }, []);
  const change=(key:string,recipients:RecipientRule)=>setConfig(current=>current?{...current,rules:{...current.rules,[key]:{...current.rules[key],recipients}}}:current);
  const save=async()=>{if(!config)return;setSaving(true);try{await notificationsAPI.saveRules(config.rules);setConfig(await notificationsAPI.rules());toast.success('Reglas actualizadas');}catch{toast.error('No se pudieron guardar las reglas');}finally{setSaving(false);}};
  return <section className="space-y-3 rounded-xl border p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-medium">Destinatarios de avisos</h2><p className="text-xs text-muted-foreground">Las reglas respetan los permisos y la privacidad del registro. El autor no recibe su propio aviso.</p></div><ActionButton tone="edit" disabled={!config||saving} onClick={()=>void save()}>Guardar reglas</ActionButton></div>
    {!config?<p className="text-sm text-muted-foreground">Cargando reglas…</p>:types.map(type=>{
      const rule=config.rules[type.event_type];if(!rule)return null;
      return <div key={type.event_type} className="flex flex-wrap items-center gap-3 border-t pt-3"><div className="min-w-48 flex-1"><p className="text-sm">{type.label}</p><p className="text-xs text-muted-foreground">{type.source} · Plataforma</p></div><SearchableSelect value={rule.recipients.kind} onValueChange={kind=>change(type.event_type,{kind:kind as RecipientRule['kind'],ids:[]})} options={[{value:'eligible',label:'Usuarios con acceso'},{value:'administrators',label:'Programador'},...(type.event_type.startsWith('calendar_events.')?[{value:'participants',label:'Participantes del evento'}]:[]),{value:'roles',label:'Roles específicos'},{value:'users',label:'Usuarios específicos'}]} />
        {(rule.recipients.kind==='users'||rule.recipients.kind==='roles')&&<SearchableMultiSelect values={rule.recipients.ids.map(String)} onValuesChange={ids=>change(type.event_type,{...rule.recipients,ids:ids.map(Number)})} options={(rule.recipients.kind==='users'?config.users:config.roles).map(person=>({value:String(person.id),label:person.name}))} />}
      </div>;
    })}
  </section>;
}
