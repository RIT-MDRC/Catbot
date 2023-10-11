#! /usr/bin/env node
import yargs from 'yargs';
import { hideBin } from 'yargs/helpers';
import { spawn } from 'child_process';
import { install } from './install.js';
import { upload } from './upload.js';

yargs(hideBin(process.argv))
	.command({
		command: 'install',
		aliases: ['i'],
		describe: 'set up arduino and raspberry pi to run catbot',
		handler(args) {
			const debug = args.d ?? false;
			console.log(`installing catbot... (debug: ${debug})`);
			return install(debug);
		},
	})
	.command({
		command: 'upload',
		aliases: ['u'],
		describe: 'upload catbot code to arduino',
		handler: upload,
	})
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
			file = args.f ?? args.file ?? 'main';
			console.log(
				`starting catbot${args.f ? ` with file '${args.f}.py'` : '...'}`
			);
			const childProcess = spawn('python', [`src/raspi/${file}.py`], {
				stdio: 'inherit',
			});
			childProcess.on('close', (code) => {
				console.log(`exited with code ${code}`);
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
