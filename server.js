// server.js

// 1. MODULE IMPORTS (ESM Syntax)
import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';
import { createClient } from "@libsql/client";
import { promises as fsPromises } from 'fs';

// 2. SETUP
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const isVercel = process.env.VERCEL === '1';

// --- 2. CONFIGURATION & INITIALIZATION ---
const app = express();
const PORT = process.env.PORT || 3000;

// Configure CORS for all routes
app.use(cors());

// Parse JSON and URL-encoded data
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve static files from the 'public' directory
app.use(express.static(path.join(__dirname, 'public'), {
  setHeaders: (res, path) => {
    // Set proper cache headers for static assets
    if (path.endsWith('.html')) {
      res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    } else {
      res.setHeader('Cache-Control', 'public, max-age=31536000');
    }
  }
}));

// Get connection details from environment variables
const dbUrl = process.env.TURSO_DATABASE_URL;
const dbAuthToken = process.env.TURSO_AUTH_TOKEN;

// Initialize the libSQL client
let db;
if (dbUrl && dbAuthToken) {
  db = createClient({
    url: dbUrl,
    authToken: dbAuthToken
  });
  console.log('Turso database client initialized');
} else {
  console.warn('Turso database configuration not found. Some features may not work.');
}

// --- 3. MIDDLEWARE ---
// (CORS and JSON parsing already set up above)

// --- 4. API ENDPOINTS ---

/**
 * GET /api/test
 * Tests the database connection by running a simple query.
 */
app.get('/api/test', async (req, res) => {
    try {
        // Run a simple, harmless query to test the connection
        await db.execute("SELECT 1");
        res.json({
            status: "success",
            message: "Database connection test successful."
        });
    } catch (error) {
        // This is where you would catch the ConnectTimeoutError
        console.error("Database connection test failed:", error.message);
        res.status(500).json({
            status: "error",
            message: "Database connection test failed.",
            detail: error.message,
            // If it's a timeout, provide a specific hint
            hint: error.code === 'UND_ERR_CONNECT_TIMEOUT' ? "Check network, firewall, or TURSO_AUTH_TOKEN validity." : "Check server logs for details."
        });
    }
});

/**
 * GET /api/search?query=...
 * Searches posts/data using a user-provided query term.
 */
app.get('/api/search', async (req, res) => {
    const searchTerm = req.query.query;

    if (!searchTerm) {
        return res.status(400).json({ status: "error", message: "Missing 'query' search parameter." });
    }

    // Sanitize the search term for SQL LIKE
    const queryTerm = `%${searchTerm}%`;

    try {
        // Use a positional placeholder (?) for security (SQL Injection prevention)
        const result = await db.execute({
            sql: "SELECT title, content, slug FROM blog_posts WHERE title LIKE ? OR content LIKE ?",
            args: [queryTerm, queryTerm],
            timeout: 5000
        });

        res.json({
            status: "success",
            count: result.rows.length,
            posts: result.rows.map(row => ({
                title: row.title,
                content: row.content,
                slug: row.slug
            }))
        });

    } catch (error) {
        console.error("Search query failed:", error);
        res.status(500).json({
            status: "error",
            message: "Failed to execute search query.",
            detail: error.message
        });
    }
});


// --- 5. SPECIFIC ROUTES ---
const servePages = async (req, res, next) => {
    const filePath = path.join(__dirname, 'pages.html');
    
    // If there's a slug, try to fetch the post from the database
    if (req.params.slug) {
        try {
            // Fetch the blog post with just the required fields
            const result = await db.execute({
                sql: "SELECT title, content FROM blog_posts WHERE slug = ?",
                args: [req.params.slug],
                timeout: 5000
            });

            if (result.rows.length > 0) {
                const post = result.rows[0];
                
                // Use current date for all posts
                const formattedDate = new Date().toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                });
                
                // Read the template file
                let template = await fs.promises.readFile(filePath, 'utf-8');
                
                // Replace placeholders with actual content
                template = template
                    // Update page title
                    .replace(/<title>[^<]*<\/title>/, `<title>${post.title} - Liveenity</title>`)
                    // Update main heading
                    .replace(/<h1 class="display-4 fw-bold mb-3 blog-title">[^<]*<\/h1>/, 
                            `<h1 class="display-4 fw-bold mb-3 blog-title">${post.title}</h1>`)
                    // Update post date
                    .replace(/<span class="post-date">[^<]*<\/span>/, 
                            `<span class="post-date">${formattedDate}</span>`)
                    // Update post content
                    .replace(/<div class="blog-content[\s\S]*?<\/div>/, 
                            `<div class="blog-content article-content text-start">${post.content}</div>`);
                
                return res.send(template);
            } else {
                // If no post found, serve 404 page
                return res.status(404).sendFile(path.join(__dirname, '404.html'), (err) => {
                    if (err) {
                        // If 404.html doesn't exist, send a simple 404 message
                        res.status(404).send('404 - Page not found');
                    }
                });
            }
        } catch (error) {
            console.error('Error fetching post:', error);
            // Continue to serve the default page if there's an error
        }
    }
    
    // If no slug or post not found, serve the default pages.html
    res.sendFile(filePath, { 
        headers: {
            'Content-Type': 'text/html; charset=UTF-8'
        },
        dotfiles: 'deny'
    }, (err) => {
        if (err) {
            console.error('Error serving pages.html:', err);
            if (err.code === 'ENOENT') {
                return res.status(404).send('pages.html not found');
            }
            return res.status(500).send('Error loading page');
        }
    });
};

// Handle both /pages and /pages/:slug with the same handler
app.get(['/pages', '/pages/:slug'], servePages);

// Keywords route
app.get('/keywords', async (req, res) => {
    try {
        const keywordsPath = path.join(__dirname, 'SCRAP', 'KEYWORDS.txt');
        let keywords = [];
        
        try {
            const data = await fsPromises.readFile(keywordsPath, 'utf8');
            keywords = data.split('\n').filter(k => k.trim() !== '');
        } catch (err) {
            console.error('Error reading keywords file:', err);
            // Continue with empty keywords array if file doesn't exist yet
        }
        
        res.send(`
            <!DOCTYPE html>
            <html>
            <head>
                <title>Manage Keywords</title>
                <style>
                    body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                    h1 { color: #333; }
                    textarea { width: 100%; height: 200px; margin: 10px 0; padding: 10px; }
                    button { padding: 8px 16px; background: #0070f3; color: white; border: none; border-radius: 4px; cursor: pointer; }
                    button:hover { background: #005bb5; }
                    .container { margin-top: 20px; }
                </style>
            </head>
            <body>
                <h1>Manage Keywords</h1>
                <form action="/keywords" method="POST">
                    <p>Enter one keyword per line:</p>
                    <textarea name="keywords" placeholder="Enter keywords, one per line">${keywords.join('\n')}</textarea>
                    <div>
                        <button type="submit">Save Keywords</button>
                    </div>
                </form>
                <div class="container">
                    <h3>Current Keywords (${keywords.length}):</h3>
                    <ul>${keywords.map(k => `<li>${k}</li>`).join('')}</ul>
                </div>
            </body>
            </html>
        `);
    } catch (error) {
        console.error('Error in /keywords route:', error);
        res.status(500).send('Error loading keywords');
    }
});

app.post('/keywords', express.urlencoded({ extended: true }), async (req, res) => {
    try {
        const keywords = req.body.keywords;
        const keywordsPath = path.join(__dirname, 'SCRAP', 'KEYWORDS.txt');
        
        // Create directory if it doesn't exist
        await fsPromises.mkdir(path.dirname(keywordsPath), { recursive: true });
        
        // Save the keywords
        await fsPromises.writeFile(keywordsPath, keywords, 'utf8');
        
        res.redirect('/keywords?success=1');
    } catch (error) {
        console.error('Error saving keywords:', error);
        res.status(500).send('Error saving keywords');
    }
});

// API to trigger Python script
app.post('/api/run-keyword-search', express.json(), (req, res) => {
    const { keyword } = req.body;
    
    if (!keyword) {
        return res.status(400).json({ error: 'Keyword is required' });
    }

    const { spawn } = require('child_process');
    const pythonProcess = spawn('python', [
        path.join(__dirname, 'SCRAP', 'keyword_searcher.py'),
        '--keyword',
        keyword
    ]);

    let output = '';
    let errorOutput = '';

    pythonProcess.stdout.on('data', (data) => {
        output += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
        errorOutput += data.toString();
    });

    pythonProcess.on('close', (code) => {
        if (code !== 0) {
            console.error(`Python script exited with code ${code}`);
            console.error('Error output:', errorOutput);
            return res.status(500).json({
                error: 'Error running script',
                details: errorOutput
            });
        }
        
        res.json({
            success: true,
            output: output,
            message: 'Script executed successfully'
        });
    });
});

// API Endpoints for Keywords
app.get('/api/keywords', async (req, res) => {
    try {
        const keywordsPath = path.join(__dirname, 'SCRAP', 'KEYWORDS.txt');
        let keywords = [];
        
        try {
            const data = await fsPromises.readFile(keywordsPath, 'utf8');
            keywords = data.split('\n')
                         .map(k => k.trim())
                         .filter(k => k !== '');
        } catch (err) {
            if (err.code !== 'ENOENT') {
                console.error('Error reading keywords file:', err);
                return res.status(500).json({ error: 'Error reading keywords file' });
            }
            // If file doesn't exist, return empty array
        }
        
        res.json({ keywords });
    } catch (error) {
        console.error('Error in /api/keywords:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
});

app.post('/api/keywords', express.json(), async (req, res) => {
    try {
        const { keywords } = req.body;
        
        if (!Array.isArray(keywords)) {
            return res.status(400).json({ error: 'Keywords must be an array' });
        }
        
        const keywordsPath = path.join(__dirname, 'SCRAP', 'KEYWORDS.txt');
        const keywordsDir = path.dirname(keywordsPath);
        
        // Create directory if it doesn't exist
        try {
            await fsPromises.mkdir(keywordsDir, { recursive: true });
        } catch (err) {
            console.error('Error creating directory:', err);
            return res.status(500).json({ error: 'Error creating directory' });
        }
        
        // Save the keywords, one per line
        await fsPromises.writeFile(keywordsPath, keywords.join('\n'), 'utf8');
        
        res.json({ success: true });
    } catch (error) {
        console.error('Error saving keywords:', error);
        res.status(500).json({ error: 'Error saving keywords' });
    }
});

// Serve keywords.html
app.get('/keywords', (req, res) => {
    res.sendFile(path.join(__dirname, 'SCRAP', 'keywords.html'));
});

// Serve sitemap.xml
app.get('/sitemap.xml', (req, res) => {
    const sitemapPath = path.join(__dirname, 'sitemap.xml');
    res.sendFile(sitemapPath, { 
        headers: {
            'Content-Type': 'application/xml'
        }
    }, (err) => {
        if (err) {
            console.error('Error serving sitemap.xml:', err);
            res.status(404).send('Sitemap not found');
        }
    });
});

// --- 6. CATCH-ALL ROUTE FOR CLIENT-SIDE ROUTING ---
app.get('*', (req, res) => {
    const indexPath = path.join(__dirname, 'index.html');
    
    // If the file exists, send it
    if (fs.existsSync(indexPath)) {
        return res.sendFile(indexPath);
    }
    
    // If file doesn't exist, send 404
    res.status(404).send('Not Found');
});

// --- 7. START SERVER ---
if (!isVercel) {
    // Start the server only if not running on Vercel
    app.listen(PORT, () => {
        console.log(`Server running on http://localhost:${PORT}`);
        console.log("API endpoints:");
        console.log(`- GET  /api/test - Test database connection`);
        console.log(`- GET  /api/search?query=your_search_term - Search posts`);
    });
}

// Export the Express app for Vercel
// This allows Vercel to use the app as a serverless function
export default app;