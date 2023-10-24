#! /usr/bin/env node
import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';
import { spawn } from 'child_process';

const SRC_FOLDER = '/opt/catbot/src';

yargs(hideBin(process.argv))
	.command({
		command: 'start',
		aliases: ['s'],
		describe: 'start catbot',
		builder: (yargs) =>
			yargs.option('f', {
				alias: 'file',
				describe: 'specify file to run',
				default: 'main',
				type: 'string',
			}),
		handler(args) {
			const srcFolder = args.D || args.dev ? './src' : SRC_FOLDER;
			const file = args.f ?? args.file ?? 'main';
			console.log(
				`starting catbot${args.f ? ` with file '${args.f}.py'` : '...'}`
			);
			const childProcess = spawn(
				'python3',
				[`${srcFolder}/raspi/${file}.py`],
				{
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
	.command({
		command: 'arduino',
		aliases: ['a'],
		describe: 'run arduino cli',
		handler(args) {
			console.log('running arduino cli...');
			const childProcess = spawn('arduino-cli', args._.slice(1), {
				stdio: 'inherit',
			});
			childProcess.on('close', (code) =>
				console.log(`exited with code ${code}`)
			);
		},
	})
	.demandCommand(1, '')
	.parse();
