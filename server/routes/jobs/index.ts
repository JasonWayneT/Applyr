import { Router } from 'express';
import { requireApiToken } from '../../middleware.js';
import crudRouter from './crud.js';
import filesRouter from './files.js';
import draftRouter from './draft.js';

const router = Router();
router.use(requireApiToken);
router.use(crudRouter);
router.use(filesRouter);
router.use(draftRouter);

export default router;
