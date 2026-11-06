# Auth0 setup

Login uses Auth0 (Regular Web Application) with Google. A UW Google account signs in through UW NetID and Duo. Only `@uw.edu` / `@washington.edu` accounts are allowed.

Dashboard labels may differ slightly from the steps below.

## 1. Tenant and application

1. Create a free Auth0 tenant.
2. **Settings** (tenant) → *Friendly Name*: `Campus Pulse` (shown on the login page).
3. **Applications → Create Application** → name `Campus Pulse`, type **Regular Web Applications**.
4. In the application's **Settings**:
   - *Allowed Callback URLs*: `http://localhost:3000/auth/callback, https://css382-dyop.vercel.app/auth/callback`
   - *Allowed Logout URLs*: `http://localhost:3000, https://css382-dyop.vercel.app`
   - *Allowed Web Origins*: `http://localhost:3000, https://css382-dyop.vercel.app`
5. In the application's **Connections** tab: enable **google-oauth2**, and disable **Username-Password-Authentication**.

Auth0's built-in Google development keys are fine for testing. For production, create a Google Cloud OAuth client and enter its keys under **Authentication → Social → Google**.

## 2. UW-only Action

1. **Actions → Library → Build Custom**: name `UW only login`, trigger **Login / Post Login**.
2. Paste the code from [`actions/uw-only-login.js`](actions/uw-only-login.js) and click **Deploy**.
3. **Actions → Triggers → post-login**: drag `UW only login` into the flow and click **Apply**.

## 3. Environment variables (frontend)

| Variable | Local (`frontend/.env.local`) | Vercel (Production) |
|---|---|---|
| `AUTH0_DOMAIN` | the application's *Domain* | same |
| `AUTH0_CLIENT_ID` | the application's *Client ID* | same |
| `AUTH0_CLIENT_SECRET` | the application's *Client Secret* | same |
| `AUTH0_SECRET` | `openssl rand -hex 32` | a **different** `openssl rand -hex 32` |
| `APP_BASE_URL` | `http://localhost:3000` | `https://css382-dyop.vercel.app` |

Remove the old v2 variables `AUTH0_BASE_URL` and `AUTH0_ISSUER_BASE_URL` from Vercel.

If the Auth0 variables are missing, public pages still work and only `/auth/*` returns 503 (see `frontend/proxy.ts`).

## 4. Check

1. In `frontend/`, run `npm run dev` and open http://localhost:3000.
2. Sign in with a UW Google account. You should go through UW NetID + Duo and come back signed in.
3. Sign in with a non-UW Google account. Auth0 should refuse it.
