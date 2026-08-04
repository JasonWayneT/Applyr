import { Router } from 'express';
import { requireApiToken } from '../../middleware.js';
import crudRouter from './crud.js';
import filesRouter from './files.js';
import debriefsRouter from './debriefs.js';

const router = Router();
router.use(requireApiToken);
router.use(crudRouter);
router.use(filesRouter);
router.use(debriefsRouter);

export default router;
