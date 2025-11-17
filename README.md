# Reddit Vote Remover

A simple web app to bulk remove your Reddit upvotes and downvotes.

## Why?

Sometimes you want to clean up your Reddit voting history. This tool makes it easy.

## Features

- Remove all upvotes, downvotes, or both
- Real-time progress updates
- Clickable links to each post
- Works with any Reddit account

## How to Use

1. Visit [reddit-vote-remover](https://owaissafa.github.io/reddit-vote-remover/)
2. Get your Reddit session cookies (Press F12 → Network → Copy cookie header from any reddit.com request)
3. Enter your Reddit username
4. Choose what to remove (upvotes, downvotes, or both)
5. Click "Start Removal"
6. **Important:** Log out of Reddit after you're done to invalidate your session cookies

## Security

- Your credentials are only used in-memory during processing
- Nothing is stored permanently
- All communication happens over HTTPS
- Open source - review the code yourself

## Tech Stack

- **Frontend:** Vanilla JavaScript, Socket.IO, GitHub Pages
- **Backend:** Python, Flask, Flask-SocketIO, Gevent

## Local Development

### Frontend
```bash
cd frontend
python -m http.server 8080
```

### Backend
```bash
cd backend
pip install -r requirements.txt
cp env.example .env
# Edit .env with your settings
python app.py
```

## Deployment

- Frontend deploys automatically to GitHub Pages via GitHub Actions
- Backend can be deployed to any server with Docker support

## Disclaimer

This tool is not affiliated with Reddit Inc. Use at your own risk. Removing votes cannot be undone.

## License

MIT License - See [LICENSE](LICENSE) file for details.

