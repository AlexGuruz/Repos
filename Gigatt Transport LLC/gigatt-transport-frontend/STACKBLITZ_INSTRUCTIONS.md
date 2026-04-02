# Run Gigatt Transport frontend on StackBlitz (no npm on your PC)

## Quick steps

1. **Open StackBlitz**  
   Go to: **https://stackblitz.com**

2. **Start a React project**  
   Click **“New project”** → choose **“React”** or **“Vite”** (React + TypeScript).  
   Wait until the project loads and the preview appears.

3. **Replace with the Gigatt app**  
   - In the **left file tree**, delete the default `src` folder (right‑click → Delete).  
   - Open this folder on your PC:  
     `E:\Repos\Gigatt Transport LLC\gigatt-transport-frontend\gigatt-transport`  
   - **Drag and drop** the **entire `gigatt-transport` folder** (or its contents: `src`, `public`, `package.json`, `tailwind.config.js`, `postcss.config.js`, `tsconfig.json`) into the StackBlitz file tree.  
   - If you drag the folder, drop it so the **root** of the project has `package.json` and `src/` at the top level.

4. **Install and run**  
   - StackBlitz usually runs `npm install` when it sees `package.json`.  
   - In the **Terminal** (bottom), run:  
     `npm start`  
   - The preview should refresh and show the Gigatt landing page.

5. **Open the app**  
   Use the **“Open in new tab”** (or preview) link so you can browse `/`, `/request`, and `/admin/login` (demo login: **admin** / **gigatt**).

---

## If your repo is on GitHub

If the Gigatt app is the **root** of a GitHub repo (so the repo contains `package.json`, `src/`, `public/` at the top):

**Open in StackBlitz and start the app:**

```
https://stackblitz.com/github/YOUR_USERNAME/YOUR_REPO_NAME?startScript=start
```

Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your GitHub user and repo. StackBlitz will clone the repo, install deps, and run `npm start`.

---

## Troubleshooting

- **Preview blank or errors**  
  Check the terminal for `npm install` / `npm start` errors. Fix any missing dependencies or TypeScript errors shown in the editor.

- **Tailwind / styles look wrong**  
  Ensure `tailwind.config.js`, `postcss.config.js`, and `src/index.css` (with Tailwind directives) are in the project and weren’t overwritten by the template.

- **Routes don’t work**  
  The app uses React Router; in StackBlitz the preview URL might need the full path (e.g. `/#/request` or the path the preview shows).
