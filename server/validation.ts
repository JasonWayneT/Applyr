import { z } from 'zod';
import type { Request, Response, NextFunction } from 'express';

// CR-104 Epic 8: Zod schema validation for the highest-risk write routes.

/** Job creation body — POST /api/jobs */
export const createJobSchema = z.object({
  id: z.string().optional(),
  company: z.string().min(1, 'company is required'),
  title: z.string().min(1, 'title is required'),
  url: z.string().url().optional().or(z.literal('')),
  score: z.union([z.number(), z.string()]).optional(),
  summary: z.string().optional(),
  status: z.string().optional(),
});

/** Job update body — PATCH /api/jobs/:id (partial, arbitrary fields) */
export const patchJobSchema = z.record(z.string(), z.unknown()).refine(
  (obj) => Object.keys(obj).some((k) => k !== 'id'),
  'No valid fields to update',
);

/** Job search preferences — POST /api/profile/job_search */
export const jobSearchSchema = z.record(z.string(), z.unknown());

/** Experience content — POST /api/experience */
export const experienceSchema = z.object({
  content: z.string().min(1, 'content is required'),
});

/** Generic profile blob — POST /api/profile/:key (must be a non-null object) */
export const profileBlobSchema = z.record(z.string(), z.unknown());

/** Express middleware factory: validates req.body against a Zod schema,
 * returns 400 with the first issue on failure. */
export function validateBody<T>(schema: z.ZodSchema<T>) {
  return (req: Request, res: Response, next: NextFunction) => {
    const result = schema.safeParse(req.body);
    if (!result.success) {
      const issue = result.error.issues[0];
      const message = issue.path.length > 0
        ? `${issue.path.join('.')}: ${issue.message}`
        : issue.message;
      return res.status(400).json({ error: message });
    }
    req.body = result.data;
    next();
  };
}
