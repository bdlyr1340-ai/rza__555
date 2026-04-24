const axios = require('axios');

function getAgents() {
  const raw = process.env.FRIDA_AGENTS || '{}';
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
    return parsed;
  } catch (err) {
    console.error('❌ FRIDA_AGENTS JSON error:', err.message);
    console.error('FRIDA_AGENTS value must be like: {"phone1":"http://1.2.3.4:5000"}');
    return {};
  }
}

async function runFridaScript(deviceId, userId) {
  const agents = getAgents();
  const agentUrl = agents[deviceId];

  if (!agentUrl) return `❌ الجهاز '${deviceId}' غير مسجل في FRIDA_AGENTS`;

  try {
    const response = await axios.post(`${String(agentUrl).replace(/\/$/, '')}/run_frida`, {
      script: 'hook_1m.js',
      user_id: userId
    }, { timeout: 60000 });

    const data = typeof response.data === 'string'
      ? response.data
      : JSON.stringify(response.data, null, 2);

    return `✅ تم التنفيذ على ${deviceId}:\n${data.slice(0, 900)}`;
  } catch (error) {
    if (error.response) {
      return `🔌 فشل الاتصال: HTTP ${error.response.status}\n${JSON.stringify(error.response.data).slice(0, 500)}`;
    }
    return `🔌 فشل الاتصال: ${error.message}`;
  }
}

module.exports = { getAgents, runFridaScript };
