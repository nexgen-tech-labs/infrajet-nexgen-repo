import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import { loadRuntimeConfig } from './config';
import { initializeFirebase } from './lib/firebase';
import React from 'react';

loadRuntimeConfig().then((config) => {
  console.log('Runtime config loaded:', config);

  // Initialize Firebase with runtime config
  initializeFirebase({
    apiKey: config.FIREBASE_API_KEY,
    authDomain: config.FIREBASE_AUTH_DOMAIN,
    projectId: config.FIREBASE_PROJECT_ID,
    storageBucket: config.FIREBASE_STORAGE_BUCKET,
    messagingSenderId: config.FIREBASE_MESSAGING_SENDER_ID,
    appId: config.FIREBASE_APP_ID,
  });

  createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App config={config} />
    </React.StrictMode>
  );
});
