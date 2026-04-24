const axios = require('axios');

async function runFridaScript(deviceId, userId) {
  const agentsRaw = process.env.FRIDA_AGENTS || '{}';
  const agents = JSON.parse(agentsRaw);
  const agentUrl = agents[deviceId];
  if (!agentUrl) return `❌ الجهاز '${deviceId}' غير مسجل`;

  try {
    const response = await axios.post(`${agentUrl}/run_frida`, {
      script: 'hook_1m.js',
      user_id: userId
    }, { timeout: 60000 });
    return `✅ تم التنفيذ على ${deviceId}:\n${response.data.slice(0, 500)}`;
  } catch (error) {
    return `🔌 فشل الاتصال: ${error.message}`;
  }
}

module.exports = { runFridaScript };