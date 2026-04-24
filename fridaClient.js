const axios = require('axios');

function getAgents() {
  try {
    return JSON.parse(process.env.FRIDA_AGENTS || '{}');
  } catch (err) {
    console.error('FRIDA_AGENTS JSON error:', err.message);
    return {};
  }
}

async function runFridaScript(deviceId, userId) {
  const agents = getAgents();
  const agentUrl = agents[deviceId];

  if (!agentUrl) return `❌ الجهاز '${deviceId}' غير مسجل في FRIDA_AGENTS`;

  try {
    const response = await axios.post(`${agentUrl}/run_frida`, {
      script: 'hook_1m.js',
      user_id: userId
    }, { timeout: 60000 });

    const data = typeof response.data === 'string'
      ? response.data
      : JSON.stringify(response.data, null, 2);

    return `✅ تم التنفيذ على ${deviceId}:\n${data.slice(0, 900)}`;
  } catch (error) {
    return `🔌 فشل الاتصال: ${error.message}`;
  }
}

module.exports = { getAgents, runFridaScript };
