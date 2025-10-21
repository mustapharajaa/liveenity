import express from "express";
import path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';
import fs from 'fs/promises';
import dotenv from 'dotenv';
import axios from 'axios';

// Initialize express app
const app = express();
const PORT = process.env.PORT || 3000;

// Get directory name in ES module
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Load environment variables
dotenv.config();

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Function to execute SQL query using Turso HTTP API
async function executeQuery(sql, params = []) {
    const timeout = 10000; // 10 second timeout
    
    try {
        console.log('Executing query:', sql);
        console.log('With params:', params);
        
        // Get the database URL from environment variables
        let dbUrl = process.env.TURSO_DATABASE_URL.trim();
        
        // Ensure the URL has the https:// prefix if it's not already there
        if (!dbUrl.startsWith('http')) {
            dbUrl = `https://${dbUrl}`;
        }
        
        // Remove any trailing slashes and /v2/pipeline if present
        dbUrl = dbUrl.replace(/\/$/, '').replace(/\/v2\/pipeline$/, '');
        
        // Turso HTTP API endpoint
        const apiUrl = `${dbUrl}/v2/pipeline`;
        
        const requestBody = {
            requests: [{
                type: 'execute',
                stmt: {
                    sql: sql,
                    args: params
                }
            }]
        };

        console.log('=== Debug: Sending Request with Axios ===');
        console.log('URL:', apiUrl);
        console.log('Headers:', {
            'Authorization': 'Bearer [REDACTED]',
            'Content-Type': 'application/json'
        });
        console.log('Body:', JSON.stringify(requestBody, null, 2));
        console.log('========================================');
        
        const response = await axios({
            method: 'post',
            url: apiUrl,
            headers: {
                'Authorization': `Bearer ${process.env.TURSO_AUTH_TOKEN}`,
                'Content-Type': 'application/json',
            },
            data: requestBody,
            timeout: timeout,
            // Add proxy settings if needed (uncomment and modify as needed)
            // proxy: {
            //     host: '127.0.0.1',
            //     port: 8888,
            //     protocol: 'http'
            // },
            // Disable SSL verification if needed (not recommended for production)
            // httpsAgent: new (require('https').Agent)({  
            //     rejectUnauthorized: false 
            // })
        });

        const data = response.data;
        console.log('=== Debug: Response Received ===');
        console.log('Status:', response.status, response.statusText);
        console.log('Headers:', response.headers);
        console.log('Data:', JSON.stringify(data, null, 2));
        console.log('================================');
        
        // Handle the response format from Turso's HTTP API
        if (data.results && data.results[0]) {
            return {
                rows: data.results[0].response?.result?.rows || [],
                columns: data.results[0].response?.result?.cols || []
            };
        }
        
        throw new Error('Unexpected response format from database');
    } catch (error) {
        console.error('=== Debug: Request Failed ===');
        if (error.response) {
            // The request was made and the server responded with a status code
            // that falls out of the range of 2xx
            console.error('Response error:', {
                status: error.response.status,
                statusText: error.response.statusText,
                headers: error.response.headers,
                data: error.response.data
            });
            throw new Error(`Database error (${error.response.status}): ${JSON.stringify(error.response.data)}`);
        } else if (error.request) {
            // The request was made but no response was received
            console.error('No response received:', error.request);
            throw new Error('No response from database server. Please check your connection.');
        } else if (error.code === 'ECONNABORTED') {
            console.error('Request timeout after', timeout, 'ms');
            throw new Error('Database connection timed out. Please check your internet connection and try again.');
        } else {
            // Something happened in setting up the request that triggered an Error
            console.error('Request setup error:', error.message);
            throw error;
        }
    }
}

// Test database connection endpoint
app.get('/api/test-db', async (req, res) => {
    try {
        console.log('Testing database connection...');
        const result = await executeQuery('SELECT 1 as test');
        res.json({
            success: true,
            message: 'Database connection successful',
            data: result
        });
    } catch (error) {
        console.error('Database test failed:', error);
        res.status(500).json({
            success: false,
            message: 'Database connection failed',
            error: error.message
        });
    }
});

// Serve static files from the root directory (excluding .html files)
app.use(express.static(__dirname, {
    extensions: ['html', 'htm'],
    index: false // Disable automatic index.html serving
}));

// Disable caching for all routes
app.use((req, res, next) => {
    res.set('Cache-Control', 'no-store, no-cache, must-revalidate, private');
    res.set('Pragma', 'no-cache');
    res.set('Expires', '0');
    next();
});

// Custom middleware to log all requests
app.use((req, res, next) => {
    console.log(`[${new Date().toISOString()}] ${req.method} ${req.url}`);
    next();
});

// Routes
app.get('/', async (req, res) => {
    try {
        const content = await fs.readFile(path.join(__dirname, 'index.html'), 'utf8');
        res.set('Content-Type', 'text/html');
        res.send(content);
    } catch (error) {
        console.error('Error serving index.html:', error);
        res.status(500).send('Error loading page');
    }
});

// Handle the specific page route with SSR from Turso
app.get('/pages/pre-recorded-video-to-live-the-ultimate-guide-for-2025', async (req, res) => {
    try {
        const slug = 'pre-recorded-video-to-live-the-ultimate-guide-for-2025';
        
        // First, try to read from the database
        try {
            const result = await executeQuery(
                'SELECT title, content, created_at FROM blog_posts WHERE slug = ?',
                [slug]
            );

            if (result && result.rows && result.rows.length > 0) {
                const post = result.rows[0];
                let template = await fs.readFile(path.join(__dirname, 'pages.html'), 'utf8');
                
                // Convert row data to object if it's in array format
                const postData = Array.isArray(post) ? {
                    title: post[0],
                    content: post[1],
                    created_at: post[2]
                } : post;
                
                template = template
                    .replace('{{title}}', postData.title || 'No Title')
                    .replace('{{content}}', postData.content || 'No content available')
                    .replace('{{date}}', new Date(postData.created_at || Date.now()).toLocaleDateString());
                
                return res.set('Content-Type', 'text/html').send(template);
            }
        } catch (dbError) {
            console.error('Database error, falling back to static content:', dbError);
            // Continue to serve static content as fallback
        }
        
        // Fallback to static content if database fails or no post found
        try {
            const content = await fs.readFile(path.join(__dirname, 'pages.html'), 'utf8');
            return res.set('Content-Type', 'text/html').send(content);
        } catch (fileError) {
            console.error('Error serving static content:', fileError);
            return res.status(500).send('Error loading page');
        }
        
    } catch (error) {
        console.error('Unexpected error:', error);
        res.status(500).send('Error loading page');
    }
});

app.get('/pages', async (req, res) => {
    try {
        const content = await fs.readFile(path.join(__dirname, 'pages.html'), 'utf8');
        res.set('Content-Type', 'text/html');
        res.send(content);
    } catch (error) {
        console.error('Error serving pages.html:', error);
        res.status(500).send('Error loading page');
    }
});

// Handle 404
app.use((req, res) => {
    console.log(`404 - Not Found: ${req.originalUrl}`);
    res.status(404).send('404 - Not Found');
});

// Error handling
app.use((err, req, res, next) => {
    console.error('Server error:', err.stack);
    res.status(500).send('500 - Server Error');
});

// Start server
const server = app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
    console.log('Available routes:');
    console.log(`- http://localhost:${PORT}/`);
    console.log(`- http://localhost:${PORT}/pages`);
});

// Handle server errors
server.on('error', (error) => {
    if (error.code === 'EADDRINUSE') {
        console.error(`Port ${PORT} is already in use`);
    } else {
        console.error('Server error:', error);
    }
});

