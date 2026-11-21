// ============================================================
//  firebase-config.js
//  Replace the values below with your Firebase project config.
//  Get these from: Firebase Console → Project Settings → Your Apps → Web App
// ============================================================

const FIREBASE_CONFIG = {
  apiKey: "REPLACE_WITH_API_KEY",
  authDomain: "REPLACE_WITH_AUTH_DOMAIN",
  projectId: "REPLACE_WITH_PROJECT_ID",
  storageBucket: "REPLACE_WITH_STORAGE_BUCKET",
  messagingSenderId: "REPLACE_WITH_MESSAGING_SENDER_ID",
  appId: "REPLACE_WITH_APP_ID"
};

// GitHub repo info for triggering workflow_dispatch
const GITHUB_OWNER = "abhilashsandi";
const GITHUB_REPO  = "nellis-auction-monitor";
const GITHUB_WORKFLOW_FILE = "scraper.yml";

firebase.initializeApp(FIREBASE_CONFIG);
