const { Pool } = require('pg');

if (!process.env.DATABASE_URL) {
  console.warn('⚠️ DATABASE_URL غير موجود. تأكد من ربط PostgreSQL في Railway.');
}

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.DATABASE_URL ? { rejectUnauthorized: false } : false
});

async function initDB() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS users (
      user_id BIGINT PRIMARY KEY,
      username TEXT,
      first_name TEXT,
      registered_at TIMESTAMP DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS frida_logs (
      id SERIAL PRIMARY KEY,
      user_id BIGINT,
      device_id TEXT,
      status TEXT,
      result TEXT,
      executed_at TIMESTAMP DEFAULT NOW()
    );
  `);
}

async function addUser(userId, username, firstName) {
  await pool.query(
    `INSERT INTO users (user_id, username, first_name)
     VALUES ($1, $2, $3)
     ON CONFLICT (user_id) DO UPDATE
     SET username = EXCLUDED.username,
         first_name = EXCLUDED.first_name`,
    [userId, username || null, firstName || null]
  );
}

async function getUsersCount() {
  const result = await pool.query('SELECT COUNT(*)::int AS count FROM users');
  return result.rows[0].count;
}

async function logFridaRun(userId, deviceId, status, resultText) {
  await pool.query(
    `INSERT INTO frida_logs (user_id, device_id, status, result)
     VALUES ($1, $2, $3, $4)`,
    [userId, deviceId, status, resultText]
  );
}

module.exports = { pool, initDB, addUser, getUsersCount, logFridaRun };
