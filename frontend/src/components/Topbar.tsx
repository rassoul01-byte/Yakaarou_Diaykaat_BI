import { Activity, RefreshCw } from "lucide-react";

import { navItems, type Page } from "./navigation";

type Props = {
  page: Page;
  onNavigate: (page: Page) => void;
  onRecharger: () => void;
  apiOnline: boolean | null;
};

/** La barre unique : marque, navigation et état, en haut.
 *
 * Elle remplace la barre latérale. Sur un tableau de bord qui tient en trois
 * pages, une colonne entière de navigation coûte de la largeur sans rien
 * apporter — et la largeur, ici, sert aux graphiques. */
export default function Topbar({ page, onNavigate, onRecharger, apiOnline }: Props) {
  return (
    <header className="topbar">
      <div className="topbar-gauche">
        <a
          className="marque"
          href="#tableau"
          onClick={(e) => {
            e.preventDefault();
            onNavigate("dashboard");
          }}
        >
          <span className="marque-pastille">
            <Activity size={19} />
          </span>
          <span className="marque-nom">
            Leeral<span> · Yakaarou Diaykaat BI</span>
          </span>
        </a>

        <nav className="topnav" aria-label="Navigation principale">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`topnav-item ${page === item.id ? "actif" : ""}`}
              onClick={() => onNavigate(item.id)}
              aria-current={page === item.id ? "page" : undefined}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="topbar-droite">
        <span className={`etat ${apiOnline ? "etat-vert" : apiOnline === false ? "etat-rouge" : ""}`}>
          <span className="etat-point" />
          {apiOnline === null ? "Vérification…" : apiOnline ? "API opérationnelle" : "API injoignable"}
        </span>

        <button className="bouton-recharger" onClick={onRecharger}>
          <RefreshCw size={15} />
          Recharger
        </button>
      </div>
    </header>
  );
}
