import { Film, FolderCog, Images, LibraryBig, Settings as SettingsIcon } from "lucide-react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { LibraryPage } from "./pages/LibraryPage";
import { MediaPage } from "./pages/MediaPage";
import { SettingsPage } from "./pages/SettingsPage";

export default function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Images size={22} /></div>
          <div><strong>mediuxarr</strong><span>MediUX → Kometa</span></div>
        </div>
        <nav>
          <NavLink to="/media"><Film size={18} /> Medien</NavLink>
          <NavLink to="/libraries"><LibraryBig size={18} /> Bibliotheken</NavLink>
          <NavLink to="/settings"><SettingsIcon size={18} /> Einstellungen</NavLink>
        </nav>
        <div className="sidebar-note">
          <FolderCog size={18} />
          <p>Assets werden unverändert gespeichert. Kometa rendert beim nächsten Lauf die Overlays.</p>
        </div>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/media" element={<MediaPage />} />
          <Route path="/libraries" element={<LibraryPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/media" replace />} />
        </Routes>
      </main>
    </div>
  );
}
