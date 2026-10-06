import { useSearchParams } from "react-router-dom";
import { Mail, MessageCircle, Settings2 } from "lucide-react";
import { UnderlineTabs } from "@/components/underline-tabs";
import SmtpPanel from "@/pages/settings-panels/smtp-panel";
import WhatsappPanel from "@/pages/settings-panels/whatsapp-panel";
import { EmissionSettings } from "./business-workspace-panels";

export function BusinessConfiguration() {
  const [params,setParams]=useSearchParams();
  const requested=params.get("channel") || "general";
  const channel=["general","email","whatsapp"].includes(requested) ? requested : "general";
  return <div className="space-y-5"><UnderlineTabs label="Configuración de emisiones y canales" value={channel} onChange={value=>setParams({tab:"settings",channel:value})} tabs={[
    {value:"general",label:"Parámetros de emisiones",icon:<Settings2 className="size-4"/>},
    {value:"email",label:"Correo",icon:<Mail className="size-4"/>},
    {value:"whatsapp",label:"WhatsApp",icon:<MessageCircle className="size-4"/>},
  ]}>{channel==="general"?<EmissionSettings/>:channel==="email"?<SmtpPanel/>:<WhatsappPanel/>}</UnderlineTabs></div>;
}
