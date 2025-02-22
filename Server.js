const express = require('express');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs').promises;
const morgan = require('morgan');
const { body, validationResult } = require('express-validator');
const winston = require('winston');
const dotenv = require('dotenv');
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

const processVideo = async (inputPath, outputPath, filters, scale, speed, overlay, overlayPosition) => {
    const pythonScriptPath = path.join(__dirname, 'video_processor.py');
    const stats = await fs.stat(inputPath);
    if (!stats.isFile()) {
        throw new Error('Input path must point to a valid file.');
    }

    return new Promise((resolve, reject) => {
        const args = [
            inputPath,
            outputPath,
            JSON.stringify(filters),
            String(scale),
            String(speed),
            overlay || '',
            overlayPosition || ''
        ];

        const pythonProcess = spawn('python', [pythonScriptPath, ...args]);

        let stdout = '';
        let stderr = '';

        pythonProcess.stdout.on('data', data => stdout += data.toString());
        pythonProcess.stderr.on('data', data => stderr += data.toString());
        pythonProcess.on('close', (code) => {
            if (code !== 0) {
                return reject(new Error(`Python script failed with exit code ${code}: ${stderr}`));
            }
            resolve(stdout);
        });
    });
};

app.post('/process-video', validateVideoProcessingRequest, async (req, res) => {
    try {
        const errors = validationResult(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({ errors: errors.array() });
        }

        const { inputPath, outputPath, filters, scale, speed, overlay, overlayPosition } = req.body;

        logger.info(`Starting video processing for input: ${inputPath}`);

        if (!(await fs.stat(inputPath)).isFile()) {
            return res.status(400).json({ error: 'Input file does not exist or is not accessible.' });
        }

        const output = await processVideo(inputPath, outputPath, filters, scale, speed, overlay, overlayPosition);

        logger.info(`Video processing completed successfully. Output: ${output}`);

        return res.json({
            message: 'Video processed successfully',
            outputPath,
            details: output
        });
    } catch (error) {
        logger.error(`Error during video processing: ${error.message}`);
        return res.status(500).json({ error: 'Video processing failed', details: error.message });
    }
});

app.use((err, req, res, next) => {
    logger.error(err.stack);
    res.status(500).json({ error: 'Something went wrong on the server' });
});

app.listen(port, () => {
    logger.info(`Server is running on http://localhost:${port}`);
});


