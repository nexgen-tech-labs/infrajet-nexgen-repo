# Firebase Authentication Testing Guide

## Prerequisites

### 1. Install Backend Dependencies
```bash
cd backend
pip install -r requirements.txt
# OR if using uv
uv pip install -r requirements.txt
```

### 2. Install Frontend Dependencies (Already Done)
```bash
cd frontend
npm install  # Already completed
```

## Step-by-Step Testing

### Step 1: Start Backend Server

Open **Terminal 1**:
```bash
cd /Users/hitesh/Documents/gitrepos/nexgentechlabs/infrajet-nexgen-repo/backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Will watch for changes in these directories: ['/path/to/backend']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

✅ **Verify:** Open http://localhost:8000/health in browser - should return health status

---

### Step 2: Start Frontend Server

Open **Terminal 2**:
```bash
cd /Users/hitesh/Documents/gitrepos/nexgentechlabs/infrajet-nexgen-repo/frontend
npm run dev
```

**Expected Output:**
```
VITE v5.4.1  ready in XXX ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

✅ **Verify:** Note the port (usually 5173 or 8080)

---

### Step 3: Test Sign Up Flow

1. **Open the application** in your browser:
   - Go to the URL shown by Vite (e.g., http://localhost:5173)

2. **Navigate to Sign Up page** (if not already there)

3. **Create a test account:**
   - Email: `test@example.com`
   - Password: `Test123456` (at least 6 characters)
   - Full Name: `Test User`

4. **Click "Sign Up"**

**Expected Results:**
- ✅ Toast notification: "Sign up successful"
- ✅ User should be automatically signed in
- ✅ Redirected to authenticated page/dashboard

**Check Browser Console (F12):**
```javascript
// Should see Firebase initialization
Runtime config loaded: { FIREBASE_API_KEY: "AIza...", ... }
```

**Common Errors:**
- ❌ "Email already in use" → Use a different email
- ❌ "Password should be at least 6 characters" → Use longer password
- ❌ Firebase initialization error → Check console for details

---

### Step 4: Test Sign Out

1. **Find and click the Sign Out button** (usually in header/profile menu)

2. **Expected Results:**
   - ✅ Toast notification: "Signed out successfully"
   - ✅ Redirected to login/landing page
   - ✅ User state cleared

---

### Step 5: Test Sign In

1. **Navigate to Sign In page**

2. **Enter credentials:**
   - Email: `test@example.com`
   - Password: `Test123456`

3. **Click "Sign In"**

**Expected Results:**
- ✅ Toast notification: "Welcome back!"
- ✅ Successfully authenticated
- ✅ Access to protected routes

**Common Errors:**
- ❌ "Invalid email or password" → Check credentials
- ❌ "Too many failed attempts" → Wait a few minutes

---

### Step 6: Test Protected Routes

1. **While signed in**, try to access protected pages:
   - Dashboard
   - Projects
   - Profile
   - Any other authenticated routes

2. **Expected Results:**
   - ✅ Pages load successfully
   - ✅ User data displayed correctly

3. **Sign out and try to access protected pages**

**Expected Results:**
   - ✅ Redirected to login page
   - ✅ `AuthGuard` component working

---

### Step 7: Test Backend Token Verification

**Check Backend Logs (Terminal 1):**

When you sign in, you should see logs like:
```
INFO: Request completed successfully
  request_id: ...
  method: GET/POST
  path: /api/v1/...
  status_code: 200
```

**Test API Call with Token:**

1. **Get Firebase Token** (from browser console):
```javascript
// Run this in browser console after signing in
const auth = getAuth();
auth.currentUser.getIdToken().then(token => console.log(token));
```

2. **Test API with curl:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN_HERE" \
     http://localhost:8000/api/v1/projects
```

**Expected Result:**
- ✅ Status 200 with data (if you have projects)
- ✅ Backend logs show authenticated request

**Without Token:**
```bash
curl http://localhost:8000/api/v1/projects
```

**Expected Result:**
- ✅ Status 401 Unauthorized
- ✅ Error: "Missing or invalid Authorization header"

---

## Verification Checklist

- [ ] Backend starts without errors
- [ ] Frontend starts without errors
- [ ] Firebase config loads correctly
- [ ] Sign Up creates new user successfully
- [ ] Sign In authenticates existing user
- [ ] Sign Out clears authentication
- [ ] Protected routes are guarded
- [ ] Backend verifies Firebase tokens
- [ ] API calls include Firebase token
- [ ] Token refresh works automatically

---

## Troubleshooting

### Frontend Issues

**"Firebase has not been initialized"**
```bash
# Check that config.json has all Firebase credentials
cat frontend/public/config.json
```

**"Network request failed"**
- Check that backend is running on port 8000
- Verify CORS settings in backend
- Check browser console for CORS errors

**"Invalid API key"**
- Verify Firebase API key in config.json
- Check Firebase Console project settings

### Backend Issues

**"Module not found: uvicorn"**
```bash
cd backend
pip install -r requirements.txt
```

**"Invalid authentication credentials"**
- Check Firebase Admin SDK initialization
- Verify FIREBASE_PROJECT_ID in backend settings
- Check GCP service account permissions

**CORS Errors**
- Check backend CORS middleware
- Verify frontend URL in FRONTEND_URL setting

### Firebase Console Checks

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select project: `infrajet-nexgen-fb-55585-e9543`
3. **Authentication → Sign-in method**:
   - ✅ Email/Password should be **enabled**
4. **Authentication → Users**:
   - Should see newly created users

---

## Success Criteria

✅ **All tests pass** → Firebase authentication is fully working!

🎉 **You should be able to:**
- Create new accounts
- Sign in with existing accounts
- Access protected routes
- Make authenticated API calls
- Sign out successfully

---

## Next Steps After Testing

If all tests pass:
1. Test with real user workflows
2. Set up Firebase Security Rules
3. Configure email verification (optional)
4. Set up password reset flow (optional)
5. Add social auth providers (Google, GitHub, etc.) if needed

If tests fail:
1. Check error messages in browser console
2. Check backend logs for errors
3. Verify Firebase configuration
4. Review this testing guide for missed steps
