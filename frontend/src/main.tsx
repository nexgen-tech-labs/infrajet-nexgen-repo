import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { loadRuntimeConfig } from './config';
import React from 'react';

loadRuntimeConfig().then((config) => {
  console.log('Runtime config loaded:', config);

  createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App config={config} />
    </React.StrictMode>
  );
});
