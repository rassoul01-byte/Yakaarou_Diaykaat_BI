import { Menu, RefreshCw } from "lucide-react";

type Props = {
  titre: string;
  onOuvrirMenu: () => void;
  onRecharger: () => void;
};

export default function Topbar({ titre, onOuvrirMenu, onRecharger }: Props) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          className="icon-button mobile-menu"
          onClick={onOuvrirMenu}
          aria-label="Ouvrir le menu"
        >
          <Menu size={20} />
        </button>
        <div>
          <div className="eyebrow">ESPACE DE PILOTAGE</div>
          <h1>{titre}</h1>
        </div>
      </div>

      <div className="topbar-actions">
        <button className="refresh-button" onClick={onRecharger}>
          <RefreshCw size={16} />
          Recharger
        </button>
        <div className="avatar">MD</div>
      </div>
    </header>
  );
}
