// Build only these SDK exports; application never uses default persistent getAuth().
export {initializeApp, deleteApp} from 'firebase/app';
export {initializeAuth, inMemoryPersistence, browserPopupRedirectResolver, GoogleAuthProvider, signInWithPopup, signOut} from 'firebase/auth';
