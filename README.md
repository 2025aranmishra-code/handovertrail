# HandoverTrail

HandoverTrail is a browser-based handover management prototype for teams and event committees.

It helps an outgoing team member organize information into:
- Decisions
- Risks
- Blockers
- Dependencies
- Next actions

The prototype includes a reviewer (Lead) workflow to generate a handover, review and approve claims, answer missing-information questions, and preview what a new member can see.

## Run locally

No build tools or installation are required.

1. Download or clone this repository.
2. Open `index.html` in a modern web browser.

For local hosting, you can also run:

```bash
python -m http.server 8000
```

Then visit http://localhost:8000.

## Deploy

This is a static HTML project. You can deploy the repository using GitHub Pages or a static hosting service such as Netlify.

### GitHub Pages

1. Push these files to a GitHub repository.
2. Open **Settings → Pages**.
3. Under **Build and deployment**, select **Deploy from a branch**.
4. Select your main branch and the `/ (root)` folder, then save.
5. Wait for GitHub Pages to publish the site.

## Demo data and limitations

The current prototype uses synthetic Tech Fest 2026 committee data embedded in the HTML file. It does not connect to a backend, database, authentication service, or live AI model. Review actions and generated handover state are held in browser memory and reset when the page is refreshed.

## Technologies

- HTML
- CSS
- Vanilla JavaScript
