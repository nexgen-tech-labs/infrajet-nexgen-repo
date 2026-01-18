const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const distPath = path.join(__dirname, 'dist');

if (!fs.existsSync(distPath)) {
  console.warn('Warning: dist directory not found. Ensure `npm run build` has been executed before starting the server.');
}

app.use(express.static(distPath));

app.get('*', (req, res) => {
  const indexHtmlPath = path.join(distPath, 'index.html');

  if (!fs.existsSync(indexHtmlPath)) {
    res.status(500).send('Build output not found. Please run `npm run build` before starting the server.');
    return;
  }

  res.sendFile(indexHtmlPath);
});

const port = process.env.PORT || 8080;
app.listen(port, () => {
  console.log(`Server is running and serving dist/ on port ${port}`);
});
