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
  },
  // Allow fallthrough for 404s so we can handle them with our custom 404 page
  fallthrough: true
}));

// --- 3. MIDDLEWARE & ROUTES ---

// Serve static files from the 'public' directory
app.use(express.static(path.join(__dirname, 'public'), {
  setHeaders: (res, path) => {
    // Set proper cache headers for static assets
    if (path.endsWith('.html')) {
      res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    } else {
      res.setHeader('Cache-Control', 'public, max-age=31536000');
    }
  },
  // Allow fallthrough for 404s so we can handle them with our custom 404 page
  fallthrough: true
}));

// Explicit route for keywords.html
app.get('/keywords', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'keywords.html'));
});

// Define servePages function
const servePages = async (req, res, next) => {
    const filePath = path.join(__dirname, 'public', 'pages.html');
    
    // If there's a slug, try to fetch the post from the database
    if (req.params.slug) {
        try {
            // Check if database is initialized
            if (!db) {
                console.error('Database not initialized. Check your TURSO_DATABASE_URL and TURSO_AUTH_TOKEN in .env file');
                throw new Error('Database not initialized');
            }
            
            console.log(`Fetching post with slug: ${req.params.slug}`);
            // Fetch the blog post with existing columns
            const result = await db.execute({
                sql: "SELECT title, content, slug FROM blog_posts WHERE slug = ?",
                args: [req.params.slug],
                timeout: 5000
            });
            
            console.log(`Found ${result.rows.length} post(s) with slug: ${req.params.slug}`);

            if (result.rows.length > 0) {
                const post = result.rows[0];
                // Read the template file
                let template = await fs.promises.readFile(filePath, 'utf-8');
                
                console.log(`Serving blog post: ${post.title} (${post.slug})`);
                
                // Update page title
                template = template.replace(/<title>[^<]*<\/title>/, `<title>${post.title} - Liveenity<\/title>`);
                
                // Update blog post title
                template = template.replace(/(<h1 class="[^"]*?blog-title[^"]*?">).*?(<\/h1>)/, `$1${post.title}$2`);
                
                // Update blog post content
                template = template.replace(/(<div class="[^"]*?blog-content[^"]*?\s+article-content[^"]*?">\s*<p class="[^"]*?lead[^"]*?\s+text-muted[^"]*?\s+mb-5[^"]*?">).*?(<\/p>)/, 
                    `$1${post.content}$2`);
                
                return res.send(template);
            } else {
                // If no post found with the given slug, serve 404 page
                console.log(`Post with slug '${req.params.slug}' not found`);
                const notFoundPath = path.join(__dirname, 'public', '404.html');
                
                // Check if 404.html exists before trying to send it
                try {
                    await fsPromises.access(notFoundPath);
                    return res.status(404).sendFile(notFoundPath);
                } catch (err) {
                    console.error('404.html not found at:', notFoundPath);
                    return res.status(404).send('Page not found');
                }
            }
        } catch (error) {
            console.error('Error serving page:', error);
            // Continue to serve the default page if there's an error
        }
    }
    
    // If no slug or post not found, serve the default page
    res.sendFile(filePath, (err) => {
        if (err) {
            console.error('Error serving pages.html:', err);
            if (err.code === 'ENOENT') {
                return res.status(404).send('pages.html not found');
            }
            return res.status(500).send('Error loading page');
        }
    });
};

// API Endpoints
app.get('/api/keywords', async (req, res) => {
    console.log('\n--- /api/keywords GET request received ---');
    try {
        const keywordsPath = path.join(__dirname, 'SCRAP', 'KEYWORDS.txt');
        console.log('Looking for keywords at:', keywordsPath);
        
        // Check if file exists and is accessible
        try {
            await fsPromises.access(keywordsPath, fs.constants.R_OK | fs.constants.W_OK);
            console.log('File exists and is accessible');
        } catch (accessError) {
            console.error('File access error:', accessError);
            if (accessError.code === 'ENOENT') {
                console.log('File does not exist, creating...');
                try {
                    await fsPromises.mkdir(path.dirname(keywordsPath), { recursive: true });
                    await fsPromises.writeFile(keywordsPath, '', 'utf-8');
                    console.log('Created empty KEYWORDS.txt file');
                } catch (writeError) {
                    console.error('Error creating file:', writeError);
                    return res.status(500).json({ 
                        error: 'Failed to create keywords file',
                        details: writeError.message 
                    });
                }
            } else {
                return res.status(500).json({ 
                    error: 'File access error',
                    details: accessError.message 
                });
            }
        }
        
        // Now read the file
        let keywords = [];
        try {
            const content = await fsPromises.readFile(keywordsPath, 'utf-8');
            console.log('File content:', JSON.stringify(content));
            keywords = content.split('\n')
                .map(k => k.trim())
                .filter(k => k !== '');
            console.log(`Loaded ${keywords.length} keywords from KEYWORDS.txt`);
        } catch (readError) {
            console.error('Error reading file:', readError);
            return res.status(500).json({ 
                error: 'Failed to read keywords file',
                details: readError.message 
            });
        }
        
        console.log('Sending response with keywords:', keywords);
        return res.json({ keywords });
    } catch (error) {
        console.error('Error in /api/keywords:', error);
        res.status(500).json({ 
            error: 'Failed to load keywords',
            details: error.message 
        });
    }
});

app.post('/api/keywords', express.json(), async (req, res) => {
    try {
        const { keywords } = req.body;
        
        if (!Array.isArray(keywords)) {
            return res.status(400).json({ error: 'Keywords must be an array' });
        }
        
        const keywordsPath = path.join(__dirname, 'SCRAP', 'KEYWORDS.txt');
        console.log('Saving keywords to:', keywordsPath);
        const content = keywords.join('\n');
        
        // Ensure the directory exists
        await fsPromises.mkdir(path.dirname(keywordsPath), { recursive: true });
        await fsPromises.writeFile(keywordsPath, content, 'utf-8');
        
        console.log(`Saved ${keywords.length} keywords to KEYWORDS.txt`);
        res.json({ success: true });
    } catch (error) {
        console.error('Error in POST /api/keywords:', error);
        res.status(500).json({ 
            error: 'Failed to save keywords',
            details: error.message 
        });
    }
});

// Serve static files directly
app.use(express.static(path.join(__dirname, 'public')));

// Handle specific routes
app.get('/:page', (req, res, next) => {
    const page = req.params.page;
    
    // Skip if the request is for a file with an extension
    if (path.extname(page)) {
        return next();
    }
    
    const filePath = path.join(__dirname, 'public', 'pages', `${page}.html`);
    
    // Check if the file exists
    fs.access(filePath, fs.constants.F_OK, (err) => {
        if (err) {
            // File doesn't exist, continue to next middleware
            return next();
        }
        // File exists, serve it
        res.sendFile(filePath, (err) => {
            if (err) {
                console.error(`Error serving ${filePath}:`, err);
                next(err);
            }
        });
    });
});

// Define routes
app.get(['/pages', '/pages/:slug'], servePages);

// Handle 404 errors for all other routes
app.use((req, res) => {
  const notFoundPath = path.join(__dirname, 'public', '404.html');
  res.status(404).sendFile(notFoundPath, (err) => {
    if (err) {
      // If the 404 page doesn't exist, send a simple 404 message
      res.status(404).send('404 - Page not found');
    }
  });
});

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

// Moved API endpoints to the top of the route definitions

// --- 5. SPECIFIC ROUTES ---

// Serve index.html from pages directory at root URL
app.get('/', (req, res) => {
    const indexPath = path.join(__dirname, 'public', 'pages', 'index.html');
    console.log('Serving index file from:', indexPath);
    res.sendFile(indexPath, (err) => {
        if (err) {
            console.error('Error serving index.html:', err);
            res.status(500).send('Error loading page');
        }
    });
});

// Handle both /pages and /pages/:slug with the same handler
app.get(['/pages', '/pages/:slug'], servePages);

// Serve keywords.html
app.get('/keywords', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'keywords.html'));
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
    const indexPath = path.join(__dirname, 'public', 'index.html');
    
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