// server.js

// 1. MODULE IMPORTS (ESM Syntax)
// Use 'dotenv/config' to automatically load environment variables from .env
import 'dotenv/config'; 
import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
import { createClient } from "@libsql/client";

// --- 2. CONFIGURATION & INITIALIZATION ---
const app = express();
const PORT = process.env.PORT || 3000;

// Get connection details from environment variables
const dbUrl = process.env.TURSO_DATABASE_URL;
const dbAuthToken = process.env.TURSO_AUTH_TOKEN;

// Initialize the libSQL client
if (!dbUrl || !dbAuthToken) {
    console.error("FATAL ERROR: TURSO_DATABASE_URL or TURSO_AUTH_TOKEN is missing in environment variables.");
    process.exit(1); // Exit if essential variables are missing
}

const db = createClient({
    url: dbUrl,
    authToken: dbAuthToken,
});

console.log("Turso client initialized successfully.");

// --- 3. MIDDLEWARE ---
app.use(cors());
app.use(express.json());

// Serve static files from the 'public' directory
app.use(express.static('public'));

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
app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
    console.log("API endpoints:");
    console.log(`- GET  /api/test - Test database connection`);
    console.log(`- GET  /api/search?query=your_search_term - Search posts`);
});