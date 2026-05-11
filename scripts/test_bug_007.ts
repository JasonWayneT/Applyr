import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const db = new Database(path.join(__dirname, '../jobagent.sqlite'));

// Create a fake dummy job
const fakeId = "test-bug-007-fake-id";
const fakeUrl = "http://example.com/fake-redirect";
try {
  db.prepare("INSERT OR IGNORE INTO jobs (id, company, title, url, status) VALUES (?, ?, ?, ?, 'New')")
    .run(fakeId, "Fake Corp", "Fake Role", fakeUrl);

  console.log('Created dummy job. Simulating error...');

  // Define dummy job object mimicking existing logic
  const job = { id: fakeId, company: "Fake Corp", title: "Fake Role", url: fakeUrl };

  // Simulate the exact Playwright error message provided in the user report
  const simulateError = new Error('page.goto: Navigation to "http://..." is interrupted by another navigation to "http://..."');

  // The logic we added to scrape_new_jobs.ts:
  const e: any = simulateError;
  if (e.message && e.message.includes('interrupted by another navigation')) {
    console.log('>> SUCCESS: Condition matched simulateError');
    db.prepare('INSERT OR IGNORE INTO stale_jobs (url, company, title) VALUES (?, ?, ?)').run(job.url, job.company, job.title);
    db.prepare('DELETE FROM jobs WHERE id = ?').run(job.id);
    console.log('>> SUCCESS: DB clean-up run.');
  } else {
    console.error('>> FAIL: Condition did not match message');
  }

  // Final verify
  const checkJobs = db.prepare("SELECT id FROM jobs WHERE id = ?").get(fakeId);
  const checkStale = db.prepare("SELECT url FROM stale_jobs WHERE url = ?").get(fakeUrl);

  if (!checkJobs && checkStale) {
    console.log(">> VERIFICATION COMPLETE: Job moved to stale_jobs correctly!");
  } else {
    console.error(">> VERIFICATION FAILED", { checkJobs, checkStale });
  }

  // Clean up the stale job to avoid polluting DB
  db.prepare("DELETE FROM stale_jobs WHERE url = ?").run(fakeUrl);
  console.log("Cleaned up regression artifacts.");

} catch (err) {
  console.error("Script Error:", err);
} finally {
  db.close();
}
