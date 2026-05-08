const fs = require('fs');
const path = require('path');

const submissionDir = path.join(__dirname, '../submissions');
if (!fs.existsSync(submissionDir)) {
  console.log('Submission dir does not exist');
  process.exit(0);
}

const dirs = fs.readdirSync(submissionDir).filter(f => fs.statSync(path.join(submissionDir, f)).isDirectory());

const missing = [];
for (const dir of dirs) {
  const coverLetterPath = path.join(submissionDir, dir, 'CoverLetter.pdf');
  if (!fs.existsSync(coverLetterPath)) {
    missing.push(dir);
  }
}

console.log('Missing CoverLetter.pdf in folders:', missing);
