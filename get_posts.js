import { createClient } from '@libsql/client';
import fs from 'fs';
import dotenv from 'dotenv';

dotenv.config();

const db = createClient({
  url: process.env.TURSO_DATABASE_URL,
  authToken: process.env.TURSO_AUTH_TOKEN
});

async function getPosts() {
  try {
    const result = await db.execute('SELECT slug FROM blog_posts');
    console.log('Blog posts:', result.rows);
    return result.rows;
  } catch (error) {
    console.error('Error fetching posts:', error);
    return [];
  }
}

getPosts();
