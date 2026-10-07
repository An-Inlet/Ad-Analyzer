const endpoint = '/api/customer/v1/session';
const options = {credentials: 'same-origin', redirect: 'error', cache: 'no-store'};
const unavailable = () => new Error('Google sign-in is not configured.');

export async function prepareSignIn(fetcher = globalThis.fetch, loader = () => import('./firebase-auth.mjs')) {
  const response = await fetcher('/api/customer/v1/auth-config', options);
  if (!response.ok) throw unavailable();
  const config = await response.json();
  if (!config.enabled) return null;
  if (config.providers?.length !== 1 || config.providers[0] !== 'google.com' ||
      !/^[a-z][a-z0-9-]{4,28}[a-z0-9]$/.test(config.firebase?.projectId) ||
      config.firebase.authDomain !== `${config.firebase.projectId}.firebaseapp.com`) throw unavailable();
  const sdk = await loader();
  let busy = false;
  return async (cookies = globalThis.document?.cookie || '') => {
    if (busy) throw new Error('A sign-in attempt is already in progress.');
    busy = true;
    let app, auth, token, result;
    let exchangeStarted = false;
    try {
      // A failed/unknown logout must not turn into a second identity exchange.
      const existing = await fetcher(endpoint, options);
      if (existing.ok) {
        const csrf = cookies.split(';').map(v => v.trim()).find(v => v.startsWith('__Host-inlet_csrf='))?.split('=')[1];
        if (!/^[A-Za-z0-9_-]{43}$/.test(csrf || '')) throw new Error('Sign out before changing accounts.');
        const revoked = await fetcher(endpoint, {...options, method: 'DELETE', headers: {'X-CSRF-Token': csrf}});
        if (!revoked.ok) throw new Error('Sign-out could not be confirmed. Check Session Again.');
      } else if (existing.status !== 401) throw new Error('Your session could not be checked. Try again later.');
      app = sdk.initializeApp(config.firebase, 'inlet-signin-' + crypto.randomUUID());
      auth = sdk.initializeAuth(app, {persistence: sdk.inMemoryPersistence});
      const provider = new sdk.GoogleAuthProvider();
      provider.setCustomParameters({prompt: 'select_account'});
      result = await sdk.signInWithPopup(auth, provider, sdk.browserPopupRedirectResolver);
      token = await result.user.getIdToken(true);
      exchangeStarted = true;
      const exchanged = await fetcher(endpoint, {...options, method: 'POST',
        headers: {'Accept': 'application/json', 'Content-Type': 'application/json', 'X-Inlet-Request': '1'},
        body: JSON.stringify({id_token: token})});
      if (!exchanged.ok) throw new Error('Sign-in was not completed. Check Session Again before retrying.');
      await exchanged.json();
    } catch (error) {
      // Provider errors can contain identity/token material: never display their text.
      throw new Error(exchangeStarted
        ? 'Sign-in outcome could not be confirmed. Check Session Again before starting a new sign-in.'
        : 'Sign-in could not be completed. Check your session and allow the Google popup before retrying.');
    } finally {
      token = undefined; result = undefined;
      let cleanupFailed = false;
      try { if (auth) await sdk.signOut(auth); } catch { cleanupFailed = true; }
      try { if (app) await sdk.deleteApp(app); } catch { cleanupFailed = true; }
      auth = undefined; app = undefined; busy = false;
      if (cleanupFailed) throw new Error('Sign-in cleanup could not be confirmed. Reload this page and check your session.');
    }
  };
}
