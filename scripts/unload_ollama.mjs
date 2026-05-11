import http from 'http';

const models = [
  "gemma4-e4b:latest",
  "ministral-3-14b:latest",
  "hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-IQ4_XS",
  "gemma2:9b"
];

async function unload(modelName) {
  return new Promise((resolve) => {
    const data = JSON.stringify({
      model: modelName,
      keep_alive: 0
    });

    const options = {
      hostname: 'localhost',
      port: 11434,
      path: '/api/chat',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': data.length
      }
    };

    const req = http.request(options, (res) => {
      console.log(`UNLOAD ${modelName} -> STATUS: ${res.statusCode}`);
      resolve();
    });
    req.on('error', () => resolve());
    req.write(data);
    req.end();
  });
}

async function run() {
  for (const m of models) {
    await unload(m);
  }
  console.log("All unload trigger signals sent.");
}

run();
