// ============================================================
//  app.js  —  Nellis Auction Monitor UI
//  Handles: Firebase Auth (GitHub), Firestore CRUD, Run Now
// ============================================================

const auth = firebase.auth();
const db   = firebase.firestore();

const provider = new firebase.auth.GithubAuthProvider();

// ---- DOM refs ----
const loadingScreen = document.getElementById('loading-screen');
const loginScreen   = document.getElementById('login-screen');
const appScreen     = document.getElementById('app-screen');
const loginBtn      = document.getElementById('login-btn');
const logoutBtn     = document.getElementById('logout-btn');
const userNameEl    = document.getElementById('user-name');
const userAvatarEl  = document.getElementById('user-avatar');
const statusBar     = document.getElementById('status-bar');
const statusMsg     = document.getElementById('status-msg');
const newTermInput  = document.getElementById('new-term-input');
const addTermBtn    = document.getElementById('add-term-btn');
const termsList     = document.getElementById('terms-list');
const termsCount    = document.getElementById('terms-count');
const termsEmpty    = document.getElementById('terms-empty');
const runBtn        = document.getElementById('run-btn');
const runStatus     = document.getElementById('run-status');
const patInput      = document.getElementById('pat-input');
const patToggle     = document.getElementById('pat-toggle');

// ---- State ----
let currentUser = null;
let termsUnsubscribe = null;

// ===========================
//  SCREEN HELPERS
// ===========================
function showScreen(name) {
  loadingScreen.classList.add('hidden');
  loginScreen.classList.add('hidden');
  appScreen.classList.add('hidden');
  document.getElementById(name + '-screen').classList.remove('hidden');
}

function showStatus(msg, duration = 4000) {
  statusMsg.textContent = msg;
  statusBar.classList.remove('hidden');
  if (duration > 0) setTimeout(() => statusBar.classList.add('hidden'), duration);
}

function setRunStatus(msg, type) {
  runStatus.textContent = msg;
  runStatus.className = 'run-status ' + type;
  runStatus.classList.remove('hidden');
}

// ===========================
//  AUTH
// ===========================
loginBtn.addEventListener('click', () => {
  auth.signInWithPopup(provider).catch(err => {
    console.error(err);
    alert('Sign-in failed: ' + err.message);
  });
});

logoutBtn.addEventListener('click', () => {
  if (termsUnsubscribe) termsUnsubscribe();
  auth.signOut();
});

auth.onAuthStateChanged(user => {
  if (user) {
    currentUser = user;
    onUserSignedIn(user);
  } else {
    currentUser = null;
    if (termsUnsubscribe) { termsUnsubscribe(); termsUnsubscribe = null; }
    showScreen('login');
  }
});

async function onUserSignedIn(user) {
  // Update header
  userNameEl.textContent = user.displayName || user.email || 'User';
  if (user.photoURL) {
    userAvatarEl.src = user.photoURL;
    userAvatarEl.style.display = 'block';
  }

  // Ensure user profile doc exists
  const profileRef = db.collection('users').doc(user.uid).collection('meta').doc('profile');
  await profileRef.set({
    displayName: user.displayName || '',
    email: user.email || '',
    photoURL: user.photoURL || '',
    githubLogin: user.reloadUserInfo?.screenName || '',
    lastLogin: firebase.firestore.FieldValue.serverTimestamp()
  }, { merge: true });

  showScreen('app');
  loadPAT();
  subscribeToTerms(user.uid);
}

// ===========================
//  TERMS — FIRESTORE
// ===========================
function termsRef(uid) {
  return db.collection('users').doc(uid).collection('alerts');
}

function subscribeToTerms(uid) {
  termsUnsubscribe = termsRef(uid)
    .orderBy('createdAt', 'asc')
    .onSnapshot(snapshot => {
      renderTerms(snapshot.docs);
    }, err => {
      console.error('Firestore error:', err);
      showStatus('⚠ Failed to load terms: ' + err.message);
    });
}

function renderTerms(docs) {
  termsList.innerHTML = '';
  termsCount.textContent = docs.length;

  if (docs.length === 0) {
    termsEmpty.classList.remove('hidden');
    return;
  }
  termsEmpty.classList.add('hidden');

  docs.forEach(doc => {
    const data = doc.data();
    const li = document.createElement('li');
    li.className = 'term-item';
    li.dataset.id = doc.id;

    li.innerHTML = `
      <span class="term-text">${escapeHtml(data.term)}</span>
      <button class="term-delete" title="Remove" data-id="${doc.id}">✕</button>
    `;
    termsList.appendChild(li);
  });

  // Delete buttons
  termsList.querySelectorAll('.term-delete').forEach(btn => {
    btn.addEventListener('click', () => deleteTerm(btn.dataset.id));
  });
}

async function addTerm() {
  if (!currentUser) return;
  const term = newTermInput.value.trim();
  if (!term) return;

  addTermBtn.disabled = true;
  try {
    // Check for duplicate
    const existing = await termsRef(currentUser.uid)
      .where('term', '==', term).limit(1).get();

    if (!existing.empty) {
      showStatus(`"${term}" is already in your list.`);
      return;
    }

    await termsRef(currentUser.uid).add({
      term,
      createdAt: firebase.firestore.FieldValue.serverTimestamp(),
      active: true
    });
    newTermInput.value = '';
    showStatus(`Added "${term}" ✓`);
  } catch (err) {
    console.error(err);
    showStatus('Failed to add term: ' + err.message);
  } finally {
    addTermBtn.disabled = false;
    newTermInput.focus();
  }
}

async function deleteTerm(docId) {
  if (!currentUser) return;
  if (!confirm('Remove this search term?')) return;
  try {
    await termsRef(currentUser.uid).doc(docId).delete();
    showStatus('Term removed.');
  } catch (err) {
    console.error(err);
    showStatus('Failed to remove term: ' + err.message);
  }
}

// ===========================
//  ADD TERM — UI
// ===========================
addTermBtn.addEventListener('click', addTerm);
newTermInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') addTerm();
});

// ===========================
//  PAT — localStorage
// ===========================
const PAT_KEY = 'nellis_github_pat';

function loadPAT() {
  const saved = localStorage.getItem(PAT_KEY) || '';
  patInput.value = saved;
}

patInput.addEventListener('change', () => {
  localStorage.setItem(PAT_KEY, patInput.value.trim());
});

patToggle.addEventListener('click', () => {
  if (patInput.type === 'password') {
    patInput.type = 'text';
    patToggle.textContent = 'Hide';
  } else {
    patInput.type = 'password';
    patToggle.textContent = 'Show';
  }
});

// ===========================
//  RUN NOW — GitHub API
// ===========================
runBtn.addEventListener('click', async () => {
  const pat = patInput.value.trim();
  if (!pat) {
    setRunStatus('⚠ Please enter your GitHub Personal Access Token first.', 'err');
    return;
  }
  // Save PAT
  localStorage.setItem(PAT_KEY, pat);

  runBtn.disabled = true;
  setRunStatus('⏳ Triggering GitHub Action…', 'info');

  try {
    const res = await fetch(
      `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${GITHUB_WORKFLOW_FILE}/dispatches`,
      {
        method: 'POST',
        headers: {
          'Authorization': `token ${pat}`,
          'Accept': 'application/vnd.github+json',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ ref: 'master' })
      }
    );

    if (res.status === 204) {
      setRunStatus('✅ Scraper triggered! Check your GitHub Actions tab — it will start in a moment.', 'ok');
    } else if (res.status === 401) {
      setRunStatus('❌ Invalid token. Make sure your PAT has the "repo" or "workflow" scope.', 'err');
    } else if (res.status === 404) {
      setRunStatus('❌ Workflow not found. Check that scraper.yml exists on the master branch.', 'err');
    } else {
      const body = await res.text();
      setRunStatus(`❌ GitHub returned ${res.status}: ${body}`, 'err');
    }
  } catch (err) {
    setRunStatus('❌ Network error: ' + err.message, 'err');
  } finally {
    runBtn.disabled = false;
  }
});

// ===========================
//  UTILS
// ===========================
function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
