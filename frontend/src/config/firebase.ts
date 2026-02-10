import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyAebTKXFjPBIGXp0eu6JwJMSRlygcQq-Kk",
  authDomain: "infrajet-nexgen-fb-55585-e9543.firebaseapp.com",
  projectId: "infrajet-nexgen-fb-55585-e9543",
  storageBucket: "infrajet-nexgen-fb-55585-e9543.firebasestorage.app",
  messagingSenderId: "805180795886",
  appId: "1:805180795886:web:8c60814253364a847d7cff"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Firebase Authentication and get a reference to the service
export const auth = getAuth(app);
