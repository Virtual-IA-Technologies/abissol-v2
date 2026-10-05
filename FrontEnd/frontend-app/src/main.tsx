import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./index.css";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { Toaster } from "@/components/ui/sonner";
import { ThemeProvider } from "./context/theme-context";
import { AppErrorBoundary } from "@/components/app-error-boundary";
import { PlatformSettingsProvider } from "@/context/PlatformSettingsContext";
import { NotificationProvider } from "@/features/notifications/notification-context";
import { UploadProgress } from '@/components/upload-progress';

//document.documentElement.classList.add('dark');

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <PlatformSettingsProvider>
      <BrowserRouter>
        <AuthProvider>
          <NotificationProvider>
            <ThemeProvider>
              <AppErrorBoundary>
                <Toaster />
                <UploadProgress />
                <App />
              </AppErrorBoundary>
            </ThemeProvider>
          </NotificationProvider>
        </AuthProvider>
      </BrowserRouter>
    </PlatformSettingsProvider>
  </StrictMode>,
);
