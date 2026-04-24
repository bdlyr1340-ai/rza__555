const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false }
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
    `INSERT INTO users (user_id, username, first_name) VALUES ($1, $2, $3)
     ON CONFLICT (user_id) DO NOTHING`,
    [userId, username, firstName]
  );
}

async function logFridaRun(userId, deviceId, status, result) {
  await pool.query(
    `INSERT INTO frida_logs (user_id, device_id, status, result) VALUES ($1,$2,$3,$4)`,
    [userId, deviceId, status, result]
  );
}

module.exports = { initDB, addUser, logFridaRun, pool };