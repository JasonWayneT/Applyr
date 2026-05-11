import http from 'http';

const data = JSON.stringify({
  model: "hf.co/unsloth/gemma-4-26B-A4B-it-GGUF:UD-IQ4_XS",
  prompt: "hi",
  stream: false
});

const options = {
  hostname: 'localhost',
  port: 11434,
  path: '/api/generate',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Content-Length': data.length
  }
};

console.log("Attempting to ping bigger model via direct node http request...");
const req = http.request(options, (res) => {
  console.log(`STATUS: ${res.statusCode}`);
  res.setEncoding('utf8');
  res.on('data', (chunk) => {
    console.log(`BODY: ${chunk}`);
  });
});

req.on('error', (e) => {
  console.error(`problem with request: ${e.message}`);
});

req.write(data);
req.end();
