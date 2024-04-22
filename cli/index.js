#! /usr/bin/env node
import { spawn } from 'child_process';
import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';

const DEFAULT_FOLDER = '/opt/catbot/src';
const DEV_SRC_FOLDER = './src';
const DEFAULT_FILE_PATH = 'raspi/main';
const PYTHON_COMMAND = "python3"


yargs(hideBin(process.argv))
	.command({
		command: 'start',
		aliases: ['s'],
		describe: 'start catbot',
		builder: (yargs) =>
			yargs
				.option('f', {
					alias: 'file',
					describe: 'specify file to run',
					type: 'string',
				})
				.option('p', {
					alias: 'proj',
					describe: 'run from a specific project folder',
					type: 'string',
				})
				.option('D', {
					alias: 'dev',
					describe:
						'run from current repo folder instead of the global copy',
					type: 'boolean',
				}),
		handler(args) {
			const sourcePath =
				args.D || args.dev ? DEV_SRC_FOLDER : DEFAULT_FOLDER;
			const srcFolder = args.proj ?? args.p ?? sourcePath;
			const file = args.f ?? args.file ?? DEFAULT_FILE_PATH;
			console.log(
				`starting catbot${args.f ? ` with file '${args.f}.py'` : '...'}`
			);
			const childProcess = spawn(PYTHON_COMMAND, [`${srcFolder}/${file}.py`], {
				stdio: 'inherit',
			});
			childProcess.on('close', (code) => {
				console.log(`exited with code ${code}`);
			});
			childProcess.on('error', (err) => {
				console.log('Failed to execute python script');
				console.log(
					"Make sure you have python3 installed and that you have ran 'npm run postinstall'"
				);
				console.log(err);
			});
		},
	})
	.command({
		command: 'sample [file]',
		aliases: ['smpl'],
		describe: 'run sample code',
		builder: (yargs) =>
			yargs
				.option('file', {
					alias: 'f',
					describe: 'run the specified sample file',
					type: 'string',
				})
				.option('D', {
					alias: 'dev',
					describe:
						'run from current repo folder instead of the global copy',
					type: 'boolean',
				}),
		handler(args) {
			const file = args.file;
			if (!file) {
				console.log(
					'No file specified. Please specify a file after the command.'
				);
				process.exit(1);
			}
			console.log(`running sample file '${file}.py'`);
			const sourcePath =
				args.D || args.dev ? DEV_SRC_FOLDER : DEFAULT_FOLDER;
			const childProcess = spawn(
				PYTHON_COMMAND,
				[`${sourcePath}/raspi/samples/${file}.py`],
				{
					env: {
						...process.env, PYTHONPATH: sourcePath + '/raspi'},
					stdio: 'inherit',
				}
			);
			childProcess.on('close', (code) => {
				console.log(`exited with code ${code}`);
			});
			childProcess.on('error', (err) => {
				console.log('Failed to execute python script');
				console.log(
					"Make sure you have python3 installed and that you have ran 'npm run postinstall'"
				);
				console.log(err);
			});
		},
	})
	.demandCommand(1, '')
	.parse();
