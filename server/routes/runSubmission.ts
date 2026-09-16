import { Router, type NextFunction, type Request, type Response } from 'express';
import { requireApiToken } from '../middleware.js';
import {
  RunSubmissionServiceError,
  runSubmissionCommand,
  type RunSubmissionCommand,
  type RunSubmissionCommandResult,
  type RunSubmissionRequest,
  type RunSubmissionScope,
} from '../services/runSubmissionRunner.js';

type RunSubmissionService = (
  request: RunSubmissionRequest,
) => Promise<RunSubmissionCommandResult>;

const COMMANDS: RunSubmissionCommand[] = ['start', 'resume', 'status', 'finalize'];
const SCOPES = new Set<RunSubmissionScope>(['pending-review', 'submissions']);

function requireConfiguredApiToken(
  _req: Request,
  res: Response,
  next: NextFunction,
): void {
  if (!process.env.APPLYR_API_TOKEN) {
    res.status(503).json({ error: 'Operator API token is not configured.' });
    return;
  }
  next();
}

/**
 * Build authenticated routes for the canonical submission workflow operator.
 * Implements FR-316 / AC-413 and uses the existing CR-025 token middleware.
 */
export function createRunSubmissionRouter(
  service: RunSubmissionService = runSubmissionCommand,
): Router {
  const router = Router();
  router.use(requireConfiguredApiToken);
  router.use(requireApiToken);

  for (const command of COMMANDS) {
    router.post('/api/run-submission/:scope/:slug/' + command, async (req, res) => {
      const scope = req.params.scope;
      const slug = req.params.slug;
      if (
        Array.isArray(scope)
        || Array.isArray(slug)
        || !SCOPES.has(scope as RunSubmissionScope)
      ) {
        res.status(400).json({ error: 'Invalid submission scope.' });
        return;
      }
      try {
        const result = await service({
          command,
          scope: scope as RunSubmissionScope,
          slug,
        });
        res.json(result);
      } catch (error) {
        if (error instanceof RunSubmissionServiceError) {
          res.status(error.statusCode).json({ error: error.message });
          return;
        }
        res.status(500).json({ error: 'Submission workflow request failed.' });
      }
    });
  }

  return router;
}

export const runSubmissionRouter = createRunSubmissionRouter();
