const { Pool } = require('pg');

let pool = null;
let dbReady = false;
let lastDbError = null;

function hasDatabaseConfig() {
  return Boolean(
    process.env.DATABASE_URL ||
    (process.env.PGHOST && process.env.PGUSER && process.env.PGDATABASE)
  );
}

function createPool() {
  if (!hasDatabaseConfig()) {
    lastDbError = 'DATABASE_URL أو متغيرات PGHOST/PGUSER/PGDATABASE غير موجودة داخل خدمة البوت.';
    console.warn('⚠️ ' + lastDbError);
    return null;
  }

  const config = process.env.DATABASE_URL
    ? { connectionString: process.env.DATABASE_URL }
    : {
        host: process.env.PGHOST,
        port: Number(process.env.PGPORT || 5432),
        user: process.env.PGUSER,
        password: process.env.PGPASSWORD,
        database: process.env.PGDATABASE
      };

  // Railway Postgres عادة يحتاج SSL عند استخدام DATABASE_URL/الخدمة الداخلية.
  config.ssl = { rejectUnauthorized: false };

  return new Pool(config);
}

async function initDB() {
  pool = createPool();
  if (!pool) return false;

  try {
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
    dbReady = true;
    lastDbError = null;
    console.log('✅ Database connected and tables are ready.');
    return true;
  } catch (err) {
    dbReady = false;
    lastDbError = err.message;
    console.error('❌ Database init error:', err);
    return false;
  }
}

async function safeQuery(sql, params = []) {
  if (!dbReady || !pool) {
    throw new Error(lastDbError || 'Database is not ready');
  }
  return pool.query(sql, params);
}

async function addUser(userId, username, firstName) {
  return safeQuery(
    `INSERT INTO users (user_id, username, first_name)
     VALUES ($1, $2, $3)
     ON CONFLICT (user_id) DO UPDATE
     SET username = EXCLUDED.username,
         first_name = EXCLUDED.first_name`,
    [userId, username || null, firstName || null]
  );
}

async function getUsersCount() {
  const result = await safeQuery('SELECT COUNT(*)::int AS count FROM users');
  return result.rows[0].count;
}

async function logFridaRun(userId, deviceId, status, resultText) {
  return safeQuery(
    `INSERT INTO frida_logs (user_id, device_id, status, result)
     VALUES ($1, $2, $3, $4)`,
    [userId, deviceId, status, resultText]
  );
}

function getDbStatus() {
  return { ready: dbReady, error: lastDbError };
}

module.exports = { initDB, addUser, getUsersCount, logFridaRun, getDbStatus };
