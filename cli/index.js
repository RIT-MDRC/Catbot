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
			const srcFolder =
				args.proj ?? args.p ?? (args.D || args.dev)
					? 'src'
					: SRC_FOLDER;
			const file = args.f ?? args.file ?? 'raspi/main';
			console.log(
				`starting catbot${args.f ? ` with file '${args.f}.py'` : '...'}`
			);
			const childProcess = spawn('python3', [`${srcFolder}/${file}.py`], {
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
	.demandCommand(1, '')
	.parse();
