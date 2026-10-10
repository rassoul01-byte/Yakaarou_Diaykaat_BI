import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// La police, servie avec l'application. Avant, `index.html` la chargeait
// depuis fonts.googleapis.com : une requête tierce, bloquante au rendu, dont
// la page dépendait pour s'afficher. Ici le fichier est dans le paquet.
import '@fontsource-variable/familjen-grotesk'

import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
