import { Palette } from "lucide-react";
import { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { MyAccountSheet } from '@/components/my-account-sheet';
import { ActionButton } from '@/components/action-button';

import GeneralPanel from "@/pages/settings-panels/general-panel";

export default function PersonalAppearancePage() {
  const [accountOpen,setAccountOpen]=useState(false);
  const {user}=useAuth();
  return <main className="space-y-5 p-5 md:p-7">
    <div>
      <div className="flex items-center gap-2">
        <Palette className="size-6 text-sky-600" />
        <h1 className="text-2xl font-semibold tracking-tight">Apariencia</h1>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">Personaliza cómo ves ABISSOL sin cambiar la configuración de otros usuarios.</p>
    </div>
    {user&&<ActionButton tone="edit" onClick={()=>setAccountOpen(true)}>Editar mis datos</ActionButton>}
    <MyAccountSheet open={accountOpen} onOpenChange={setAccountOpen}/>
    <GeneralPanel />
  </main>;
}
