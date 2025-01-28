const express = require('express');
const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');
const morgan = require('morgan');
const { body, validationResult } = require('express-validator');
const winston = require('winston');
const dotenv = require('dotenv');
const util = require('util');

dotenv.config();

const app = express();
const port = process.env.PORT || 3000;

const logger = winston.createLogger({
    level: 'info',
    format: winston.format.json(),
    transports: [
        new winston.transports.Console(),
        new winston.transports.File({ filename: 'error.log', level: 'error' }),
        new winston.transports.File({ filename: 'combined.log' }),
    ],
});

app.use(morgan('combined', { stream: { write: (message) => logger.info(message.trim()) } }));
app.use(express.json());

const validateVideoProcessingRequest = [
    body('inputPath').notEmpty().withMessage('Input path is required'),
    body('outputPath').notEmpty().withMessage('Output path is required'),
    body('filters').isArray().withMessage('Filters must be an array'),
    body('scale').isInt({ min: 10, max: 300 }).withMessage('Scale must be between 10 and 300'),
    body('speed').isInt({ min: 50, max: 200 }).withMessage('Speed must be between 50 and 200'),
    body('overlay').optional().isString(),
    body('overlayPosition').optional().isString(),
];

const execAsync = util.promisify(exec);

const processVideo = async (inputPath, outputPath, filters, scale, speed, overlay, overlayPosition) => {
    const pythonScriptPath = path.join(__dirname, 'video_processor.py');
    const args = [
        inputPath,
        outputPath,
        JSON.stringify(filters),
        scale,
        speed,
        overlay || '',
        overlayPosition || ''
    ];

    const command = `python ${pythonScriptPath} ${args.map(arg => `"${arg}"`).join(' ')}`;
    const { stdout, stderr } = await execAsync(command);

    if (stderr) {
        throw new Error(stderr);
    }

    return stdout;
};

app.post('/process-video', validateVideoProcessingRequest, async (req, res) => {
    try {
        const errors = validationResult(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }

        const { inputPath, outputPath, filters, scale, speed, overlay, overlayPosition } = req.body;

        if (!fs.existsSync(inputPath)) {
            return res.status(400).json({ error: 'Input file does not exist' });
        }

        const output = await processVideo(inputPath, outputPath, filters, scale, speed, overlay, overlayPosition);
        logger.info(`Output: ${output}`);
        res.json({ message: 'Video processed successfully', outputPath });
    } catch (error) {
        logger.error(`Error: ${error.message}`);
        res.status(500).json({ error: 'Video processing failed', details: error.message });
    }
});

app.use((err, req, res, next) => {
    logger.error(err.stack);
    res.status(500).json({ error: 'Something went wrong on the server' });
});

app.listen(port, () => {
    logger.info(`Server is running on http://localhost:${port}`);
});